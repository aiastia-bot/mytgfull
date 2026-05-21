import html as html_module

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
    get_last_active_user,
)

router = Router()


def is_admin(message: Message) -> bool:
    """检查是否是管理员"""
    return message.from_user.id == config.ADMIN_ID


async def extract_user_id(message: Message) -> int | None:
    """从回复的消息或命令参数中提取用户 ID"""
    # 优先从回复的消息中提取
    if message.reply_to_message:
        reply_msg_id = message.reply_to_message.message_id
        user_id = await get_admin_msg_user_id(reply_msg_id)
        if user_id:
            return user_id

    # 其次从命令参数中提取
    if message.text:
        args = message.text.split(maxsplit=1)
    else:
        args = []
    if len(args) >= 2:
        try:
            return int(args[1].strip())
        except ValueError:
            pass

    return None


@router.message(F.chat.type == "private", Command("users"))
async def cmd_users(message: Message):
    """查看所有用户列表"""
    if not is_admin(message):
        return

    users = await get_all_users()
    if not users:
        await message.answer("📭 暂无用户")
        return

    text = "📋 <b>用户列表</b>\n\n"
    for u in users:
        takeover_mark = "🔴" if u[6] else "🤖"
        username = f"@{html_module.escape(u[1])} " if u[1] else ""
        name = html_module.escape(u[2] or u[1] or "Unknown")
        text += f'{takeover_mark} {name} {username}| <a href="tg://user?id={u[0]}">{u[0]}</a> | 末次活跃: {u[5][:16]}\n'

    await message.answer(text, parse_mode="HTML")


@router.message(F.chat.type == "private", Command("takeover"))
async def cmd_takeover(message: Message):
    """接管用户对话 - 支持回复消息或输入用户ID"""
    if not is_admin(message):
        return

    user_id = await extract_user_id(message)
    if not user_id:
        await message.answer("用法: 回复用户消息使用 /takeover，或 /takeover 用户ID")
        return

    await set_takeover(user_id, True)
    await message.answer(f'✅ 已接管用户 <a href="tg://user?id={user_id}">{user_id}</a> 的对话，现在由你亲自回复。', parse_mode="HTML")

    # 通知用户
    try:
        await message.bot.send_message(user_id, "👤 管理员已接管对话，接下来由真人回复您。")
    except Exception:
        pass


@router.message(F.chat.type == "private", Command("auto"))
async def cmd_auto(message: Message):
    """交回给 AI 自动回复 - 支持回复消息或输入用户ID"""
    if not is_admin(message):
        return

    user_id = await extract_user_id(message)
    if not user_id:
        await message.answer("用法: 回复用户消息使用 /auto，或 /auto 用户ID")
        return

    await set_takeover(user_id, False)
    await message.answer(f'✅ 用户 <a href="tg://user?id={user_id}">{user_id}</a> 的对话已交回 AI 助理。', parse_mode="HTML")

    # 通知用户
    try:
        await message.bot.send_message(user_id, "🤖 AI 助理已恢复为您服务。")
    except Exception:
        pass


@router.message(F.chat.type == "private", Command("history"))
async def cmd_history(message: Message):
    """查看用户对话历史 - 支持回复消息或输入用户ID"""
    if not is_admin(message):
        return

    user_id = await extract_user_id(message)
    if not user_id:
        await message.answer("用法: 回复用户消息使用 /history，或 /history 用户ID")
        return

    history = await get_user_history(user_id, limit=20)
    if not history:
        await message.answer("📭 暂无对话记录")
        return

    text = f'📜 <b>用户 <a href="tg://user?id={user_id}">{user_id}</a> 对话历史</b>\n\n'
    for row in history:
        direction = row[0]
        content = html_module.escape(row[1] or "")
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

    await message.answer(text, parse_mode="HTML")


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
        f"📊 <b>Bot 统计</b>\n\n"
        f"👥 用户数: {stats['user_count']}\n"
        f"💬 消息数: {stats['msg_count']}\n"
        f"💰 捐赠次数: {stats['donation_count']}\n"
        f"💰 捐赠总额: {stats['total_donated']}"
    )

    await message.answer(text, parse_mode="HTML")


async def send_admin_message_to_user(message: Message, user_id: int):
    """发送管理员消息（文本或媒体）给指定用户"""
    try:
        if message.text:
            content = message.text
            await message.bot.send_message(user_id, content)
        elif message.sticker:
            content = f"[贴纸 {message.sticker.emoji or '🎭'}]"
            await message.bot.send_sticker(user_id, message.sticker.file_id)
        elif message.photo:
            content = "[图片]" + (f": {message.caption}" if message.caption else "")
            await message.bot.send_photo(user_id, message.photo[-1].file_id, caption=message.caption)
        elif message.video:
            content = "[视频]" + (f": {message.caption}" if message.caption else "")
            await message.bot.send_video(user_id, message.video.file_id, caption=message.caption)
        elif message.document:
            content = f"[文件: {message.document.file_name or '未知'}]"
            await message.bot.send_document(user_id, message.document.file_id, caption=message.caption)
        elif message.voice:
            content = "[语音消息]"
            await message.bot.send_voice(user_id, message.voice.file_id)
        elif message.animation:
            content = "[动图]" + (f": {message.caption}" if message.caption else "")
            await message.bot.send_animation(user_id, message.animation.file_id, caption=message.caption)
        elif message.video_note:
            content = "[视频笔记]"
            await message.bot.send_video_note(user_id, message.video_note.file_id)
        elif message.audio:
            content = f"[音频: {message.audio.file_name or '未知'}]"
            await message.bot.send_audio(user_id, message.audio.file_id, caption=message.caption)
        else:
            content = "[非文本消息]"
            await message.bot.send_message(user_id, content)

        # 保存管理员回复
        await save_message(user_id, "out_admin", content)

        await message.answer(f'✅ 已发送给用户 <a href="tg://user?id={user_id}">{user_id}</a>', parse_mode="HTML")
    except Exception as e:
        await message.answer(f"❌ 发送失败: {e}")


@router.message(F.chat.type == "private", F.from_user.id == config.ADMIN_ID, F.reply_to_message)
async def handle_admin_reply(message: Message):
    """管理员通过回复转发消息来回复用户"""

    # 查找转发消息对应的用户 ID
    reply_msg_id = message.reply_to_message.message_id
    user_id = await get_admin_msg_user_id(reply_msg_id)

    if not user_id:
        await message.answer("❌ 无法找到对应用户，请使用 /takeover 用户ID 后直接发送消息。")
        return

    await send_admin_message_to_user(message, user_id)


@router.message(F.chat.type == "private", F.from_user.id == config.ADMIN_ID, ~F.text.startswith("/"))
async def handle_admin_direct_message(message: Message):
    """管理员直接发消息（不引用、非命令）→ 自动回复最后一个用户"""

    user_id = await get_last_active_user(config.ADMIN_ID)
    if not user_id:
        await message.answer("📭 暂无用户消息，无法确定回复对象。")
        return

    await send_admin_message_to_user(message, user_id)
