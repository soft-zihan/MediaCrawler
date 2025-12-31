# -*- coding: utf-8 -*-
"""
Lite Crawler 命令行入口

使用方式：
    # 启动API服务
    python -m lite_crawler serve
    
    # 命令行搜索
    python -m lite_crawler search "python教程"
    
    # 指定平台搜索
    python -m lite_crawler search "python教程" --platforms bilibili,zhihu
"""

import asyncio
import argparse
import json
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lite_crawler.config import get_config, update_config
from lite_crawler.crawlers.factory import search, CrawlerFactory
from lite_crawler.api.server import start_server


def main():
    parser = argparse.ArgumentParser(
        description="Lite Crawler - 轻量级多平台聚合搜索爬虫",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s serve                          启动API服务
  %(prog)s serve --port 8888              指定端口启动
  %(prog)s search "python教程"            搜索所有平台
  %(prog)s search "python" -p bilibili    只搜索B站
  %(prog)s search "AI" -p bilibili,zhihu  搜索B站和知乎
  %(prog)s platforms                      查看支持的平台
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="可用命令")
    
    # serve 命令
    serve_parser = subparsers.add_parser("serve", help="启动API服务")
    serve_parser.add_argument(
        "--host", "-H",
        default="0.0.0.0",
        help="服务主机地址 (默认: 0.0.0.0)"
    )
    serve_parser.add_argument(
        "--port", "-p",
        type=int,
        default=8888,
        help="服务端口 (默认: 8888)"
    )
    
    # search 命令
    search_parser = subparsers.add_parser("search", help="命令行搜索")
    search_parser.add_argument(
        "keyword",
        help="搜索关键词"
    )
    search_parser.add_argument(
        "--platforms", "-p",
        default=None,
        help="要搜索的平台，用逗号分隔 (默认搜索所有平台)"
    )
    search_parser.add_argument(
        "--output", "-o",
        choices=["json", "markdown", "simple"],
        default="simple",
        help="输出格式 (默认: simple)"
    )
    search_parser.add_argument(
        "--save", "-s",
        default=None,
        help="保存结果到文件"
    )
    
    # platforms 命令
    platforms_parser = subparsers.add_parser("platforms", help="查看支持的平台")
    
    # config 命令
    config_parser = subparsers.add_parser("config", help="查看或修改配置")
    config_parser.add_argument(
        "--set",
        nargs=2,
        metavar=("KEY", "VALUE"),
        action="append",
        help="设置配置项"
    )
    
    args = parser.parse_args()
    
    if args.command == "serve":
        start_server(host=args.host, port=args.port)
        
    elif args.command == "search":
        asyncio.run(do_search(args))
        
    elif args.command == "platforms":
        show_platforms()
        
    elif args.command == "config":
        handle_config(args)
        
    else:
        parser.print_help()


async def do_search(args):
    """执行搜索"""
    platforms = None
    if args.platforms:
        platforms = [p.strip() for p in args.platforms.split(",")]
    
    print(f"\n🔍 正在搜索: {args.keyword}")
    if platforms:
        print(f"📱 平台: {', '.join(platforms)}")
    else:
        print("📱 平台: 所有支持的平台")
    print("-" * 50)
    
    result = await search(args.keyword, platforms)
    
    # 输出结果
    if args.output == "json":
        output = json.dumps(result.to_dict(), ensure_ascii=False, indent=2)
    elif args.output == "markdown":
        output = result.to_markdown()
    else:
        # simple 格式
        output = format_simple_output(result)
    
    print(output)
    
    # 保存结果
    if args.save:
        with open(args.save, "w", encoding="utf-8") as f:
            if args.output == "json":
                f.write(output)
            elif args.output == "markdown":
                f.write(output)
            else:
                # 默认保存为JSON
                f.write(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        print(f"\n💾 结果已保存到: {args.save}")
    
    # 输出统计
    print("-" * 50)
    print(f"✅ 搜索完成 | 耗时: {result.duration:.2f}秒 | 共 {result.get_total_count()} 条结果")
    
    if result.errors:
        print(f"⚠️ 部分平台出错: {', '.join(result.errors.keys())}")


def format_simple_output(result):
    """格式化简单输出"""
    lines = []
    
    for platform, items in result.results.items():
        lines.append(f"\n【{platform.upper()}】({len(items)}条)")
        
        for i, item in enumerate(items, 1):
            lines.append(f"\n  {i}. {item.title}")
            lines.append(f"     🔗 {item.url}")
            
            if item.content:
                content_preview = item.content[:100]
                if len(item.content) > 100:
                    content_preview += "..."
                lines.append(f"     📝 {content_preview}")
            
            stats = []
            if item.view_count > 0:
                stats.append(f"👁{item.view_count}")
            if item.like_count > 0:
                stats.append(f"👍{item.like_count}")
            if item.comment_count > 0:
                stats.append(f"💬{item.comment_count}")
            if stats:
                lines.append(f"     {' '.join(stats)}")
            
            if item.comments:
                lines.append(f"     📣 热评({len(item.comments)}条):")
                for j, comment in enumerate(item.comments[:3], 1):
                    comment_text = comment.content[:50]
                    if len(comment.content) > 50:
                        comment_text += "..."
                    lines.append(f"        {j}. {comment_text}")
    
    return "\n".join(lines)


def show_platforms():
    """显示支持的平台"""
    config = get_config()
    
    print("\n支持的平台:")
    print("-" * 50)
    
    platform_info = {
        "bilibili": ("B站", "视频", "10条评论"),
        "douyin": ("抖音", "视频", "10条评论"),
        "xiaohongshu": ("小红书", "笔记", "10条评论"),
        "weibo": ("微博", "帖子", "10条评论"),
        "zhihu": ("知乎", "回答", "20条评论"),
        "tieba": ("贴吧", "帖子", "100条评论"),
        "kuaishou": ("快手", "视频", "10条评论"),
    }
    
    for platform, (name, content_type, comments) in platform_info.items():
        aliases = [k for k, v in config.platform_aliases.items() if v == platform]
        alias_str = f" (别名: {', '.join(aliases)})" if aliases else ""
        print(f"  {platform:12} | {name:6} | {content_type:4} | {comments}{alias_str}")
    
    print("-" * 50)
    print(f"共 {len(platform_info)} 个平台")


def handle_config(args):
    """处理配置命令"""
    config = get_config()
    
    if args.set:
        updates = {}
        for key, value in args.set:
            # 类型转换
            if value.lower() in ("true", "false"):
                value = value.lower() == "true"
            elif value.isdigit():
                value = int(value)
            elif value.replace(".", "").isdigit():
                value = float(value)
            updates[key] = value
        
        update_config(**updates)
        print("配置已更新:")
        for key, value in updates.items():
            print(f"  {key} = {value}")
    else:
        print("\n当前配置:")
        print("-" * 50)
        print(f"  登录方式: {config.login_type}")
        print(f"  无头模式: {config.headless}")
        print(f"  CDP模式: {config.enable_cdp_mode}")
        print(f"  爬取间隔: {config.crawl_interval}秒")
        print(f"  最大内容数: {config.limits.max_contents}")
        print("-" * 50)


if __name__ == "__main__":
    main()
