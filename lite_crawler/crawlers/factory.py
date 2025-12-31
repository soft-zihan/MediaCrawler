# -*- coding: utf-8 -*-
"""
爬虫工厂

负责创建和管理各平台爬虫实例
"""

from typing import Dict, List, Optional, Type
from playwright.async_api import Playwright, async_playwright

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools import utils

from .base import BaseLiteCrawler
from .bilibili import BilibiliLiteCrawler
from .douyin import DouyinLiteCrawler
from .xiaohongshu import XiaohongshuLiteCrawler
from .weibo import WeiboLiteCrawler
from .zhihu import ZhihuLiteCrawler
from .tieba import TiebaLiteCrawler
from .kuaishou import KuaishouLiteCrawler
from ..config import LiteCrawlerConfig, get_config
from ..models import SearchResult, ContentItem


class CrawlerFactory:
    """
    爬虫工厂
    
    管理各平台爬虫的创建、初始化和生命周期
    """
    
    # 平台到爬虫类的映射
    CRAWLERS: Dict[str, Type[BaseLiteCrawler]] = {
        "bilibili": BilibiliLiteCrawler,
        "douyin": DouyinLiteCrawler,
        "xiaohongshu": XiaohongshuLiteCrawler,
        "weibo": WeiboLiteCrawler,
        "zhihu": ZhihuLiteCrawler,
        "tieba": TiebaLiteCrawler,
        "kuaishou": KuaishouLiteCrawler,
    }
    
    def __init__(self, config: Optional[LiteCrawlerConfig] = None):
        """
        初始化工厂
        
        Args:
            config: 配置对象
        """
        self.config = config or get_config()
        self._crawlers: Dict[str, BaseLiteCrawler] = {}
        self._playwright: Optional[Playwright] = None
        self._is_initialized = False
    
    def get_crawler(self, platform: str) -> Optional[BaseLiteCrawler]:
        """
        获取指定平台的爬虫实例
        
        Args:
            platform: 平台名称
            
        Returns:
            爬虫实例，如果平台不支持则返回None
        """
        platform = self.config.normalize_platform(platform)
        
        if platform not in self.CRAWLERS:
            utils.logger.error(f"不支持的平台: {platform}")
            return None
        
        if platform not in self._crawlers:
            crawler_class = self.CRAWLERS[platform]
            self._crawlers[platform] = crawler_class(self.config)
        
        return self._crawlers[platform]
    
    async def initialize_crawler(self, platform: str, playwright: Playwright) -> bool:
        """
        初始化指定平台的爬虫
        
        Args:
            platform: 平台名称
            playwright: Playwright实例
            
        Returns:
            是否初始化成功
        """
        crawler = self.get_crawler(platform)
        if not crawler:
            return False
        
        return await crawler.initialize(playwright)
    
    async def search_platform(
        self,
        platform: str,
        keyword: str,
        playwright: Playwright
    ) -> List[ContentItem]:
        """
        在指定平台搜索
        
        Args:
            platform: 平台名称
            keyword: 搜索关键词
            playwright: Playwright实例
            
        Returns:
            搜索结果列表
        """
        platform = self.config.normalize_platform(platform)
        
        # 确保爬虫已初始化
        if not await self.initialize_crawler(platform, playwright):
            utils.logger.error(f"[{platform}] 初始化失败")
            return []
        
        crawler = self.get_crawler(platform)
        if not crawler:
            return []
        
        # 执行搜索（包含评论）
        return await crawler.search_with_comments(keyword)
    
    async def search_all_platforms(
        self,
        keyword: str,
        platforms: Optional[List[str]] = None,
    ) -> SearchResult:
        """
        在所有（或指定）平台搜索
        
        这是主要的对外接口
        
        Args:
            keyword: 搜索关键词
            platforms: 要搜索的平台列表，默认搜索所有支持的平台
            
        Returns:
            聚合搜索结果
        """
        import time
        start_time = time.time()
        
        result = SearchResult(keyword=keyword)
        
        # 确定要搜索的平台
        if platforms is None:
            platforms = self.config.supported_platforms
        else:
            platforms = [self.config.normalize_platform(p) for p in platforms]
        
        async with async_playwright() as playwright:
            self._playwright = playwright
            
            for platform in platforms:
                try:
                    utils.logger.info(f"[CrawlerFactory] 开始搜索 {platform}...")
                    
                    contents = await self.search_platform(platform, keyword, playwright)
                    
                    if contents:
                        result.add_result(platform, contents)
                        utils.logger.info(f"[CrawlerFactory] {platform} 找到 {len(contents)} 条结果")
                    else:
                        utils.logger.info(f"[CrawlerFactory] {platform} 无结果")
                        
                except Exception as e:
                    error_msg = str(e)
                    utils.logger.error(f"[CrawlerFactory] {platform} 搜索失败: {error_msg}")
                    result.add_error(platform, error_msg)
            
            # 清理所有爬虫
            await self.cleanup_all()
        
        result.duration = time.time() - start_time
        
        if not result.results and result.errors:
            result.status = "failed"
        
        return result
    
    async def cleanup_crawler(self, platform: str):
        """
        清理指定平台的爬虫
        
        Args:
            platform: 平台名称
        """
        platform = self.config.normalize_platform(platform)
        
        if platform in self._crawlers:
            try:
                await self._crawlers[platform].cleanup()
            except Exception as e:
                utils.logger.warning(f"[{platform}] 清理失败: {e}")
            finally:
                del self._crawlers[platform]
    
    async def cleanup_all(self):
        """清理所有爬虫"""
        for platform in list(self._crawlers.keys()):
            await self.cleanup_crawler(platform)
        
        self._crawlers.clear()
        self._is_initialized = False
    
    @classmethod
    def get_supported_platforms(cls) -> List[str]:
        """获取支持的平台列表"""
        return list(cls.CRAWLERS.keys())


# 全局工厂实例
_factory: Optional[CrawlerFactory] = None


def get_factory() -> CrawlerFactory:
    """获取全局工厂实例"""
    global _factory
    if _factory is None:
        _factory = CrawlerFactory()
    return _factory


async def search(
    keyword: str,
    platforms: Optional[List[str]] = None,
) -> SearchResult:
    """
    便捷搜索函数
    
    Args:
        keyword: 搜索关键词
        platforms: 要搜索的平台列表
        
    Returns:
        搜索结果
    """
    factory = get_factory()
    return await factory.search_all_platforms(keyword, platforms)
