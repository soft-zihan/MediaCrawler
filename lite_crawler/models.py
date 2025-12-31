# -*- coding: utf-8 -*-
"""
Lite Crawler 数据模型

定义统一的数据结构，适用于所有平台
专注于AI聚合搜索场景所需的核心字段
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any
from enum import Enum


class Platform(str, Enum):
    """支持的平台枚举"""
    BILIBILI = "bilibili"
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    WEIBO = "weibo"
    ZHIHU = "zhihu"
    TIEBA = "tieba"
    KUAISHOU = "kuaishou"


class ContentType(str, Enum):
    """内容类型枚举"""
    VIDEO = "video"          # 视频（B站、抖音、快手）
    NOTE = "note"            # 图文笔记（小红书）
    POST = "post"            # 帖子/微博（微博、贴吧）
    ANSWER = "answer"        # 回答（知乎）
    ARTICLE = "article"      # 文章（知乎）
    QUESTION = "question"    # 问题（知乎）


@dataclass
class CommentItem:
    """
    评论数据模型
    
    只保留核心字段，不包含用户个人信息/主页链接
    """
    # 评论内容
    content: str
    
    # 点赞数
    like_count: int = 0
    
    # 评论时间（ISO格式字符串）
    create_time: str = ""
    
    # 是否为子评论/回复
    is_reply: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "content": self.content,
            "like_count": self.like_count,
            "create_time": self.create_time,
            "is_reply": self.is_reply,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CommentItem":
        """从字典创建"""
        return cls(
            content=data.get("content", ""),
            like_count=data.get("like_count", 0),
            create_time=data.get("create_time", ""),
            is_reply=data.get("is_reply", False),
        )


@dataclass
class ContentItem:
    """
    内容数据模型
    
    统一表示各平台的内容（视频、帖子、回答等）
    包含链接，不包含创作者个人信息
    """
    # 平台
    platform: str
    
    # 内容类型
    content_type: str
    
    # 标题
    title: str
    
    # 内容正文（图文类平台）
    content: str = ""
    
    # 原始链接（重要！用于AI返回依据）
    url: str = ""
    
    # 发布时间
    publish_time: str = ""
    
    # 互动数据
    like_count: int = 0          # 点赞/赞同数
    comment_count: int = 0       # 评论数
    share_count: int = 0         # 分享/转发数
    view_count: int = 0          # 播放/阅读数
    
    # 评论列表
    comments: List[CommentItem] = field(default_factory=list)
    
    # 额外信息（平台特定字段）
    extra: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "platform": self.platform,
            "content_type": self.content_type,
            "title": self.title,
            "content": self.content,
            "url": self.url,
            "publish_time": self.publish_time,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "share_count": self.share_count,
            "view_count": self.view_count,
            "comments": [c.to_dict() for c in self.comments],
            "extra": self.extra,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContentItem":
        """从字典创建"""
        comments = [CommentItem.from_dict(c) for c in data.get("comments", [])]
        return cls(
            platform=data.get("platform", ""),
            content_type=data.get("content_type", ""),
            title=data.get("title", ""),
            content=data.get("content", ""),
            url=data.get("url", ""),
            publish_time=data.get("publish_time", ""),
            like_count=data.get("like_count", 0),
            comment_count=data.get("comment_count", 0),
            share_count=data.get("share_count", 0),
            view_count=data.get("view_count", 0),
            comments=comments,
            extra=data.get("extra", {}),
        )
    
    def to_markdown(self) -> str:
        """
        转换为Markdown格式，方便AI阅读
        """
        lines = []
        lines.append(f"### [{self.platform}] {self.title}")
        lines.append(f"**链接**: {self.url}")
        
        if self.content:
            # 截取前500字符
            content_preview = self.content[:500]
            if len(self.content) > 500:
                content_preview += "..."
            lines.append(f"\n{content_preview}")
        
        # 互动数据
        stats = []
        if self.view_count > 0:
            stats.append(f"👁 {self.view_count}")
        if self.like_count > 0:
            stats.append(f"👍 {self.like_count}")
        if self.comment_count > 0:
            stats.append(f"💬 {self.comment_count}")
        if stats:
            lines.append(f"\n{' | '.join(stats)}")
        
        # 评论
        if self.comments:
            lines.append(f"\n**热门评论** ({len(self.comments)}条):")
            for i, comment in enumerate(self.comments[:5], 1):
                comment_text = comment.content[:100]
                if len(comment.content) > 100:
                    comment_text += "..."
                lines.append(f"{i}. {comment_text}")
        
        return "\n".join(lines)


@dataclass
class SearchResult:
    """
    搜索结果数据模型
    
    包含多个平台的搜索结果
    """
    # 搜索关键词
    keyword: str
    
    # 搜索时间
    search_time: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 各平台结果
    results: Dict[str, List[ContentItem]] = field(default_factory=dict)
    
    # 搜索状态
    status: str = "success"
    
    # 错误信息（如果有）
    errors: Dict[str, str] = field(default_factory=dict)
    
    # 搜索耗时（秒）
    duration: float = 0.0
    
    def add_result(self, platform: str, items: List[ContentItem]):
        """添加平台搜索结果"""
        self.results[platform] = items
    
    def add_error(self, platform: str, error: str):
        """添加平台错误信息"""
        self.errors[platform] = error
        if self.status == "success":
            self.status = "partial"
    
    def get_all_items(self) -> List[ContentItem]:
        """获取所有平台的内容项"""
        all_items = []
        for items in self.results.values():
            all_items.extend(items)
        return all_items
    
    def get_total_count(self) -> int:
        """获取总内容数"""
        return sum(len(items) for items in self.results.values())
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "keyword": self.keyword,
            "search_time": self.search_time,
            "status": self.status,
            "duration": self.duration,
            "total_count": self.get_total_count(),
            "results": {
                platform: [item.to_dict() for item in items]
                for platform, items in self.results.items()
            },
            "errors": self.errors,
        }
    
    def to_markdown(self) -> str:
        """
        转换为Markdown格式，适合AI阅读和理解
        """
        lines = []
        lines.append(f"# 搜索结果: {self.keyword}")
        lines.append(f"*搜索时间: {self.search_time}*")
        lines.append(f"*共找到 {self.get_total_count()} 条结果*")
        lines.append("")
        
        for platform, items in self.results.items():
            lines.append(f"## {platform.upper()} ({len(items)}条)")
            lines.append("")
            for item in items:
                lines.append(item.to_markdown())
                lines.append("")
                lines.append("---")
                lines.append("")
        
        if self.errors:
            lines.append("## 错误信息")
            for platform, error in self.errors.items():
                lines.append(f"- **{platform}**: {error}")
        
        return "\n".join(lines)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SearchResult":
        """从字典创建"""
        results = {}
        for platform, items in data.get("results", {}).items():
            results[platform] = [ContentItem.from_dict(item) for item in items]
        
        return cls(
            keyword=data.get("keyword", ""),
            search_time=data.get("search_time", ""),
            status=data.get("status", "success"),
            duration=data.get("duration", 0.0),
            results=results,
            errors=data.get("errors", {}),
        )
