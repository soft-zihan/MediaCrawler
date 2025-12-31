# -*- coding: utf-8 -*-
"""
Lite Crawler 基础爬虫类

提供所有平台爬虫的公共功能：
- 浏览器管理（CDP模式）
- 登录状态管理
- 统一的数据转换接口
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from playwright.async_api import BrowserContext, Page, Playwright, async_playwright

import sys
import os

# 添加项目根目录到路径，以便导入原项目模块
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from tools.cdp_browser import CDPBrowserManager
from tools import utils

from ..config import LiteCrawlerConfig, get_config
from ..models import ContentItem, CommentItem, SearchResult


class BaseLiteCrawler(ABC):
    """
    轻量级爬虫基类
    
    所有平台爬虫都继承此类，实现统一的接口
    """
    
    # 平台名称（子类必须覆盖）
    platform_name: str = ""
    
    # 平台首页URL
    index_url: str = ""
    
    def __init__(self, config: Optional[LiteCrawlerConfig] = None):
        """
        初始化爬虫
        
        Args:
            config: 配置对象，如果不提供则使用全局配置
        """
        self.config = config or get_config()
        self.browser_context: Optional[BrowserContext] = None
        self.context_page: Optional[Page] = None
        self.cdp_manager: Optional[CDPBrowserManager] = None
        self._is_initialized = False
        self._client = None  # API客户端，由子类初始化
    
    @property
    def max_contents(self) -> int:
        """获取最大内容数限制"""
        return self.config.limits.max_contents
    
    @property
    def max_comments(self) -> int:
        """获取最大评论数限制"""
        return self.config.get_comment_limit(self.platform_name)
    
    async def initialize(self, playwright: Playwright) -> bool:
        """
        初始化爬虫（启动浏览器、登录等）
        
        Args:
            playwright: Playwright实例
            
        Returns:
            是否初始化成功
        """
        if self._is_initialized:
            return True
        
        try:
            utils.logger.info(f"[{self.platform_name}] 初始化爬虫...")
            
            # 使用CDP模式启动浏览器
            if self.config.enable_cdp_mode:
                self.cdp_manager = CDPBrowserManager()
                self.browser_context = await self.cdp_manager.launch_and_connect(
                    playwright=playwright,
                    playwright_proxy=None,
                    user_agent=self._get_user_agent(),
                    headless=self.config.headless,
                )
            else:
                # 标准模式
                browser = await playwright.chromium.launch(headless=self.config.headless)
                self.browser_context = await browser.new_context(
                    user_agent=self._get_user_agent()
                )
                # 注入反检测脚本
                await self.browser_context.add_init_script(path="libs/stealth.min.js")
            
            # 创建页面并访问首页
            self.context_page = await self.browser_context.new_page()
            await self.context_page.goto(self.index_url, wait_until="domcontentloaded")
            
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
    
    async def cleanup(self):
        """清理资源"""
        try:
            if self.cdp_manager:
                await self.cdp_manager.cleanup()
            elif self.browser_context:
                await self.browser_context.close()
        except Exception as e:
            utils.logger.warning(f"[{self.platform_name}] 清理资源时出错: {e}")
        finally:
            self._is_initialized = False
    
    @abstractmethod
    async def search(self, keyword: str) -> List[ContentItem]:
        """
        搜索内容
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            内容列表（最多max_contents条）
        """
        pass
    
    @abstractmethod
    async def get_comments(self, content_id: str, **kwargs) -> List[CommentItem]:
        """
        获取内容的评论
        
        Args:
            content_id: 内容ID
            **kwargs: 额外参数（平台特定）
            
        Returns:
            评论列表（根据平台限制数量）
        """
        pass
    
    @abstractmethod
    async def _init_client(self):
        """初始化API客户端（子类实现）"""
        pass
    
    @abstractmethod
    async def _check_login(self) -> bool:
        """检查登录状态（子类实现）"""
        pass
    
    @abstractmethod
    async def _do_login(self):
        """执行登录（子类实现）"""
        pass
    
    def _get_user_agent(self) -> str:
        """获取User-Agent（子类可覆盖）"""
        return utils.get_user_agent()
    
    async def search_with_comments(self, keyword: str) -> List[ContentItem]:
        """
        搜索内容并获取评论
        
        这是主要的对外接口，会自动限制数量并获取评论
        
        Args:
            keyword: 搜索关键词
            
        Returns:
            包含评论的内容列表
        """
        # 搜索内容
        contents = await self.search(keyword)
        
        # 限制数量
        contents = contents[:self.max_contents]
        
        # 获取每个内容的评论
        for content in contents:
            try:
                # 从extra中获取内容ID
                content_id = content.extra.get("content_id", "")
                if content_id:
                    # 复制extra，移除content_id避免参数重复
                    extra_kwargs = {k: v for k, v in content.extra.items() if k != "content_id"}
                    comments = await self.get_comments(content_id, **extra_kwargs)
                    content.comments = comments[:self.max_comments]
                
                # 添加爬取间隔
                await asyncio.sleep(self.config.crawl_interval)
                
            except Exception as e:
                utils.logger.warning(f"[{self.platform_name}] 获取评论失败: {e}")
        
        return contents
    
    @staticmethod
    def format_count(count: Any) -> int:
        """
        格式化计数（处理各种格式的数字）
        
        Args:
            count: 原始计数（可能是字符串、数字等）
            
        Returns:
            整数计数
        """
        if count is None:
            return 0
        if isinstance(count, int):
            return count
        if isinstance(count, float):
            return int(count)
        if isinstance(count, str):
            count = count.strip()
            if not count:
                return 0
            # 处理"1.2万"、"1.2w"等格式
            count = count.lower().replace(",", "")
            multiplier = 1
            if "万" in count or "w" in count:
                multiplier = 10000
                count = count.replace("万", "").replace("w", "")
            elif "亿" in count:
                multiplier = 100000000
                count = count.replace("亿", "")
            try:
                return int(float(count) * multiplier)
            except ValueError:
                return 0
        return 0
    
    @staticmethod
    def clean_text(text: str) -> str:
        """
        清理文本（去除多余空白、特殊字符等）
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        if not text:
            return ""
        # 去除多余空白
        text = " ".join(text.split())
        return text.strip()
