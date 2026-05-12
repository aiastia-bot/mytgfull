# 🤖 Telegram AI 助理 Bot

一个功能强大的 Telegram 私聊机器人，AI 助理自动代替你回复用户消息，支持实时监控和随时接管。

## ✨ 功能特性

### 🤖 AI 自动代聊
- AI 助理自动回复所有用户消息
- 支持自定义 AI 人设（系统提示词）
- 对话上下文记忆（可设置轮数）
- 支持 OpenAI 兼容的 API（自定义 URL 和模型）

### 👁️ 实时监控
- 所有用户消息和 AI 回复都实时转发给管理员
- 查看所有用户列表和对话历史
- 查看统计数据

### 🔄 无缝接管
- 管理员可随时接管某个用户的对话
- 通过回复转发消息直接回复用户
- 一键交回 AI 助理

### 💰 捐赠功能
- Telegram 内置支付
- 多个预设金额选项
- 管理员收到捐赠通知

## 📦 快速开始

### 1. 安装依赖

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入你的配置
```

### 3. 运行

```bash
python -m bot.main
```

### 4. Docker 部署

```bash
# 配置 .env
docker compose up -d
```

## ⚙️ 配置说明

| 环境变量 | 说明 | 必填 |
|---------|------|------|
| `BOT_TOKEN` | Telegram Bot Token（@BotFather 获取） | ✅ |
| `ADMIN_ID` | 管理员的 Telegram ID | ✅ |
| `OPENAI_API_KEY` | OpenAI API Key | ✅ |
| `OPENAI_API_BASE` | OpenAI API 地址（支持兼容 API） | ❌ |
| `OPENAI_MODEL` | 使用的模型名称 | ❌ |
| `AI_SYSTEM_PROMPT` | AI 助理人设 | ❌ |
| `MAX_HISTORY_ROUNDS` | 对话记忆轮数 | ❌ |
| `PAYMENT_PROVIDER_TOKEN` | Telegram 支付 Token | ❌ |
| `DONATION_CURRENCY` | 捐赠货币 | ❌ |

## 📋 管理员命令

| 命令 | 说明 |
|------|------|
| `/users` | 查看所有用户列表 |
| `/takeover <ID>` | 接管某用户的对话 |
| `/auto <ID>` | 交回给 AI 助理 |
| `/history <ID>` | 查看用户对话历史 |
| `/setprompt <内容>` | 设置 AI 助理人设 |
| `/stats` | 查看统计数据 |

## 🔧 获取 Telegram ID

向 [@userinfobot](https://t.me/userinfobot) 发送任意消息即可获取你的 ID。

## 📄 项目结构

```
mytgfull/
├── bot/
│   ├── __init__.py
│   ├── main.py              # 入口文件
│   ├── config.py             # 配置管理
│   ├── database.py           # 数据库操作
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── private_chat.py   # 私聊 + AI 助理
│   │   ├── admin.py          # 管理员命令
│   │   └── donate.py         # 捐赠功能
│   └── utils/
│       ├── __init__.py
│       └── openai_client.py  # OpenAI 封装
├── data/                     # 数据目录
├── .env.example
├── requirements.txt
├── Dockerfile
└── docker-compose.yml