# Lite Crawler - 轻量级多平台聚合搜索爬虫

专为 **AI 聚合搜索场景** 设计的简化版爬虫，基于 [MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) 项目。

> ⚠️ **免责声明**：本项目仅供学习和研究使用，请遵守相关法律法规和平台服务条款。

## ✨ 特点

- 🎯 **专注聚合搜索**: 只爬取前 8 条内容，每条内容附带链接
- 📝 **精简数据**: 不爬取创作者个人信息、主页
- 💬 **差异化评论**: 各平台评论数量有针对性限制
- 🌐 **统一 API**: 提供 REST API 接口，支持多设备调用
- 🛡️ **CDP 模式**: 默认使用 CDP 模式，更好的反检测能力

## 📊 爬取规则

| 平台   | 内容类型      | 内容数量 | 评论数量 | 状态 |
| ------ | ------------- | -------- | -------- | ---- |
| B站    | 视频标题      | 8条      | 10条     | ✅ 已测试 |
| 抖音   | 视频标题      | 8条      | 10条     | ✅ 已测试 |
| 小红书 | 帖子标题+内容 | 8条      | 10条     | ✅ 已测试 |
| 知乎   | 回答内容      | 8条      | 20条     | ✅ 已测试 |
| 贴吧   | 帖子内容      | 8条      | 2页      | ✅ 已测试 |
| 微博   | 帖子标题+内容 | 8条      | 10条     | 🚧 开发中 |
| 快手   | 视频标题      | 8条      | 10条     | 🚧 开发中 |

## 🚀 快速开始

### 前置条件

确保已完成 MediaCrawler 主项目的环境配置：

```bash
# 安装依赖
uv sync
# 或
pip install -r requirements.txt

# 安装浏览器驱动
playwright install
```

### 1. 命令行搜索

```bash
# 搜索指定平台
python -m lite_crawler search "Python教程" -p xhs

# 搜索多个平台
python -m lite_crawler search "Python教程" -p bilibili,zhihu,xhs

# 输出格式选项: simple(默认) / json / markdown
python -m lite_crawler search "Python教程" -p xhs -o json

# 保存结果到文件
python -m lite_crawler search "Python教程" -p xhs -s result.json
```

### 2. 启动 API 服务

```bash
# 默认端口 8888
python -m lite_crawler serve

# 指定端口
python -m lite_crawler serve --port 9000
```

### 3. 调用 API

```bash
# GET 请求
curl "http://localhost:8888/api/search?keyword=python&platforms=bilibili,zhihu"

# POST 请求
curl -X POST "http://localhost:8888/api/search" \
     -H "Content-Type: application/json" \
     -d '{"keyword": "python", "platforms": ["bilibili", "zhihu"]}'

# 获取 Markdown 格式（适合 AI 输入）
curl "http://localhost:8888/api/search/markdown?keyword=python"
```

## 📡 API 文档

启动服务后访问: `http://localhost:8888/docs`

### 主要端点

| 端点                     | 方法     | 描述                     |
| ------------------------ | -------- | ------------------------ |
| `/api/search`          | GET/POST | 多平台聚合搜索           |
| `/api/search/markdown` | GET      | 搜索并返回 Markdown 格式 |
| `/api/platforms`       | GET      | 获取支持的平台列表       |
| `/api/config`          | GET/POST | 查看/修改配置            |
| `/api/health`          | GET      | 健康检查                 |

### 返回数据示例

```json
{
  "success": true,
  "message": "搜索完成，共找到 24 条结果",
  "data": {
    "keyword": "python",
    "search_time": "2024-12-30T10:00:00",
    "status": "success",
    "duration": 45.2,
    "total_count": 24,
    "results": {
      "bilibili": [
        {
          "platform": "bilibili",
          "content_type": "video",
          "title": "Python从入门到精通",
          "url": "https://www.bilibili.com/video/BV...",
          "like_count": 12345,
          "comment_count": 678,
          "view_count": 100000,
          "comments": [
            {
              "content": "讲得很好！",
              "like_count": 100,
              "create_time": "2024-12-29"
            }
          ]
        }
      ]
    }
  }
}
```

## ⚙️ 配置说明

配置文件: `lite_crawler/config.py`

```python
# 主要配置项
enable_cdp_mode = True      # 使用 CDP 模式（推荐）
headless = False            # 是否无头浏览器
login_type = "qrcode"       # 登录方式
crawl_interval = 1.5        # 爬取间隔（秒）
api_port = 8888             # API 端口

# 各平台评论限制
bilibili_comments = 10
douyin_comments = 10
xiaohongshu_comments = 10
weibo_comments = 10
zhihu_comments = 20         # 知乎 20 条
tieba_comments = 100        # 贴吧约 100 条
kuaishou_comments = 10
```

## 🤖 与 AI 集成

### 使用场景

1. 用户提问: "Python怎么学？"
2. 调用 API 搜索多个平台
3. AI 读取搜索结果
4. AI 综合回答并附上来源链接

### Markdown 格式输出

```bash
curl "http://localhost:8888/api/search/markdown?keyword=python"
```

返回的 Markdown 格式适合直接作为 AI 的上下文输入。

## ⚠️ 注意事项

1. **首次使用**: 需要扫码登录各平台
2. **请求频率**: 请合理控制，建议间隔 1.5 秒以上
3. **反爬检测**: 使用 CDP 模式可降低被检测风险
4. **账号安全**: 建议使用小号登录
5. **法律合规**: 仅供学习研究使用

## 📁 文件结构

```
lite_crawler/
├── __init__.py          # 模块初始化
├── __main__.py          # 命令行入口
├── config.py            # 配置文件
├── models.py            # 数据模型
├── api/
│   ├── __init__.py
│   └── server.py        # FastAPI 服务
└── crawlers/
    ├── __init__.py
    ├── base.py          # 爬虫基类
    ├── factory.py       # 爬虫工厂
    ├── bilibili.py      # B站爬虫 ✅
    ├── douyin.py        # 抖音爬虫 ✅
    ├── xiaohongshu.py   # 小红书爬虫 ✅
    ├── zhihu.py         # 知乎爬虫 ✅
    ├── tieba.py         # 贴吧爬虫 ✅
    ├── weibo.py         # 微博爬虫 🚧
    └── kuaishou.py      # 快手爬虫 🚧
```

## 🔧 开发说明

### 设计原则

1. **不修改原文件** - 所有代码都在 `lite_crawler` 目录下，方便与上游同步
2. **复用原有逻辑** - 导入并使用原项目的 client 类
3. **统一数据模型** - 使用 `ContentItem` 和 `CommentItem` 标准化输出
4. **灵活的参数传递** - 通过 `extra` 字典在不同阶段传递平台特定参数

## 📜 许可证

本项目遵循 MediaCrawler 项目的许可证条款，仅供学习和研究使用。
