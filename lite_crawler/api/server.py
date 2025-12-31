# -*- coding: utf-8 -*-
"""
Lite Crawler REST API 服务

提供统一的HTTP接口，供手机/其他设备调用
"""

import asyncio
from typing import List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ..config import get_config, update_config, LiteCrawlerConfig
from ..models import SearchResult
from ..crawlers.factory import get_factory, search, CrawlerFactory


# ==================== Pydantic模型 ====================

class SearchRequest(BaseModel):
    """搜索请求"""
    keyword: str = Field(..., description="搜索关键词", min_length=1, max_length=100)
    platforms: Optional[List[str]] = Field(
        default=None,
        description="要搜索的平台列表，不指定则搜索所有平台"
    )


class SearchResponse(BaseModel):
    """搜索响应"""
    success: bool = True
    message: str = "搜索完成"
    data: dict = Field(default_factory=dict)


class ConfigRequest(BaseModel):
    """配置更新请求"""
    login_type: Optional[str] = Field(default=None, description="登录方式: qrcode, phone, cookie")
    headless: Optional[bool] = Field(default=None, description="是否使用无头浏览器")
    crawl_interval: Optional[float] = Field(default=None, description="爬取间隔（秒）")
    enable_cdp_mode: Optional[bool] = Field(default=None, description="是否启用CDP模式")


class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str = "ok"
    version: str = "1.0.0"
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class PlatformsResponse(BaseModel):
    """平台列表响应"""
    platforms: List[str]
    aliases: dict


# ==================== FastAPI应用 ====================

app = FastAPI(
    title="Lite Crawler API",
    description="""
# 轻量级多平台聚合搜索爬虫 API

专为AI聚合搜索场景设计，支持在多个平台同时搜索并返回结构化结果。

## 支持的平台

| 平台 | 代号 | 内容类型 | 评论数量 |
|------|------|---------|---------|
| B站 | bilibili | 视频 | 10条 |
| 抖音 | douyin | 视频 | 10条 |
| 小红书 | xiaohongshu/xhs | 笔记 | 10条 |
| 微博 | weibo/wb | 帖子 | 10条 |
| 知乎 | zhihu | 回答 | 20条 |
| 贴吧 | tieba | 帖子 | 100条(约2页) |
| 快手 | kuaishou/ks | 视频 | 10条 |

## 使用方式

1. 调用 `/api/search` 接口进行搜索
2. 返回的结果包含各平台的内容和评论
3. 每条内容都附带原始链接，方便引用

## 注意事项

- 首次使用需要扫码登录各平台
- 建议使用CDP模式以获得更好的反检测效果
- 请合理控制请求频率
""",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS配置
config = get_config()
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== API端点 ====================

@app.get("/", response_model=HealthResponse)
async def root():
    """API根路径，返回服务状态"""
    return HealthResponse()


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse()


@app.get("/api/platforms", response_model=PlatformsResponse)
async def get_platforms():
    """获取支持的平台列表"""
    config = get_config()
    return PlatformsResponse(
        platforms=CrawlerFactory.get_supported_platforms(),
        aliases=config.platform_aliases,
    )


@app.post("/api/search", response_model=SearchResponse)
async def api_search(request: SearchRequest):
    """
    多平台聚合搜索
    
    在指定平台（或所有平台）搜索关键词，返回内容和评论。
    
    - **keyword**: 搜索关键词
    - **platforms**: 要搜索的平台列表（可选，不指定则搜索所有平台）
    
    返回结果包含：
    - 各平台的搜索结果
    - 每条内容的标题、正文、链接、互动数据
    - 每条内容的热门评论
    """
    try:
        # 执行搜索
        result: SearchResult = await search(
            keyword=request.keyword,
            platforms=request.platforms,
        )
        
        return SearchResponse(
            success=result.status != "failed",
            message=f"搜索完成，共找到 {result.get_total_count()} 条结果",
            data=result.to_dict(),
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search", response_model=SearchResponse)
async def api_search_get(
    keyword: str = Query(..., description="搜索关键词", min_length=1, max_length=100),
    platforms: Optional[str] = Query(default=None, description="平台列表，用逗号分隔"),
):
    """
    多平台聚合搜索（GET方式）
    
    与POST方式功能相同，方便在浏览器中直接调用。
    
    示例：
    - `/api/search?keyword=python`
    - `/api/search?keyword=python&platforms=bilibili,zhihu`
    """
    platform_list = None
    if platforms:
        platform_list = [p.strip() for p in platforms.split(",")]
    
    request = SearchRequest(keyword=keyword, platforms=platform_list)
    return await api_search(request)


@app.get("/api/search/markdown")
async def api_search_markdown(
    keyword: str = Query(..., description="搜索关键词"),
    platforms: Optional[str] = Query(default=None, description="平台列表，用逗号分隔"),
):
    """
    多平台聚合搜索（返回Markdown格式）
    
    适合AI直接阅读的格式。
    """
    platform_list = None
    if platforms:
        platform_list = [p.strip() for p in platforms.split(",")]
    
    try:
        result: SearchResult = await search(
            keyword=keyword,
            platforms=platform_list,
        )
        
        return JSONResponse(
            content={
                "success": result.status != "failed",
                "markdown": result.to_markdown(),
            }
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
async def get_current_config():
    """获取当前配置"""
    config = get_config()
    return {
        "login_type": config.login_type,
        "headless": config.headless,
        "enable_cdp_mode": config.enable_cdp_mode,
        "crawl_interval": config.crawl_interval,
        "max_contents": config.limits.max_contents,
        "comment_limits": {
            "bilibili": config.limits.bilibili_comments,
            "douyin": config.limits.douyin_comments,
            "xiaohongshu": config.limits.xiaohongshu_comments,
            "weibo": config.limits.weibo_comments,
            "zhihu": config.limits.zhihu_comments,
            "tieba": config.limits.tieba_comments,
            "kuaishou": config.limits.kuaishou_comments,
        }
    }


@app.post("/api/config")
async def update_current_config(request: ConfigRequest):
    """更新配置"""
    updates = {}
    if request.login_type is not None:
        updates["login_type"] = request.login_type
    if request.headless is not None:
        updates["headless"] = request.headless
    if request.crawl_interval is not None:
        updates["crawl_interval"] = request.crawl_interval
    if request.enable_cdp_mode is not None:
        updates["enable_cdp_mode"] = request.enable_cdp_mode
    
    if updates:
        update_config(**updates)
    
    return {"success": True, "message": "配置已更新", "updated": updates}


# ==================== 启动函数 ====================

def start_server(host: str = None, port: int = None):
    """
    启动API服务
    
    Args:
        host: 服务主机地址
        port: 服务端口
    """
    import uvicorn
    
    config = get_config()
    host = host or config.api_host
    port = port or config.api_port
    
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║                  Lite Crawler API Server                     ║
╠══════════════════════════════════════════════════════════════╣
║  服务地址: http://{host}:{port}                              
║  API文档:  http://{host}:{port}/docs                         
║  健康检查: http://{host}:{port}/api/health                   
╠══════════════════════════════════════════════════════════════╣
║  使用示例:                                                    
║  GET  /api/search?keyword=python                             
║  POST /api/search  {{"keyword": "python"}}                    
╚══════════════════════════════════════════════════════════════╝
    """)
    
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_server()
