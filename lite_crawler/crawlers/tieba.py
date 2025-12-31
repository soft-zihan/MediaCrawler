# -*- coding: utf-8 -*-
"""
百度贴吧轻量级爬虫

爬取规则：
- 最多8条帖子
- 每个帖子获取所有评论（上限约100条，约2页）
- 包含帖子标题和内容
- 不爬取用户个人信息
"""

import asyncio
from typing import Dict, List, Optional, Any

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools import utils
from media_platform.tieba.client import BaiduTieBaClient
from media_platform.tieba.login import BaiduTieBaLogin
from media_platform.tieba.field import SearchSortType, SearchNoteType
from model.m_baidu_tieba import TiebaNote

from .base import BaseLiteCrawler
from ..models import ContentItem, CommentItem, ContentType
from ..config import get_config


class TiebaLiteCrawler(BaseLiteCrawler):
    """百度贴吧轻量级爬虫"""
    
    platform_name = "tieba"
    index_url = "https://tieba.baidu.com"
    
    def __init__(self, config=None):
        super().__init__(config)
        self.tieba_client: Optional[BaiduTieBaClient] = None
        # 缓存帖子详情用于获取评论
        self._note_details_cache: Dict[str, TiebaNote] = {}
    
    async def initialize(self, playwright):
        """贴吧需要特殊的初始化流程"""
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
            
            # 贴吧需要注入反检测脚本
            await self._inject_anti_detection_scripts()
            
            self.context_page = await self.browser_context.new_page()
            
            # 贴吧需要先访问百度首页，再进入贴吧
            await self._navigate_to_tieba_via_baidu()
            
            # 初始化API客户端
            await self._init_client()
            
            # 检查并执行登录
            if not await self._check_login():
                await self._do_login()
            
            self._is_initialized = True
            utils.logger.info(f"[{self.platform_name}] 初始化完成")
            return True
            
        except Exception as e:
            utils.logger.error(f"[{self.platform_name}] 初始化失败: {e}")
            return False
    
    async def _inject_anti_detection_scripts(self):
        """注入反检测脚本"""
        # 贴吧的特殊反检测
        await self.browser_context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
    
    async def _navigate_to_tieba_via_baidu(self):
        """通过百度首页进入贴吧"""
        utils.logger.info("[tieba] 通过百度首页进入贴吧...")
        await self.context_page.goto("https://www.baidu.com", wait_until="domcontentloaded")
        await asyncio.sleep(2)
        await self.context_page.goto(self.index_url, wait_until="domcontentloaded")
        await asyncio.sleep(2)
    
    async def _init_client(self):
        """初始化贴吧API客户端"""
        # 只获取贴吧相关域名的Cookie
        tieba_cookies = await self.browser_context.cookies(urls=[
            "https://tieba.baidu.com",
            "https://www.baidu.com"
        ])
        cookie_str, cookie_dict = utils.convert_cookies(tieba_cookies)
        # 贴吧客户端不需要 cookie_dict 参数
        self.tieba_client = BaiduTieBaClient(
            timeout=self.config.request_timeout,
            headers={
                "User-Agent": await self.context_page.evaluate("() => navigator.userAgent"),
                "Cookie": cookie_str,
                "Origin": "https://tieba.baidu.com",
                "Referer": "https://tieba.baidu.com/",
            },
            playwright_page=self.context_page,
        )
    
    async def _check_login(self) -> bool:
        """检查贴吧登录状态"""
        try:
            return await self.tieba_client.pong(browser_context=self.browser_context)
        except Exception:
            return False
    
    async def _do_login(self):
        """执行贴吧登录"""
        login_obj = BaiduTieBaLogin(
            login_type=self.config.login_type,
            login_phone="",
            browser_context=self.browser_context,
            context_page=self.context_page,
            cookie_str=self.config.cookies,
        )
        await login_obj.begin()
        await self.tieba_client.update_cookies(browser_context=self.browser_context)
    
    async def search(self, keyword: str) -> List[ContentItem]:
        """
        搜索贴吧帖子
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            帖子内容列表
        """
        contents = []
        
        try:
            utils.logger.info(f"[tieba] 搜索关键词: {keyword}")
            
            # 搜索帖子
            notes_list: List[TiebaNote] = await self.tieba_client.get_notes_by_keyword(
                keyword=keyword,
                page=1,
                page_size=self.max_contents,
                sort=SearchSortType.TIME_DESC,
                note_type=SearchNoteType.FIXED_THREAD,
            )
            
            count = 0
            for note in notes_list:
                if count >= self.max_contents:
                    break
                    
                try:
                    note_id = note.note_id
                    if not note_id:
                        continue
                    
                    # 获取帖子详情
                    note_detail = await self.tieba_client.get_note_by_id(note_id)
                    
                    if not note_detail:
                        continue
                    
                    # 构建帖子URL
                    post_url = f"https://tieba.baidu.com/p/{note_id}"
                    
                    # 提取内容 - TiebaNote 使用 desc 而不是 content
                    title = self.clean_text(note_detail.title or "")
                    content_text = self.clean_text(note_detail.desc or "")
                    
                    content = ContentItem(
                        platform=self.platform_name,
                        content_type=ContentType.POST.value,
                        title=title,
                        content=content_text,
                        url=post_url,
                        publish_time=str(note_detail.publish_time or ""),
                        like_count=0,  # TiebaNote 没有 liked_count
                        comment_count=self.format_count(note_detail.total_replay_num or 0),
                        share_count=0,  # TiebaNote 没有 share_count
                        view_count=0,
                        extra={
                            "content_id": note_id,
                            "tieba_name": note_detail.tieba_name or "",
                            "total_page": note_detail.total_replay_page or 1,
                        }
                    )
                    contents.append(content)
                    
                    # 缓存帖子详情用于后续获取评论
                    self._note_details_cache[note_id] = note_detail
                    
                    count += 1
                    
                    # 添加爬取间隔
                    await asyncio.sleep(self.config.crawl_interval)
                    
                except Exception as e:
                    utils.logger.warning(f"[tieba] 处理帖子失败: {e}")
                    continue
            
        except Exception as e:
            utils.logger.error(f"[tieba] 搜索失败: {e}")
        
        return contents
    
    async def get_comments(self, content_id: str, **kwargs) -> List[CommentItem]:
        """
        获取贴吧帖子评论
        
        贴吧特殊：获取所有评论（上限约100条，约2页）
        
        Args:
            content_id: 帖子ID
            **kwargs: 包含 total_page
            
        Returns:
            评论列表
        """
        comments = []
        
        try:
            utils.logger.info(f"[tieba] 获取帖子 {content_id} 的评论")
            
            # 从缓存获取帖子详情，如果没有则重新获取
            note_detail = self._note_details_cache.get(content_id)
            if not note_detail:
                note_detail = await self.tieba_client.get_note_by_id(content_id)
            
            if not note_detail:
                utils.logger.warning(f"[tieba] 无法获取帖子 {content_id} 详情")
                return comments
            
            # 收集评论的回调
            collected_comments = []
            
            async def comment_callback(note_id: str, comment_list: List):
                collected_comments.extend(comment_list)
            
            # 使用 get_note_all_comments 获取评论
            await self.tieba_client.get_note_all_comments(
                note_detail=note_detail,
                crawl_interval=self.config.crawl_interval,
                callback=comment_callback,
                max_count=self.max_comments,  # 贴吧100条
            )
            
            # 转换评论格式
            for comment_data in collected_comments[:self.max_comments]:
                try:
                    # comment_data 是 TiebaComment 对象
                    content_text = self.clean_text(
                        getattr(comment_data, "content", "") or ""
                    )
                    
                    comment = CommentItem(
                        content=content_text,
                        like_count=self.format_count(
                            getattr(comment_data, "like_count", 0) or 0
                        ),
                        create_time=str(
                            getattr(comment_data, "publish_time", "") or ""
                        ),
                        is_reply=False,
                    )
                    comments.append(comment)
                except Exception as e:
                    utils.logger.warning(f"[tieba] 处理评论失败: {e}")
                    continue
                    
        except Exception as e:
            utils.logger.error(f"[tieba] 获取评论失败: {e}")
        
        return comments
