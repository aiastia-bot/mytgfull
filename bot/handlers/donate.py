from aiogram import Router, F
from aiogram.types import Message, LabeledPrice, PreCheckoutQuery
from aiogram.filters import Command
from bot.config import config
from bot.database import save_donation, ensure_user

router = Router()


# 捐赠金额选项
DONATION_OPTIONS = [
    (1, "☕ 请喝一杯咖啡"),
    (5, "🍔 请吃一顿快餐"),
    (10, "🍕 请吃一顿披萨"),
    (25, "🎉 鼎力支持"),
]


@router.message(Command("donate"))
async def cmd_donate(message: Message):
    """显示捐赠选项"""
    if not config.PAYMENT_PROVIDER_TOKEN:
        await message.answer(
            "❤️ 感谢你的心意！\n\n"
            "目前暂未开放捐赠功能，请稍后再试。"
        )
        return

    text = (
        "❤️ **支持我们**\n\n"
        "如果你觉得这个 Bot 对你有帮助，可以考虑支持一下！\n"
        "点击下方按钮选择捐赠金额：\n\n"
    )

    # 使用 inline keyboard 提供选项
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    buttons = []
    for amount, label in DONATION_OPTIONS:
        buttons.append([InlineKeyboardButton(text=f"{label} - ${amount}", callback_data=f"donate_{amount}")])

    buttons.append([InlineKeyboardButton(text="❌ 取消", callback_data="donate_cancel")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, reply_markup=keyboard, parse_mode="Markdown")


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

    # 发送 Invoice
    await callback_query.message.bot.send_invoice(
        chat_id=callback_query.from_user.id,
        title="支持我们",
        description=f"感谢你的 ${amount} 捐赠！",
        payload=f"donation_{amount}",
        provider_token=config.PAYMENT_PROVIDER_TOKEN,
        currency=config.DONATION_CURRENCY,
        prices=[LabeledPrice(label=f"捐赠 ${amount}", amount=amount * 100)],  # 金额单位为分
        start_parameter="donate",
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

    # 保存捐赠记录
    amount = payment.total_amount / 100  # 分转元
    await save_donation(
        message.from_user.id,
        amount,
        payment.currency,
        payment.telegram_payment_charge_id,
        payment.provider_payment_charge_id,
    )

    await message.answer(
        f"🎉 感谢你的 ${amount:.0f} 捐赠！\n\n你的支持是我们前进的动力 ❤️"
    )

    # 通知管理员
    try:
        await message.bot.send_message(
            config.ADMIN_ID,
            f"💰 收到捐赠！\n\n"
            f"👤 来自: {message.from_user.first_name} (@{message.from_user.username or 'N/A'})\n"
            f"💵 金额: ${amount:.0f} {payment.currency}",
        )
    except Exception:
        pass