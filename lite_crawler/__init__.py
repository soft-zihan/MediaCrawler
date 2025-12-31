# -*- coding: utf-8 -*-
"""
Lite Crawler - 轻量级多平台聚合搜索爬虫

专为AI聚合搜索场景设计的简化版爬虫，特点：
1. 只爬取前8条内容，每条内容附带链接
2. 不爬取创作者个人信息
3. 各平台评论数量有针对性限制
4. 提供统一的REST API接口

支持平台：
- B站、抖音：视频标题 + 前10条评论
- 小红书、微博：帖子标题/内容 + 前10条评论  
- 知乎：回答 + 前20条评论
- 贴吧：帖子 + 所有评论（或前2页）
"""

from .config import LiteCrawlerConfig
from .models import SearchResult, ContentItem, CommentItem
from .api import app as lite_api_app

__version__ = "1.0.0"
__all__ = [
    "LiteCrawlerConfig",
    "SearchResult", 
    "ContentItem",
    "CommentItem",
    "lite_api_app",
]
