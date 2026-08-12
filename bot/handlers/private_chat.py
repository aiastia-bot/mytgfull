import asyncio
import html as html_module

from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from bot.config import config
from bot.database import (
    ensure_user,
    is_takeover,
    save_message,
    update_message_admin_id,
    get_admin_msg_user_id,
    get_last_admin_msg_id,
    is_user_unlocked,
    get_user_total_donated,
    is_user_banned,
)
from bot.utils.openai_client import ask_ai
from bot.utils.sensitive_filter import check_sensitive

router = Router()


BANNED_NOTICE = "🚫 你已被封禁，无法使用本 Bot。如有疑问请联系管理员。"


def _need_donation_unlock() -> bool:
    """是否启用捐赠门槛"""
    return getattr(config, "DONATION_REQUIRED", False)


async def _user_can_use(user_id: int) -> bool:
    """用户是否可以使用 Bot（管理员或已解锁）"""
    if user_id == config.ADMIN_ID:
        return True
    if not _need_donation_unlock():
        return True
    return await is_user_unlocked(user_id)


async def _donation_block_notice(user_id: int) -> str:
    """未解锁时给用户的提示文案"""
    donated = await get_user_total_donated(user_id)
    need = int(config.DONATION_MIN_AMOUNT - donated) if donated < config.DONATION_MIN_AMOUNT else 0
    progress = f"\n\n📊 当前进度: ⭐{int(donated)} / ⭐{int(config.DONATION_MIN_AMOUNT)}"
    if need > 0:
        progress += f"（还差 ⭐{need}）"
    return (
        "🔒 <b>需要先支持一下才能使用</b>\n\n"
        f"本 Bot 需累计捐赠 ⭐{int(config.DONATION_MIN_AMOUNT)} Telegram Stars 后解锁使用。\n"
        "发送 /donate 选择金额完成支持，即可永久解锁。\n\n"
        "⚠️ 注意：本 Bot 不是解码 Bot！是私聊 Bot。\n"
        f"{progress}"
    )


async def _delete_after(msg: Message, seconds: int):
    """延迟删除消息"""
    await asyncio.sleep(seconds)
    try:
        await msg.delete()
    except Exception:
        pass


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

    # 封禁检查（最高优先级，封禁用户禁止一切交互）
    if message.from_user.id != config.ADMIN_ID and await is_user_banned(message.from_user.id):
        await message.answer(BANNED_NOTICE)
        return

    user_name = message.from_user.first_name or "朋友"

    # 已解锁（或未开启门槛）
    if await _user_can_use(message.from_user.id):
        await message.answer(
            f"👋 你好 {user_name}！\n\n"
            f"我是主人的私人助理 Bot。\n"
            f"你可以直接给我发消息，我会尽力帮助你。\n\n"
            f"📌 可用命令：\n"
            f"/donate - 支持我们 ❤️"
        )
        return

    # 未解锁
    await message.answer(await _donation_block_notice(message.from_user.id), parse_mode="HTML")


