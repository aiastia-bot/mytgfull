import html as html_module

from aiogram import Router, F
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from bot.config import config
from bot.database import save_donation, ensure_user, refresh_unlock_status, get_user_total_donated, is_user_banned

router = Router()

BANNED_NOTICE = "🚫 你已被封禁，无法使用本 Bot。"


# 捐赠金额选项（Telegram Stars）
DONATION_OPTIONS = [
    (10, "🌟 入门支持"),
    (50, "☕ 请喝一杯咖啡"),
    (150, "🍔 请吃一顿快餐"),
    (300, "🍕 请吃一顿披萨"),
    (500, "🎉 鼎力支持"),
]


@router.message(Command("donate"))
async def cmd_donate(message: Message):
    """显示捐赠选项"""
    # 封禁用户禁止捐赠
    if message.from_user.id != config.ADMIN_ID and await is_user_banned(message.from_user.id):
        await message.answer(BANNED_NOTICE)
        return

    text = (
        "❤️ <b>支持我们</b>\n\n"
        "如果你觉得这个 Bot 对你有帮助，可以考虑支持一下！\n"
        "点击下方按钮选择捐赠金额（使用 Telegram Stars ⭐）：\n\n"
    )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = []
    for amount, label in DONATION_OPTIONS:
        buttons.append([InlineKeyboardButton(text=f"{label} - ⭐{amount}", callback_data=f"donate_{amount}")])

    buttons.append([InlineKeyboardButton(text="❌ 取消", callback_data="donate_cancel")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, reply_markup=keyboard, parse_mode="HTML")

    # 如果启用了加密货币捐赠，额外展示钱包地址
    if config.CRYPTO_ENABLED:
        crypto_lines = ["\n₿ <b>加密货币捐赠</b>\n"]
        if config.CRYPTO_BTC:
            crypto_lines.append(f"<b>BTC:</b> <code>{html_module.escape(config.CRYPTO_BTC)}</code>")
        if config.CRYPTO_ETH:
            crypto_lines.append(f"<b>ETH:</b> <code>{html_module.escape(config.CRYPTO_ETH)}</code>")
        if config.CRYPTO_USDT:
            crypto_lines.append(f"<b>USDT (ERC-20):</b> <code>{html_module.escape(config.CRYPTO_USDT)}</code>")
        if config.CRYPTO_TRON:
            crypto_lines.append(f"<b>TRON (TRC-20):</b> <code>{html_module.escape(config.CRYPTO_TRON)}</code>")

        if len(crypto_lines) > 1:
            crypto_text = "\n".join(crypto_lines)
            await message.answer(crypto_text, parse_mode="HTML")


@router.callback_query(F.data.startswith("donate_"))
async def process_donation_callback(callback_query):
    """处理捐赠按钮点击"""
    data = callback_query.data

    if data == "donate_cancel":
        await callback_query.message.edit_text("已取消。")
        await callback_query.answer()
        return

    amount_str = data.replace("donate_", "")
    try:
        amount = int(amount_str)
    except ValueError:
        await callback_query.answer("❌ 无效金额")
        return

    # 发送 Invoice（Telegram Stars 使用 XTR 货币，不需要 provider_token）
    await callback_query.message.bot.send_invoice(
        chat_id=callback_query.from_user.id,
        title="支持我们",
        description=f"感谢你的 ⭐{amount} 捐赠！",
        payload=f"donation_{amount}",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=f"⭐ 捐赠 {amount} Stars", amount=amount)],
    )

    await callback_query.answer()


@router.pre_checkout_query()
async def process_pre_checkout_query(pre_checkout_query: PreCheckoutQuery):
    """处理预结账查询"""
    await pre_checkout_query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message):
    """处理支付成功"""
    payment = message.successful_payment

    # 确保用户在数据库中
    await ensure_user(
        message.from_user.id,
        message.from_user.username,
        message.from_user.first_name,
        message.from_user.last_name,
    )

    # 保存捐赠记录（XTR 金额就是星星数）
    amount = payment.total_amount
    await save_donation(
        message.from_user.id,
        amount,
        payment.currency,
        payment.telegram_payment_charge_id,
        payment.provider_payment_charge_id,
    )

    # 根据累计捐赠重新计算解锁状态
    just_unlocked = await refresh_unlock_status(message.from_user.id)

    thanks = f"🎉 感谢你的 ⭐{amount} 捐赠！\n\n你的支持是我们前进的动力 ❤️"

    if getattr(config, "DONATION_REQUIRED", False):
        total = await get_user_total_donated(message.from_user.id)
        if just_unlocked:
            thanks += (
                "\n\n🔓 <b>恭喜！你已累计捐赠 ⭐{total}，Bot 已解锁，现在可以正常使用了！</b>\n"
                "直接给我发消息即可。"
            ).format(total=int(total))
        elif total < config.DONATION_MIN_AMOUNT:
            thanks += (
                "\n\n📊 累计已支持 ⭐{total} / ⭐{need}，"
                "还差 ⭐{remain} 即可解锁 Bot 使用权限。"
            ).format(
                total=int(total),
                need=int(config.DONATION_MIN_AMOUNT),
                remain=int(config.DONATION_MIN_AMOUNT - total),
            )

    await message.answer(thanks, parse_mode="HTML")

    # 通知管理员
    try:
        await message.bot.send_message(
            config.ADMIN_ID,
            f"💰 收到捐赠！\n\n"
            f"👤 来自: {message.from_user.first_name} (@{message.from_user.username or 'N/A'})\n"
            f"⭐ 金额: {amount} Stars",
        )
    except Exception:
        pass