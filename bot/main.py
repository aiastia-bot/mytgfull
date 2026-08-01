import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeAllPrivateChats, BotCommandScopeChat

from bot.config import config
from bot.database import init_db
from bot.handlers import private_chat, admin, donate


async def main():
    # 验证配置
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        print("❌ 请在 .env 文件中设置 BOT_TOKEN")
        sys.exit(1)

    if not config.ADMIN_ID or config.ADMIN_ID == 0:
        print("❌ 请在 .env 文件中设置 ADMIN_ID")
        sys.exit(1)

    # 初始化数据库
    await init_db()
    logging.info("✅ 数据库初始化完成")

    # 创建 Bot
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    # 创建 Dispatcher
    dp = Dispatcher()

    # 处理未匹配的更新（避免日志刷屏）
    @dp.update()
    async def handle_unhandled_update(update):
        pass

    # 注册路由（命令优先，通用消息最后）
    dp.include_router(donate.router)
    dp.include_router(admin.router)
    dp.include_router(private_chat.router)

    # 注册命令菜单
    # 普通用户命令
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="开始使用"),
            BotCommand(command="donate", description="支持我们 ❤️"),
        ],
        scope=BotCommandScopeAllPrivateChats(),
    )

    # 管理员命令
    try:
        await bot.set_my_commands(
            [
                BotCommand(command="start", description="开始使用"),
                BotCommand(command="donate", description="支持我们 ❤️"),
                BotCommand(command="users", description="查看用户列表"),
                BotCommand(command="takeover", description="接管用户对话"),
                BotCommand(command="auto", description="交回 AI 助理"),
                BotCommand(command="history", description="查看对话历史"),
                BotCommand(command="setprompt", description="设置 AI 人设"),
                BotCommand(command="stats", description="查看统计"),
                BotCommand(command="unlock", description="手动解锁用户"),
                BotCommand(command="lock", description="撤销手动解锁"),
                BotCommand(command="ban", description="封禁用户"),
                BotCommand(command="unban", description="解封用户"),
            ],
            scope=BotCommandScopeChat(chat_id=config.ADMIN_ID),
        )
    except Exception as e:
        logging.warning(f"注册管理员命令失败: {e}")

    # 启动 Bot
    logging.info("🤖 Bot 启动中...")

    # 通知管理员 Bot 已上线
    try:
        await bot.send_message(
            config.ADMIN_ID,
            "✅ Bot 已上线！\n\n"
            "如果有用户在离线期间发送了消息，系统会自动处理（Telegram 最多缓存24小时内的消息）。",
        )
    except Exception as e:
        logging.warning(f"发送启动通知失败: {e}")

    # drop_pending_updates=False: 不丢弃离线期间的用户消息
    await dp.start_polling(bot, drop_pending_updates=False)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())