@router.message(F.chat.type == "private", ~F.text.startswith("/"), F.text | F.photo | F.document | F.sticker | F.voice | F.video | F.animation | F.video_note | F.audio)
async def handle_user_message(message: Message):
    """处理用户发来的消息（非命令）"""
    # 管理员的消息由 admin.py 处理，这里跳过
    if message.from_user.id == config.ADMIN_ID:
        return

    user = message.from_user

    # 确保用户在数据库中
    await ensure_user(user.id, user.username, user.first_name, user.last_name)

    # 封禁检查（最高优先级）：被封用户照常转发给管理员（带标记），但不调 AI、回封禁提示
    is_banned = await is_user_banned(user.id)

    # 捐赠门槛：未解锁用户照常转发给管理员（带标记），但不调 AI、回捐赠提示
    is_locked = (not is_banned) and (not await _user_can_use(user.id))

    # 检查是否被管理员接管
    takeover = await is_takeover(user.id)

    # 获取消息文本内容
    content = message.text or message.caption or "[非文本消息]"

    # 构建管理员消息头部
    user_info = f"👤 用户: {html_module.escape(user.first_name or '未知')}"
    if user.username:
        user_info += f" (@{html_module.escape(user.username)})"
    user_info += f' | ID: <a href="tg://user?id={user.id}">{user.id}</a>'

    if is_banned:
        mode_label = "🚫 [已封禁]"
    elif is_locked:
        mode_label = "🔒 [未捐赠]"
    elif takeover:
        mode_label = "🔴 [人工接管中]"
    else:
        mode_label = "🤖 [AI 自动回复]"
    header = f"{mode_label}\n{user_info}"

    # 转发给管理员（只转发，不保存消息到 DB，避免 ask_ai 历史重复）
    last_admin_msg_id = await get_last_admin_msg_id(user.id)
    admin_msg_id = None

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

        forward_text = f"{header}{forward_info}\n\n💬 {html_module.escape(content)}"
        try:
            admin_msg = await message.bot.send_message(
                config.ADMIN_ID,
                forward_text,
                parse_mode="HTML",
                reply_to_message_id=last_admin_msg_id if last_admin_msg_id else None,
            )
            admin_msg_id = admin_msg.message_id
        except Exception:
            pass
    else:
        # 媒体消息
        admin_msg = await forward_media_to_admin(message, config.ADMIN_ID, header)
        if admin_msg:
            admin_msg_id = admin_msg.message_id

    # 发送短暂提示，3秒后自动删除（Telegram Bot 不支持主动弹窗，这是最接近 toast 的方式）
    try:
        notice = await message.answer("📨 消息已收到~")
        asyncio.get_event_loop().create_task(_delete_after(notice, 3))
    except Exception:
        pass

    # 封禁用户：消息已转发给管理员，但不调 AI、不存对话历史（AI 上下文），
    # 只回封禁提示。仍需保存 admin_msg_id 映射，否则管理员回复时无法反查 user_id。
    if is_banned:
        if admin_msg_id:
            await save_message(user.id, "in", content, admin_msg_id=admin_msg_id)
        await message.answer(BANNED_NOTICE)
        return

    # 未解锁用户：消息已转发给管理员，但不调 AI、不存对话历史（AI 上下文），
    # 只回捐赠提示。仍需保存 admin_msg_id 映射，否则管理员回复时无法反查 user_id。
    if is_locked:
        if admin_msg_id:
            await save_message(user.id, "in", content, admin_msg_id=admin_msg_id)
        await message.answer(await _donation_block_notice(user.id), parse_mode="HTML")
        return

    # 如果未被接管，AI 自动回复
    if not takeover:
        # 敏感词检测：如果命中敏感词，直接返回默认回复，不调用 AI
        is_sensitive, sensitive_reply = check_sensitive(content)
        if is_sensitive:
            # 保存用户消息到 DB
            await save_message(user.id, "in", content, admin_msg_id=admin_msg_id)

            # 发送默认回复给用户
            await message.answer(sensitive_reply, parse_mode=None)

            # 通知管理员触发了敏感词
            try:
                await message.bot.send_message(
                    config.ADMIN_ID,
                    f"⚠️ [敏感词拦截] {html_module.escape(user.first_name or '未知')} 的消息触发敏感词过滤\n\n"
                    f"💬 {html_module.escape(content)}\n\n"
                    f"🤖 已自动回复: {html_module.escape(sensitive_reply)}",
                )
            except Exception:
                pass
            return

        # 媒体消息处理
        ai_content = content
        if message.sticker:
            # 贴纸告诉 AI emoji，让它自然回应
            emoji = message.sticker.emoji or "🎭"
            ai_content = f"[用户发送了一个表情包 {emoji}，请根据 emoji 自然地回应，简短友好]"
        elif not message.text:
            # 其他媒体统一提示无法查看
            ai_content = "[用户发送了一条媒体消息，你无法查看，请告知用户你目前无法查看媒体内容，建议用文字描述]"

        # 发送"正在输入"状态
        await message.bot.send_chat_action(user.id, "typing")

        # 调用 AI（此时用户消息尚未保存到 DB，历史记录不会重复）
        ai_reply = await ask_ai(user.id, ai_content)

        # 保存用户消息到 DB（仅一次，在 ask_ai 之后避免历史重复）
        await save_message(user.id, "in", content, admin_msg_id=admin_msg_id)

        # 保存 AI 回复到 DB（仅一次）
        await save_message(user.id, "out_ai", ai_reply)

        # 发送 AI 回复给用户（parse_mode=None 避免 AI 回复中的 HTML 特殊字符导致解析错误）
        await message.answer(ai_reply, parse_mode=None)

        # 通知管理员 AI 的回复（回复到用户消息，形成线程）
        try:
            current_last = await get_last_admin_msg_id(user.id)
            ai_admin_msg = await message.bot.send_message(
                config.ADMIN_ID,
                f"🤖 [AI 回复给 {html_module.escape(user.first_name)}]\n\n{html_module.escape(ai_reply)}",
                reply_to_message_id=current_last if current_last else None,
            )
            # 更新 AI 回复记录的 admin_msg_id（避免重复保存）
            await update_message_admin_id(user.id, "out_ai", ai_admin_msg.message_id)
        except Exception:
            pass
    else:
        # 接管模式：只保存用户消息
        await save_message(user.id, "in", content, admin_msg_id=admin_msg_id)
