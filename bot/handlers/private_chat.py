from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from bot.config import config
from bot.database import (
    ensure_user,
    is_takeover,
    save_message,
    get_admin_msg_user_id,
    get_last_admin_msg_id,
)
from bot.utils.openai_client import ask_ai

router = Router()


async def forward_media_to_admin(message: Message, admin_id: int, header: str) -> Message | None:
    """将媒体消息转发给管理员，返回管理员收到的消息对象"""
    reply_to = await get_last_admin_msg_id(message.from_user.id)

    # 转发消息处理
    forward_info = ""
    if message.forward_date:
        if message.forward_from:
            forward_info = f"\n📨 转发自: {message.forward_from.first_name}"
            if message.forward_from.username:
                forward_info += f" (@{message.forward_from.username})"
            forward_info += f" | ID: {message.forward_from.id}"
        elif message.forward_sender_name:
            forward_info = f"\n📨 转发自: {message.forward_sender_name}"
        elif message.forward_from_chat:
            forward_info = f"\n📨 转发自频道: {message.forward_from_chat.title}"

    caption_text = f"{header}{forward_info}"

    try:
        if message.photo:
            caption = f"{caption_text}\n\n💬 图片" + (f": {message.caption}" if message.caption else "")
            return await message.bot.send_photo(
                admin_id, message.photo[-1].file_id,
                caption=caption[:1024],
                reply_to_message_id=reply_to,
            )
        elif message.video:
            caption = f"{caption_text}\n\n💬 视频" + (f": {message.caption}" if message.caption else "")
            return await message.bot.send_video(
                admin_id, message.video.file_id,
                caption=caption[:1024],
                reply_to_message_id=reply_to,
            )
        elif message.document:
            caption = f"{caption_text}\n\n💬 文件: {message.document.file_name or '未知'}" + (f"\n{message.caption}" if message.caption else "")
            return await message.bot.send_document(
                admin_id, message.document.file_id,
                caption=caption[:1024],
                reply_to_message_id=reply_to,
            )
        elif message.voice:
            caption = f"{caption_text}\n\n💬 语音消息"
            return await message.bot.send_voice(
                admin_id, message.voice.file_id,
                caption=caption[:1024],
                reply_to_message_id=reply_to,
            )
        elif message.sticker:
            # 贴纸没有 caption，先发贴纸再发文字说明
            sticker_msg = await message.bot.send_sticker(
                admin_id, message.sticker.file_id,
                reply_to_message_id=reply_to,
            )
            await message.bot.send_message(
                admin_id, f"{caption_text}\n\n💬 贴纸: {message.sticker.emoji or '🎭'}",
                reply_to_message_id=sticker_msg.message_id,
            )
            return sticker_msg
        elif message.animation:
            caption = f"{caption_text}\n\n💬 动图" + (f": {message.caption}" if message.caption else "")
            return await message.bot.send_animation(
                admin_id, message.animation.file_id,
                caption=caption[:1024],
                reply_to_message_id=reply_to,
            )
        elif message.video_note:
            # 视频笔记（圆形视频）
            vn_msg = await message.bot.send_video_note(
                admin_id, message.video_note.file_id,
                reply_to_message_id=reply_to,
            )
            await message.bot.send_message(
                admin_id, f"{caption_text}\n\n💬 视频笔记",
                reply_to_message_id=vn_msg.message_id,
            )
            return vn_msg
        elif message.audio:
            caption = f"{caption_text}\n\n💬 音频: {message.audio.file_name or '未知'}" + (f"\n{message.caption}" if message.caption else "")
            return await message.bot.send_audio(
                admin_id, message.audio.file_id,
                caption=caption[:1024],
                reply_to_message_id=reply_to,
            )
    except Exception:
        pass

    return None


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


@router.message(F.chat.type == "private", ~F.text.startswith("/"), F.text | F.photo | F.document | F.sticker | F.voice | F.video | F.animation | F.video_note | F.audio)
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

    # 构建管理员消息头部
    user_info = f"👤 用户: {user.first_name}"
    if user.username:
        user_info += f" (@{user.username})"
    user_info += f" | ID: `{user.id}`"

    mode_label = "🔴 [人工接管中]" if takeover else "🤖 [AI 自动回复]"
    header = f"{mode_label}\n{user_info}"

    # 转发给管理员
    last_admin_msg_id = await get_last_admin_msg_id(user.id)

    if message.text:
        # 纯文本消息
        forward_info = ""
        if message.forward_date:
            if message.forward_from:
                forward_info = f"\n📨 转发自: {message.forward_from.first_name}"
                if message.forward_from.username:
                    forward_info += f" (@{message.forward_from.username})"
                forward_info += f" | ID: {message.forward_from.id}"
            elif message.forward_sender_name:
                forward_info = f"\n📨 转发自: {message.forward_sender_name}"
            elif message.forward_from_chat:
                forward_info = f"\n📨 转发自频道: {message.forward_from_chat.title}"
            else:
                forward_info = "\n📨 转发消息"

        forward_text = f"{header}{forward_info}\n\n💬 {content}"
        try:
            admin_msg = await message.bot.send_message(
                config.ADMIN_ID,
                forward_text,
                parse_mode="Markdown",
                reply_to_message_id=last_admin_msg_id if last_admin_msg_id else None,
            )
            await save_message(user.id, "in", content, admin_msg_id=admin_msg.message_id)
        except Exception:
            pass
    else:
        # 媒体消息
        admin_msg = await forward_media_to_admin(message, config.ADMIN_ID, header)
        if admin_msg:
            await save_message(user.id, "in", content, admin_msg_id=admin_msg.message_id)

    # 如果未被接管，AI 自动回复
    if not takeover:
        # 媒体消息统一提示 AI 无法查看
        ai_content = content
        if not message.text:
            ai_content = "[用户发送了一条媒体消息，你无法查看，请告知用户你目前无法查看媒体内容，建议用文字描述]"

        # 发送"正在输入"状态
        await message.bot.send_chat_action(user.id, "typing")

        ai_reply = await ask_ai(user.id, ai_content)

        # 保存 AI 回复
        await save_message(user.id, "out_ai", ai_reply)

        await message.answer(ai_reply)

        # 通知管理员 AI 的回复（回复到用户消息，形成线程）
        try:
            current_last = await get_last_admin_msg_id(user.id)
            ai_admin_msg = await message.bot.send_message(
                config.ADMIN_ID,
                f"🤖 [AI 回复给 {user.first_name}]\n\n{ai_reply}",
                reply_to_message_id=current_last if current_last else None,
            )
            await save_message(user.id, "out_ai", ai_reply, admin_msg_id=ai_admin_msg.message_id)
        except Exception:
            pass