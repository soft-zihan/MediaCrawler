# -*- coding: utf-8 -*-
"""
小红书轻量级爬虫

爬取规则：
- 最多8条笔记
- 每条笔记获取前10条评论
- 包含笔记标题和内容
- 不爬取创作者个人信息
"""

import asyncio
from typing import Dict, List, Optional, Any

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools import utils
from media_platform.xhs.client import XiaoHongShuClient
from media_platform.xhs.login import XiaoHongShuLogin
from media_platform.xhs.field import SearchSortType
from media_platform.xhs.help import get_search_id

from .base import BaseLiteCrawler
from ..models import ContentItem, CommentItem, ContentType
from ..config import get_config


class XiaohongshuLiteCrawler(BaseLiteCrawler):
    """小红书轻量级爬虫"""
    
    platform_name = "xiaohongshu"
    index_url = "https://www.xiaohongshu.com"
    
    def __init__(self, config=None):
        super().__init__(config)
        self.xhs_client: Optional[XiaoHongShuClient] = None
    
    def _get_user_agent(self) -> str:
        return "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
    
    async def _init_client(self):
        """初始化小红书API客户端"""
        # 只获取小红书域名的Cookie，避免Cookie过大导致请求失败
        xhs_cookies = await self.browser_context.cookies(urls=["https://www.xiaohongshu.com"])
        cookie_str, cookie_dict = utils.convert_cookies(xhs_cookies)
        self.xhs_client = XiaoHongShuClient(
            timeout=self.config.request_timeout,
            headers={
                "accept": "application/json, text/plain, */*",
                "accept-language": "zh-CN,zh;q=0.9",
                "cache-control": "no-cache",
                "content-type": "application/json;charset=UTF-8",
                "origin": "https://www.xiaohongshu.com",
                "pragma": "no-cache",
                "priority": "u=1, i",
                "referer": "https://www.xiaohongshu.com/",
                "sec-ch-ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
                "sec-fetch-dest": "empty",
                "sec-fetch-mode": "cors",
                "sec-fetch-site": "same-site",
                "user-agent": await self.context_page.evaluate("() => navigator.userAgent"),
                "Cookie": cookie_str,
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
        )
    
    async def _update_client_cookies(self):
        """更新客户端Cookie（只获取小红书域名的Cookie）"""
        xhs_cookies = await self.browser_context.cookies(urls=["https://www.xiaohongshu.com"])
        cookie_str, cookie_dict = utils.convert_cookies(xhs_cookies)
        self.xhs_client.headers["Cookie"] = cookie_str
        self.xhs_client.cookie_dict = cookie_dict
        # 检查关键Cookie
        a1_value = cookie_dict.get("a1", "")
        utils.logger.info(f"[xiaohongshu] Cookie更新完成, a1={'有值' if a1_value else '无'}, Cookie数量: {len(cookie_dict)}")
    
    async def _check_login(self) -> bool:
        """检查小红书登录状态"""
        try:
            result = await self.xhs_client.pong()
            if result:
                return True
            # 检查页面上是否显示已登录状态（有用户头像等）
            try:
                # 尝试检测页面上的登录标识
                logged_in = await self.context_page.evaluate("""
                    () => {
                        // 检查是否有登录后才会显示的元素
                        const userInfo = document.querySelector('.user-info, .login-btn, [class*="avatar"]');
                        return userInfo !== null;
                    }
                """)
                if logged_in:
                    utils.logger.info("[xiaohongshu] 页面显示已登录状态，更新Cookie...")
                    await self._update_client_cookies()
                    return True
            except Exception:
                pass
            return False
        except Exception as e:
            utils.logger.warning(f"[xiaohongshu] 检查登录状态失败: {e}")
            # 尝试从页面重新获取Cookie
            try:
                await self._update_client_cookies()
                return await self.xhs_client.pong()
            except Exception:
                return False
    
    async def _do_login(self):
        """执行小红书登录"""
        login_obj = XiaoHongShuLogin(
            login_type=self.config.login_type,
            login_phone="",
            browser_context=self.browser_context,
            context_page=self.context_page,
            cookie_str=self.config.cookies,
        )
        await login_obj.begin()
        await self._update_client_cookies()
    
    async def search(self, keyword: str) -> List[ContentItem]:
        """
        搜索小红书笔记
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            笔记内容列表
        """
        contents = []
        
        try:
            utils.logger.info(f"[xiaohongshu] 搜索关键词: {keyword}")
            
            search_id = get_search_id()
            
            # 搜索笔记
            search_result = await self.xhs_client.get_note_by_keyword(
                keyword=keyword,
                search_id=search_id,
                page=1,
                sort=SearchSortType.GENERAL,
            )
            
            utils.logger.info(f"[xiaohongshu] 搜索结果: {search_result.keys() if search_result else 'None'}")
            
            items = search_result.get("items", []) or []
            utils.logger.info(f"[xiaohongshu] 找到 {len(items)} 条原始结果")
            
            count = 0
            for item in items:
                if count >= self.max_contents:
                    break
                
                # 跳过推荐查询
                if item.get("model_type") in ("rec_query", "hot_query"):
                    continue
                    
                try:
                    note_id = item.get("id", "")
                    xsec_source = item.get("xsec_source", "")
                    xsec_token = item.get("xsec_token", "")
                    
                    if not note_id:
                        continue
                    
                    # 获取笔记详情
                    try:
                        note_detail = await self.xhs_client.get_note_by_id(
                            note_id, xsec_source, xsec_token
                        )
                    except Exception:
                        # 如果API失败，尝试从HTML获取
                        note_detail = await self.xhs_client.get_note_by_id_from_html(
                            note_id, xsec_source, xsec_token, enable_cookie=True
                        )
                    
                    if not note_detail:
                        continue
                    
                    # 提取笔记信息
                    title = self.clean_text(note_detail.get("title", ""))
                    desc = self.clean_text(note_detail.get("desc", ""))
                    note_type = note_detail.get("type", "normal")
                    
                    # 构建笔记URL
                    note_url = f"https://www.xiaohongshu.com/explore/{note_id}"
                    
                    # 获取互动数据
                    interact_info = note_detail.get("interact_info", {})
                    
                    content = ContentItem(
                        platform=self.platform_name,
                        content_type=ContentType.NOTE.value,
                        title=title if title else desc[:50],  # 如果没有标题，用内容前50字
                        content=desc,
                        url=note_url,
                        publish_time=str(note_detail.get("time", "")),
                        like_count=self.format_count(interact_info.get("liked_count", 0)),
                        comment_count=self.format_count(interact_info.get("comment_count", 0)),
                        share_count=self.format_count(interact_info.get("share_count", 0)),
                        view_count=0,  # 小红书不公开显示播放量
                        extra={
                            "content_id": note_id,
                            "xsec_source": xsec_source,
                            "xsec_token": xsec_token,
                            "note_type": note_type,
                        }
                    )
                    contents.append(content)
                    count += 1
                    
                    # 添加爬取间隔
                    await asyncio.sleep(self.config.crawl_interval)
                    
                except Exception as e:
                    utils.logger.warning(f"[xiaohongshu] 处理笔记失败: {e}")
                    continue
            
        except Exception as e:
            utils.logger.error(f"[xiaohongshu] 搜索失败: {e}")
        
        return contents
    
    async def get_comments(self, content_id: str, **kwargs) -> List[CommentItem]:
        """
        获取小红书笔记评论
        
        Args:
            content_id: 笔记ID
            **kwargs: 包含 xsec_token
            
        Returns:
            评论列表（最多10条）
        """
        comments = []
        
        try:
            utils.logger.info(f"[xiaohongshu] 获取笔记 {content_id} 的评论")
            
            xsec_token = kwargs.get("xsec_token", "")
            
            # 获取评论 - 使用正确的方法名和参数
            comment_result = await self.xhs_client.get_note_comments(
                note_id=content_id,
                xsec_token=xsec_token,
                cursor="",
            )
            
            comment_list = comment_result.get("comments", []) or []
            
            for comment_data in comment_list[:self.max_comments]:
                try:
                    comment = CommentItem(
                        content=self.clean_text(comment_data.get("content", "")),
                        like_count=self.format_count(comment_data.get("like_count", 0)),
                        create_time=str(comment_data.get("create_time", "")),
                        is_reply=False,
                    )
                    comments.append(comment)
                except Exception as e:
                    utils.logger.warning(f"[xiaohongshu] 处理评论失败: {e}")
                    continue
                    
        except Exception as e:
            utils.logger.error(f"[xiaohongshu] 获取评论失败: {e}")
        
        return comments
