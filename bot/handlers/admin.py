from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command
from bot.config import config
from bot.database import (
    get_all_users,
    get_user_history,
    set_takeover,
    is_takeover,
    get_stats,
    get_system_prompt,
    set_system_prompt,
    save_message,
    get_admin_msg_user_id,
)

router = Router()


def is_admin(message: Message) -> bool:
    """检查是否是管理员"""
    return message.from_user.id == config.ADMIN_ID


@router.message(F.chat.type == "private", Command("users"))
async def cmd_users(message: Message):
    """查看所有用户列表"""
    if not is_admin(message):
        return

    users = await get_all_users()
    if not users:
        await message.answer("📭 暂无用户")
        return

    text = "📋 **用户列表**\n\n"
    for u in users:
        takeover_mark = "🔴" if u[6] else "🤖"
        username = f"@{u[1]} " if u[1] else ""
        name = u[2] or u[1] or "Unknown"
        text += f"{takeover_mark} {name} {username}| `{u[0]}` | 末次活跃: {u[5][:16]}\n"

    await message.answer(text, parse_mode="Markdown")


@router.message(F.chat.type == "private", Command("takeover"))
async def cmd_takeover(message: Message):
    """接管用户对话"""
    if not is_admin(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("用法: /takeover 用户ID")
        return

    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ 无效的用户 ID")
        return

    await set_takeover(user_id, True)
    await message.answer(f"✅ 已接管用户 `{user_id}` 的对话，现在由你亲自回复。", parse_mode="Markdown")

    # 通知用户
    try:
        await message.bot.send_message(user_id, "👤 管理员已接管对话，接下来由真人回复您。")
    except Exception:
        pass


@router.message(F.chat.type == "private", Command("auto"))
async def cmd_auto(message: Message):
    """交回给 AI 自动回复"""
    if not is_admin(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("用法: /auto 用户ID")
        return

    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ 无效的用户 ID")
        return

    await set_takeover(user_id, False)
    await message.answer(f"✅ 用户 `{user_id}` 的对话已交回 AI 助理。", parse_mode="Markdown")

    # 通知用户
    try:
        await message.bot.send_message(user_id, "🤖 AI 助理已恢复为您服务。")
    except Exception:
        pass


@router.message(F.chat.type == "private", Command("history"))
async def cmd_history(message: Message):
    """查看用户对话历史"""
    if not is_admin(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("用法: /history 用户ID")
        return

    try:
        user_id = int(args[1].strip())
    except ValueError:
        await message.answer("❌ 无效的用户 ID")
        return

    history = await get_user_history(user_id, limit=20)
    if not history:
        await message.answer("📭 暂无对话记录")
        return

    text = f"📜 **用户 `{user_id}` 对话历史**\n\n"
    for row in history:
        direction = row[0]
        content = row[1]
        time = row[2][:16] if row[2] else ""

        if direction == "in":
            text += f"📥 [{time}] {content[:200]}\n"
        elif direction == "out_ai":
            text += f"🤖 [{time}] {content[:200]}\n"
        elif direction == "out_admin":
            text += f"👤 [{time}] {content[:200]}\n"
        text += "\n"

    # 如果太长，截断
    if len(text) > 4000:
        text = text[:4000] + "\n\n... (已截断)"

    await message.answer(text, parse_mode="Markdown")


@router.message(F.chat.type == "private", Command("setprompt"))
async def cmd_setprompt(message: Message):
    """设置 AI 系统提示词"""
    if not is_admin(message):
        return

    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        # 显示当前提示词
        current = await get_system_prompt()
        await message.answer(f"当前 AI 提示词：\n\n{current}\n\n修改: /setprompt 新提示词")
        return

    new_prompt = args[1].strip()
    await set_system_prompt(new_prompt)
    await message.answer(f"✅ AI 提示词已更新为：\n\n{new_prompt}")


@router.message(F.chat.type == "private", Command("stats"))
async def cmd_stats(message: Message):
    """查看统计信息"""
    if not is_admin(message):
        return

    stats = await get_stats()
    text = (
        f"📊 **Bot 统计**\n\n"
        f"👥 用户数: {stats['user_count']}\n"
        f"💬 消息数: {stats['msg_count']}\n"
        f"💰 捐赠次数: {stats['donation_count']}\n"
        f"💰 捐赠总额: {stats['total_donated']}"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(F.chat.type == "private", F.reply_to_message)
async def handle_admin_reply(message: Message):
    """管理员通过回复转发消息来回复用户"""
    if not is_admin(message):
        return
    if not message.reply_to_message:
        return

    # 查找转发消息对应的用户 ID
    reply_msg_id = message.reply_to_message.message_id
    user_id = await get_admin_msg_user_id(reply_msg_id)

    if not user_id:
        await message.answer("❌ 无法找到对应用户，请使用 /takeover 用户ID 后直接发送消息。")
        return

    content = message.text or "[非文本消息]"

    # 保存管理员回复
    await save_message(user_id, "out_admin", content)

    # 发送给用户
    try:
        await message.bot.send_message(user_id, content)
        await message.answer(f"✅ 已发送给用户 `{user_id}`", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ 发送失败: {e}")