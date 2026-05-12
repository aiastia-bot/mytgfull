import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

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

    # 注册路由
    dp.include_router(private_chat.router)
    dp.include_router(admin.router)
    dp.include_router(donate.router)

    # 启动 Bot
    logging.info("🤖 Bot 启动中...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    asyncio.run(main())