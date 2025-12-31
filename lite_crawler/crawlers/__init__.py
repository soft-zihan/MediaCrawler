# -*- coding: utf-8 -*-
"""
Lite Crawler 爬虫模块初始化
"""

from .base import BaseLiteCrawler
from .bilibili import BilibiliLiteCrawler
from .douyin import DouyinLiteCrawler
from .xiaohongshu import XiaohongshuLiteCrawler
from .weibo import WeiboLiteCrawler
from .zhihu import ZhihuLiteCrawler
from .tieba import TiebaLiteCrawler
from .kuaishou import KuaishouLiteCrawler
from .factory import CrawlerFactory

__all__ = [
    "BaseLiteCrawler",
    "BilibiliLiteCrawler",
    "DouyinLiteCrawler",
    "XiaohongshuLiteCrawler",
    "WeiboLiteCrawler",
    "ZhihuLiteCrawler",
    "TiebaLiteCrawler",
    "KuaishouLiteCrawler",
    "CrawlerFactory",
]
