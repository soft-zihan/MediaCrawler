# -*- coding: utf-8 -*-
"""
Lite Crawler 配置文件

专为AI聚合搜索场景设计的配置，所有配置都有合理默认值
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class PlatformLimits:
    """各平台爬取限制配置"""
    # 内容数量限制（所有平台统一为8条）
    max_contents: int = 8
    
    # 评论数量限制（根据平台不同）
    bilibili_comments: int = 10      # B站：前10条评论
    douyin_comments: int = 10        # 抖音：前10条评论
    xiaohongshu_comments: int = 10   # 小红书：前10条评论
    weibo_comments: int = 10         # 微博：前10条评论
    zhihu_comments: int = 20         # 知乎：前20条评论
    tieba_comments: int = 100        # 贴吧：所有评论（上限100条，约2页）
    kuaishou_comments: int = 10      # 快手：前10条评论


@dataclass 
class LiteCrawlerConfig:
    """Lite Crawler 主配置类"""
    
    # ==================== 平台配置 ====================
    # 支持的平台列表
    supported_platforms: List[str] = field(default_factory=lambda: [
        "bilibili",   # B站
        "douyin",     # 抖音
        "xiaohongshu", # 小红书 (xhs)
        "weibo",      # 微博
        "zhihu",      # 知乎
        "tieba",      # 百度贴吧
        "kuaishou",   # 快手
    ])
    
    # 平台别名映射（用于兼容原项目的简写）
    platform_aliases: dict = field(default_factory=lambda: {
        "bili": "bilibili",
        "dy": "douyin", 
        "xhs": "xiaohongshu",
        "wb": "weibo",
        "ks": "kuaishou",
    })
    
    # ==================== 爬取限制 ====================
    limits: PlatformLimits = field(default_factory=PlatformLimits)
    
    # ==================== 浏览器配置 ====================
    # 使用CDP模式（推荐，更好的反检测能力）
    enable_cdp_mode: bool = True
    
    # CDP调试端口
    cdp_debug_port: int = 9222
    
    # 无头模式（建议关闭以获得更好的反检测效果）
    headless: bool = False
    
    # 自定义浏览器路径（留空则自动检测）
    custom_browser_path: str = ""
    
    # 浏览器启动超时（秒）
    browser_launch_timeout: int = 60
    
    # 程序结束时是否关闭浏览器
    auto_close_browser: bool = True
    
    # ==================== 登录配置 ====================
    # 登录方式: qrcode, phone, cookie
    login_type: str = "qrcode"
    
    # Cookie字符串（使用cookie登录时需要）
    cookies: str = ""
    
    # 是否保存登录状态
    save_login_state: bool = True
    
    # ==================== 网络配置 ====================
    # 是否启用代理
    enable_proxy: bool = False
    
    # 请求超时（秒）
    request_timeout: int = 30
    
    # 爬取间隔（秒），避免请求过快
    crawl_interval: float = 1.5
    
    # ==================== API服务配置 ====================
    # API服务端口
    api_port: int = 8888
    
    # API服务主机
    api_host: str = "0.0.0.0"
    
    # 允许的CORS来源
    cors_origins: List[str] = field(default_factory=lambda: ["*"])
    
    # ==================== 输出配置 ====================
    # 数据输出目录
    output_dir: str = "lite_crawler/data"
    
    # 是否启用调试日志
    debug: bool = False
    
    def normalize_platform(self, platform: str) -> str:
        """
        标准化平台名称
        
        Args:
            platform: 平台名称或别名
            
        Returns:
            标准化后的平台名称
        """
        platform = platform.lower().strip()
        return self.platform_aliases.get(platform, platform)
    
    def is_platform_supported(self, platform: str) -> bool:
        """
        检查平台是否支持
        
        Args:
            platform: 平台名称
            
        Returns:
            是否支持
        """
        normalized = self.normalize_platform(platform)
        return normalized in self.supported_platforms
    
    def get_comment_limit(self, platform: str) -> int:
        """
        获取指定平台的评论数量限制
        
        Args:
            platform: 平台名称
            
        Returns:
            评论数量限制
        """
        normalized = self.normalize_platform(platform)
        limit_map = {
            "bilibili": self.limits.bilibili_comments,
            "douyin": self.limits.douyin_comments,
            "xiaohongshu": self.limits.xiaohongshu_comments,
            "weibo": self.limits.weibo_comments,
            "zhihu": self.limits.zhihu_comments,
            "tieba": self.limits.tieba_comments,
            "kuaishou": self.limits.kuaishou_comments,
        }
        return limit_map.get(normalized, 10)


# 全局配置实例
config = LiteCrawlerConfig()


def get_config() -> LiteCrawlerConfig:
    """获取全局配置实例"""
    return config


def update_config(**kwargs) -> LiteCrawlerConfig:
    """
    更新配置
    
    Args:
        **kwargs: 配置项
        
    Returns:
        更新后的配置实例
    """
    global config
    for key, value in kwargs.items():
        if hasattr(config, key):
            setattr(config, key, value)
    return config
