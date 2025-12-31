# -*- coding: utf-8 -*-
"""
抖音轻量级爬虫

爬取规则：
- 最多8条视频
- 每个视频获取前10条评论
- 不爬取创作者个人信息
"""

import asyncio
from typing import Dict, List, Optional, Any

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools import utils
from media_platform.douyin.client import DouYinClient
from media_platform.douyin.login import DouYinLogin
from media_platform.douyin.field import PublishTimeType

from .base import BaseLiteCrawler
from ..models import ContentItem, CommentItem, ContentType
from ..config import get_config


class DouyinLiteCrawler(BaseLiteCrawler):
    """抖音轻量级爬虫"""
    
    platform_name = "douyin"
    index_url = "https://www.douyin.com"
    
    def __init__(self, config=None):
        super().__init__(config)
        self.dy_client: Optional[DouYinClient] = None
    
    def _get_user_agent(self) -> str:
        # 抖音使用默认的 user agent
        return None  # 让浏览器使用自己的
    
    async def _init_client(self):
        """初始化抖音API客户端"""
        cookie_str, cookie_dict = utils.convert_cookies(
            await self.browser_context.cookies()
        )
        self.dy_client = DouYinClient(
            timeout=self.config.request_timeout,
            headers={
                "User-Agent": await self.context_page.evaluate("() => navigator.userAgent"),
                "Cookie": cookie_str,
                "Referer": "https://www.douyin.com/",
                "Origin": "https://www.douyin.com",
            },
            playwright_page=self.context_page,
            cookie_dict=cookie_dict,
        )
    
    async def _check_login(self) -> bool:
        """检查抖音登录状态"""
        try:
            return await self.dy_client.pong(browser_context=self.browser_context)
        except Exception:
            return False
    
    async def _do_login(self):
        """执行抖音登录"""
        login_obj = DouYinLogin(
            login_type=self.config.login_type,
            login_phone="",
            browser_context=self.browser_context,
            context_page=self.context_page,
            cookie_str=self.config.cookies,
        )
        await login_obj.begin()
        await self.dy_client.update_cookies(browser_context=self.browser_context)
    
    async def search(self, keyword: str) -> List[ContentItem]:
        """
        搜索抖音视频
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            视频内容列表
        """
        contents = []
        
        try:
            utils.logger.info(f"[douyin] 搜索关键词: {keyword}")
            
            # 搜索视频
            search_result = await self.dy_client.search_info_by_keyword(
                keyword=keyword,
                offset=0,
                publish_time=PublishTimeType.UNLIMITED,
            )
            
            data_list = search_result.get("data", []) or []
            
            count = 0
            for item in data_list:
                if count >= self.max_contents:
                    break
                    
                try:
                    # 获取视频信息
                    aweme_info = item.get("aweme_info") or item.get("aweme_mix_info", {}).get("mix_items", [{}])[0]
                    if not aweme_info:
                        continue
                    
                    aweme_id = aweme_info.get("aweme_id", "")
                    if not aweme_id:
                        continue
                    
                    # 构建视频URL
                    video_url = f"https://www.douyin.com/video/{aweme_id}"
                    
                    # 提取视频标题（desc字段）
                    title = self.clean_text(aweme_info.get("desc", ""))
                    
                    # 提取统计数据
                    statistics = aweme_info.get("statistics", {})
                    
                    content = ContentItem(
                        platform=self.platform_name,
                        content_type=ContentType.VIDEO.value,
                        title=title,
                        content="",
                        url=video_url,
                        publish_time=str(aweme_info.get("create_time", "")),
                        like_count=self.format_count(statistics.get("digg_count", 0)),
                        comment_count=self.format_count(statistics.get("comment_count", 0)),
                        share_count=self.format_count(statistics.get("share_count", 0)),
                        view_count=self.format_count(statistics.get("play_count", 0)),
                        extra={
                            "content_id": aweme_id,
                        }
                    )
                    contents.append(content)
                    count += 1
                    
                    # 添加爬取间隔
                    await asyncio.sleep(self.config.crawl_interval)
                    
                except Exception as e:
                    utils.logger.warning(f"[douyin] 处理视频失败: {e}")
                    continue
            
        except Exception as e:
            utils.logger.error(f"[douyin] 搜索失败: {e}")
        
        return contents
    
    async def get_comments(self, content_id: str, **kwargs) -> List[CommentItem]:
        """
        获取抖音视频评论
        
        Args:
            content_id: 视频aweme_id
            
        Returns:
            评论列表（最多10条）
        """
        comments = []
        
        try:
            utils.logger.info(f"[douyin] 获取视频 {content_id} 的评论")
            
            # 获取评论
            comment_result = await self.dy_client.get_aweme_comments(
                aweme_id=content_id,
                cursor=0,
            )
            
            comment_list = comment_result.get("comments", []) or []
            
            for comment_data in comment_list[:self.max_comments]:
                try:
                    comment = CommentItem(
                        content=self.clean_text(comment_data.get("text", "")),
                        like_count=self.format_count(comment_data.get("digg_count", 0)),
                        create_time=str(comment_data.get("create_time", "")),
                        is_reply=False,
                    )
                    comments.append(comment)
                except Exception as e:
                    utils.logger.warning(f"[douyin] 处理评论失败: {e}")
                    continue
                    
        except Exception as e:
            utils.logger.error(f"[douyin] 获取评论失败: {e}")
        
        return comments
