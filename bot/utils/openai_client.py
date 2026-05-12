from openai import AsyncOpenAI
from bot.config import config
from bot.database import get_chat_history_for_ai, get_system_prompt


async def ask_ai(user_id: int, user_message: str) -> str:
    """调用 OpenAI API 获取 AI 回复"""
    client = AsyncOpenAI(api_key=config.OPENAI_API_KEY, base_url=config.OPENAI_API_BASE)

    # 获取系统提示词
    system_prompt = await get_system_prompt()

    # 获取对话历史
    history = await get_chat_history_for_ai(user_id, config.MAX_HISTORY_ROUNDS)

    # 构建消息列表
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    try:
        response = await client.chat.completions.create(
            model=config.OPENAI_MODEL,
            messages=messages,
            max_tokens=1000,
            temperature=0.7,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[AI 错误] {str(e)}"