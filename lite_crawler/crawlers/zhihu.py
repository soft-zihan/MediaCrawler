# -*- coding: utf-8 -*-
"""
知乎轻量级爬虫

爬取规则：
- 最多8条回答/文章
- 每条内容获取前20条评论
- 包含回答内容
- 不爬取答主个人信息
"""

import asyncio
from typing import Dict, List, Optional, Any

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools import utils
from media_platform.zhihu.client import ZhiHuClient
from media_platform.zhihu.login import ZhiHuLogin
from model.m_zhihu import ZhihuContent

from .base import BaseLiteCrawler
from ..models import ContentItem, CommentItem, ContentType
from ..config import get_config


class ZhihuLiteCrawler(BaseLiteCrawler):
    """知乎轻量级爬虫"""
    
    platform_name = "zhihu"
    index_url = "https://www.zhihu.com"
    
    def __init__(self, config=None):
        super().__init__(config)
        self.zhihu_client: Optional[ZhiHuClient] = None
    
    def _get_user_agent(self) -> str:
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    
    async def initialize(self, playwright):
        """知乎需要特殊处理：先访问首页确保Cookie正确加载"""
        if self._is_initialized:
            return True
        
        try:
            utils.logger.info(f"[{self.platform_name}] 初始化爬虫...")
            
            # 使用CDP模式启动浏览器
            if self.config.enable_cdp_mode:
                from tools.cdp_browser import CDPBrowserManager
                self.cdp_manager = CDPBrowserManager()
                self.browser_context = await self.cdp_manager.launch_and_connect(
                    playwright=playwright,
                    playwright_proxy=None,
                    user_agent=self._get_user_agent(),
                    headless=self.config.headless,
                )
            else:
                browser = await playwright.chromium.launch(headless=self.config.headless)
                self.browser_context = await browser.new_context(
                    user_agent=self._get_user_agent()
                )
                await self.browser_context.add_init_script(path="libs/stealth.min.js")
            
            # 创建页面并访问首页
            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(self.index_url, wait_until="domcontentloaded")
            
            # 等待页面完全加载
            await asyncio.sleep(3)
            
            # 初始化API客户端
            await self._init_client()
            
            # 检查登录状态
            is_logged_in = False
            try:
                is_logged_in = await self._check_login()
            except Exception as e:
                utils.logger.warning(f"[zhihu] 登录检查异常: {e}")
            
            if not is_logged_in:
                # 尝试通过访问页面检测登录状态（检查页面上是否有登录按钮）
                try:
                    login_btn = await self.context_page.query_selector("button.SignContainer-switch")
                    if login_btn:
                        # 有登录按钮，说明未登录
                        utils.logger.info("[zhihu] 检测到未登录状态，开始登录...")
                        await self._do_login()
                        # 登录后更新Cookie
                        await self._update_client_cookies()
                    else:
                        # 没有登录按钮，可能已登录，重新获取Cookie
                        utils.logger.info("[zhihu] 页面显示已登录状态，更新Cookie...")
                        await self._update_client_cookies()
                except Exception as e:
                    utils.logger.warning(f"[zhihu] 页面登录状态检测失败: {e}，尝试继续...")
            
            # 知乎的搜索API需要先打开搜索页面获取额外Cookie
            utils.logger.info("[zhihu] 访问搜索页面获取Cookie...")
            await self.context_page.goto(
                f"{self.index_url}/search?q=test&search_source=Guess&type=content"
            )
            await asyncio.sleep(3)
            await self._update_client_cookies()
            
            self._is_initialized = True
            utils.logger.info(f"[{self.platform_name}] 初始化完成")
            return True
            
        except Exception as e:
            utils.logger.error(f"[{self.platform_name}] 初始化失败: {e}")
            return False
    
    async def _init_client(self):
        """初始化知乎API客户端"""
        cookie_str, cookie_dict = await self._get_zhihu_cookies()
        self.zhihu_client = ZhiHuClient(
            timeout=self.config.request_timeout,
            headers={
                "User-Agent": await self.context_page.evaluate("() => navigator.userAgent"),
                "Cookie": cookie_str,
                "Origin": "https://www.zhihu.com",
                "Referer": "https://www.zhihu.com/",
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
        )
    
    async def _get_zhihu_cookies(self):
        """只获取知乎域名的Cookie"""
        zhihu_cookies = await self.browser_context.cookies(urls=["https://www.zhihu.com"])
        return utils.convert_cookies(zhihu_cookies)
    
    async def _update_client_cookies(self):
        """更新客户端的Cookie（只使用知乎域名的Cookie）"""
        cookie_str, cookie_dict = await self._get_zhihu_cookies()
        self.zhihu_client.default_headers["cookie"] = cookie_str
        self.zhihu_client.cookie_dict = cookie_dict
    
    async def _check_login(self) -> bool:
        """检查知乎登录状态"""
        try:
            return await self.zhihu_client.pong()
        except Exception:
            return False
    
    async def _do_login(self):
        """执行知乎登录"""
        login_obj = ZhiHuLogin(
            login_type=self.config.login_type,
            login_phone="",
            browser_context=self.browser_context,
            context_page=self.context_page,
            cookie_str=self.config.cookies,
        )
        await login_obj.begin()
        await self.zhihu_client.update_cookies(browser_context=self.browser_context)
    
    async def search(self, keyword: str) -> List[ContentItem]:
        """
        搜索知乎内容
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            回答/文章内容列表
        """
        contents = []
        
        try:
            utils.logger.info(f"[zhihu] 搜索关键词: {keyword}")
            
            # 搜索内容
            content_list: List[ZhihuContent] = await self.zhihu_client.get_note_by_keyword(
                keyword=keyword,
                page=1,
            )
            
            count = 0
            for zhihu_content in content_list:
                if count >= self.max_contents:
                    break
                    
                try:
                    # 判断内容类型
                    content_type_str = zhihu_content.content_type
                    if content_type_str == "answer":
                        ct = ContentType.ANSWER.value
                    elif content_type_str == "article":
                        ct = ContentType.ARTICLE.value
                    else:
                        ct = ContentType.ANSWER.value
                    
                    # 构建URL
                    if content_type_str == "answer":
                        url = f"https://www.zhihu.com/question/{zhihu_content.question_id}/answer/{zhihu_content.content_id}"
                    else:
                        url = f"https://zhuanlan.zhihu.com/p/{zhihu_content.content_id}"
                    
                    # 提取内容摘要（使用 content_text 而非 content）
                    content_text = self.clean_text(zhihu_content.content_text or "")
                    title = self.clean_text(zhihu_content.title or "")
                    
                    content = ContentItem(
                        platform=self.platform_name,
                        content_type=ct,
                        title=title if title else content_text[:50],
                        content=content_text,
                        url=url,
                        publish_time=str(zhihu_content.created_time or ""),
                        like_count=self.format_count(zhihu_content.voteup_count),
                        comment_count=self.format_count(zhihu_content.comment_count),
                        share_count=0,
                        view_count=0,
                        extra={
                            "content_id": zhihu_content.content_id,
                            "content_type": content_type_str,
                            "question_id": zhihu_content.question_id or "",
                        }
                    )
                    contents.append(content)
                    count += 1
                    
                    # 添加爬取间隔
                    await asyncio.sleep(self.config.crawl_interval)
                    
                except Exception as e:
                    utils.logger.warning(f"[zhihu] 处理内容失败: {e}")
                    continue
            
        except Exception as e:
            utils.logger.error(f"[zhihu] 搜索失败: {e}")
        
        return contents
    
    async def get_comments(self, content_id: str, **kwargs) -> List[CommentItem]:
        """
        获取知乎内容评论
        
        知乎评论限制为20条
        
        Args:
            content_id: 内容ID
            **kwargs: 包含 content_type, question_id
            
        Returns:
            评论列表（最多20条）
        """
        comments = []
        
        try:
            utils.logger.info(f"[zhihu] 获取内容 {content_id} 的评论")
            
            content_type = kwargs.get("content_type", "answer")
            
            # 直接使用 get_root_comments 获取评论
            comment_result = await self.zhihu_client.get_root_comments(
                content_id=content_id,
                content_type=content_type,
                offset="",
                limit=self.max_comments,  # 知乎20条
            )
            
            comment_list = comment_result.get("data", []) or []
            
            # 转换评论格式
            for comment_data in comment_list[:self.max_comments]:
                try:
                    # comment_data 可能是 dict 或者 ZhihuComment 对象
                    if hasattr(comment_data, 'content'):
                        content_text = comment_data.content
                        like_count = comment_data.like_count if hasattr(comment_data, 'like_count') else 0
                        create_time = str(comment_data.create_time) if hasattr(comment_data, 'create_time') else ""
                    else:
                        content_text = comment_data.get("content", "")
                        like_count = comment_data.get("like_count", 0)
                        create_time = str(comment_data.get("create_time", ""))
                    
                    comment = CommentItem(
                        content=self.clean_text(content_text),
                        like_count=self.format_count(like_count),
                        create_time=create_time,
                        is_reply=False,
                    )
                    comments.append(comment)
                except Exception as e:
                    utils.logger.warning(f"[zhihu] 处理评论失败: {e}")
                    continue
                    
        except Exception as e:
            utils.logger.error(f"[zhihu] 获取评论失败: {e}")
        
        return comments
