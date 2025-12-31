# -*- coding: utf-8 -*-
"""
B站轻量级爬虫

爬取规则：
- 最多8条视频
- 每个视频获取前10条评论
- 不爬取UP主个人信息
"""

import asyncio
from typing import Dict, List, Optional, Any

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools import utils
from media_platform.bilibili.client import BilibiliClient
from media_platform.bilibili.login import BilibiliLogin
from media_platform.bilibili.field import SearchOrderType, CommentOrderType

from .base import BaseLiteCrawler
from ..models import ContentItem, CommentItem, ContentType
from ..config import get_config


class BilibiliLiteCrawler(BaseLiteCrawler):
    """B站轻量级爬虫"""
    
    platform_name = "bilibili"
    index_url = "https://www.bilibili.com"
    
    def __init__(self, config=None):
        super().__init__(config)
        self.bili_client: Optional[BilibiliClient] = None
    
    def _get_user_agent(self) -> str:
        return utils.get_user_agent()
    
    async def _init_client(self):
        """初始化B站API客户端"""
        # 只获取B站域名的Cookie，避免Cookie过大导致请求失败
        bili_cookies = await self.browser_context.cookies(urls=["https://www.bilibili.com"])
        cookie_str, cookie_dict = utils.convert_cookies(bili_cookies)
        self.bili_client = BilibiliClient(
            timeout=self.config.request_timeout,
            headers={
                "User-Agent": await self.context_page.evaluate("() => navigator.userAgent"),
                "Cookie": cookie_str,
                "Origin": "https://www.bilibili.com",
                "Referer": "https://www.bilibili.com",
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
        )
    
    async def _check_login(self) -> bool:
        """检查B站登录状态"""
        try:
            return await self.bili_client.pong()
        except Exception:
            return False
    
    async def _do_login(self):
        """执行B站登录"""
        login_obj = BilibiliLogin(
            login_type=self.config.login_type,
            login_phone="",
            browser_context=self.browser_context,
            context_page=self.context_page,
            cookie_str=self.config.cookies,
        )
        await login_obj.begin()
        await self.bili_client.update_cookies(browser_context=self.browser_context)
    
    async def search(self, keyword: str) -> List[ContentItem]:
        """
        搜索B站视频
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            视频内容列表
        """
        contents = []
        
        try:
            utils.logger.info(f"[bilibili] 搜索关键词: {keyword}")
            
            # 搜索视频
            search_result = await self.bili_client.search_video_by_keyword(
                keyword=keyword,
                page=1,
                page_size=self.max_contents,  # 直接限制为8条
                order=SearchOrderType.DEFAULT,
            )
            
            video_list = search_result.get("result", [])
            
            for video in video_list[:self.max_contents]:
                try:
                    # 获取视频详情
                    aid = video.get("aid")
                    bvid = video.get("bvid", "")
                    
                    video_detail = await self.bili_client.get_video_info(aid=aid)
                    view_data = video_detail.get("View", {})
                    
                    # 构建内容项
                    content = ContentItem(
                        platform=self.platform_name,
                        content_type=ContentType.VIDEO.value,
                        title=self.clean_text(view_data.get("title", video.get("title", ""))),
                        content="",  # 视频类不需要正文
                        url=f"https://www.bilibili.com/video/{bvid or 'av' + str(aid)}",
                        publish_time=video.get("pubdate", ""),
                        like_count=self.format_count(view_data.get("stat", {}).get("like", 0)),
                        comment_count=self.format_count(view_data.get("stat", {}).get("reply", 0)),
                        share_count=self.format_count(view_data.get("stat", {}).get("share", 0)),
                        view_count=self.format_count(view_data.get("stat", {}).get("view", 0)),
                        extra={
                            "content_id": str(aid),
                            "bvid": bvid,
                            "duration": view_data.get("duration", 0),
                        }
                    )
                    contents.append(content)
                    
                    # 添加爬取间隔
                    await asyncio.sleep(self.config.crawl_interval)
                    
                except Exception as e:
                    utils.logger.warning(f"[bilibili] 处理视频失败: {e}")
                    continue
            
        except Exception as e:
            utils.logger.error(f"[bilibili] 搜索失败: {e}")
        
        return contents
    
    async def get_comments(self, content_id: str, **kwargs) -> List[CommentItem]:
        """
        获取B站视频评论
        
        Args:
            content_id: 视频aid
            
        Returns:
            评论列表（最多10条）
        """
        comments = []
        
        try:
            utils.logger.info(f"[bilibili] 获取视频 {content_id} 的评论")
            
            # 获取评论 - 使用正确的参数名和枚举值
            # CommentOrderType: DEFAULT=0(按热度), MIXED=1(热度+时间), TIME=2(按时间)
            comment_result = await self.bili_client.get_video_comments(
                video_id=content_id,
                order_mode=CommentOrderType.DEFAULT,  # 按热度排序
            )
            
            replies = comment_result.get("replies", []) or []
            
            for reply in replies[:self.max_comments]:
                try:
                    comment = CommentItem(
                        content=self.clean_text(reply.get("content", {}).get("message", "")),
                        like_count=self.format_count(reply.get("like", 0)),
                        create_time=str(reply.get("ctime", "")),
                        is_reply=False,
                    )
                    comments.append(comment)
                except Exception as e:
                    utils.logger.warning(f"[bilibili] 处理评论失败: {e}")
                    continue
                    
        except Exception as e:
            utils.logger.error(f"[bilibili] 获取评论失败: {e}")
        
        return comments
