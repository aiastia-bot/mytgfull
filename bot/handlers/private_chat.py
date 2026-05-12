from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from bot.config import config
from bot.database import (
    ensure_user,
    is_takeover,
    save_message,
    get_admin_msg_user_id,
)
from bot.utils.openai_client import ask_ai

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """处理 /start 命令"""
    await ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
    )

    user_name = message.from_user.first_name or "朋友"
    await message.answer(
        f"👋 你好 {user_name}！\n\n"
        f"我是主人的私人助理 Bot。\n"
        f"你可以直接给我发消息，我会尽力帮助你。\n\n"
        f"📌 可用命令：\n"
        f"/donate - 支持我们 ❤️"
    )


@router.message(F.chat.type == "private", ~F.text.startswith("/"), F.text | F.photo | F.document | F.sticker | F.voice | F.video)
async def handle_user_message(message: Message):
    """处理用户发来的消息（非命令）"""
    # 管理员的消息由 admin.py 处理，这里跳过
    if message.from_user.id == config.ADMIN_ID:
        return

    user = message.from_user

    # 确保用户在数据库中
    await ensure_user(user.id, user.username, user.first_name, user.last_name)

    # 检查是否被管理员接管
    takeover = await is_takeover(user.id)

    # 获取消息文本内容
    content = message.text or message.caption or "[非文本消息]"

    # 保存用户消息
    await save_message(user.id, "in", content)

    # 转发给管理员
    user_info = f"👤 用户: {user.first_name}"
    if user.username:
        user_info += f" (@{user.username})"
    user_info += f" | ID: `{user.id}`"

    mode_label = "🔴 [人工接管中]" if takeover else "🤖 [AI 自动回复]"

    forward_text = f"{mode_label}\n{user_info}\n\n💬 {content}"

    try:
        admin_msg = await message.bot.send_message(
            config.ADMIN_ID,
            forward_text,
            parse_mode="Markdown",
        )
        # 记录转发消息 ID，方便管理员回复时关联
        await save_message(user.id, "in", content, admin_msg_id=admin_msg.message_id)
    except Exception as e:
        # 转发失败不影响 AI 回复
        pass

    # 如果未被接管，AI 自动回复
    if not takeover:
        # 发送"正在输入"状态
        await message.bot.send_chat_action(user.id, "typing")

        ai_reply = await ask_ai(user.id, content)

        # 保存 AI 回复
        await save_message(user.id, "out_ai", ai_reply)

        await message.answer(ai_reply)

        # 通知管理员 AI 的回复
        try:
            await message.bot.send_message(
                config.ADMIN_ID,
                f"🤖 [AI 回复给 {user.first_name}]\n\n{ai_reply}",
            )
        except Exception:
            pass