import aiosqlite
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "bot.db")


async def get_db() -> aiosqlite.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    return db


async def init_db():
    """初始化数据库表"""
    db = await get_db()
    try:
        await db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_active TEXT DEFAULT CURRENT_TIMESTAMP,
                is_takeover INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                direction TEXT NOT NULL,  -- 'in' from user, 'out_ai' AI reply, 'out_admin' admin reply
                content TEXT,
                admin_msg_id INTEGER,  -- 转发给管理员的消息 ID（用于回复关联）
                created_at STRING DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS donations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                telegram_charge_id TEXT,
                provider_charge_id TEXT,
                created_at STRING DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """
        )
        await db.commit()
    finally:
        await db.close()


async def ensure_user(user_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """确保用户存在于数据库"""
    db = await get_db()
    try:
        now = datetime.now().isoformat()
        await db.execute(
            """INSERT INTO users (user_id, username, first_name, last_name, first_seen, last_active)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(user_id) DO UPDATE SET
                   username = COALESCE(?, username),
                   first_name = COALESCE(?, first_name),
                   last_name = COALESCE(?, last_name),
                   last_active = ?""",
            (user_id, username, first_name, last_name, now, now,
             username, first_name, last_name, now),
        )
        await db.commit()
    finally:
        await db.close()


async def is_takeover(user_id: int) -> bool:
    """检查用户对话是否被管理员接管"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT is_takeover FROM users WHERE user_id = ?", (user_id,))
        row = await cursor.fetchone()
        return row is not None and row[0] == 1
    finally:
        await db.close()


async def set_takeover(user_id: int, takeover: bool):
    """设置/取消接管"""
    db = await get_db()
    try:
        await db.execute("UPDATE users SET is_takeover = ? WHERE user_id = ?", (1 if takeover else 0, user_id))
        await db.commit()
    finally:
        await db.close()


async def save_message(user_id: int, direction: str, content: str, admin_msg_id: int = None):
    """保存消息记录"""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO messages (user_id, direction, content, admin_msg_id) VALUES (?, ?, ?, ?)",
            (user_id, direction, content, admin_msg_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_user_history(user_id: int, limit: int = 20) -> list:
    """获取用户对话历史"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT direction, content, created_at FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()
        return list(reversed(rows))
    finally:
        await db.close()


async def get_chat_history_for_ai(user_id: int, max_rounds: int) -> list:
    """获取用于 AI 的对话历史（OpenAI 格式）"""
    from bot.config import config

    limit = max_rounds * 2  # 每轮一问一答
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT direction, content FROM messages WHERE user_id = ? ORDER BY id DESC LIMIT ?",
            (user_id, limit),
        )
        rows = await cursor.fetchall()

        messages = []
        for row in reversed(rows):
            direction = row[0]
            content = row[1]
            if direction == "in":
                messages.append({"role": "user", "content": content})
            elif direction in ("out_ai", "out_admin"):
                messages.append({"role": "assistant", "content": content})

        # 确保不超过最大轮数
        if len(messages) > max_rounds * 2:
            messages = messages[-(max_rounds * 2):]

        return messages
    finally:
        await db.close()


async def get_all_users() -> list:
    """获取所有用户列表"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT user_id, username, first_name, last_name, first_seen, last_active, is_takeover FROM users ORDER BY last_active DESC"
        )
        return await cursor.fetchall()
    finally:
        await db.close()


async def get_stats() -> dict:
    """获取统计数据"""
    db = await get_db()
    try:
        cursor = await db.execute("SELECT COUNT(*) FROM users")
        user_count = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM messages")
        msg_count = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COALESCE(SUM(amount), 0) FROM donations")
        total_donated = (await cursor.fetchone())[0]

        cursor = await db.execute("SELECT COUNT(*) FROM donations")
        donation_count = (await cursor.fetchone())[0]

        return {
            "user_count": user_count,
            "msg_count": msg_count,
            "total_donated": total_donated,
            "donation_count": donation_count,
        }
    finally:
        await db.close()


async def save_donation(user_id: int, amount: float, currency: str, telegram_charge_id: str, provider_charge_id: str):
    """保存捐赠记录"""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO donations (user_id, amount, currency, telegram_charge_id, provider_charge_id) VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, currency, telegram_charge_id, provider_charge_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_last_admin_msg_id(user_id: int) -> int | None:
    """获取某用户最近一条转发给管理员的消息的 admin_msg_id（用于线程链接）"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT admin_msg_id FROM messages WHERE user_id = ? AND admin_msg_id IS NOT NULL ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None
    finally:
        await db.close()


async def get_admin_msg_user_id(admin_msg_id: int) -> int:
    """通过管理员消息 ID 查找对应用户 ID（支持所有消息类型）"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT user_id FROM messages WHERE admin_msg_id = ? ORDER BY id DESC LIMIT 1",
            (admin_msg_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None
    finally:
        await db.close()


async def get_last_active_user(admin_id: int) -> int | None:
    """获取管理员最近交流的用户 ID（最后一个发来消息的用户）"""
    db = await get_db()
    try:
        cursor = await db.execute(
            "SELECT user_id FROM messages WHERE user_id != ? ORDER BY id DESC LIMIT 1",
            (admin_id,),
        )
        row = await cursor.fetchone()
        return row[0] if row else None
    finally:
        await db.close()


async def update_message_admin_id(user_id: int, direction: str, admin_msg_id: int):
    """更新最近一条消息的 admin_msg_id（避免重复保存消息）"""
    db = await get_db()
    try:
        await db.execute(
            "UPDATE messages SET admin_msg_id = ? WHERE user_id = ? AND direction = ? AND id = (SELECT id FROM messages WHERE user_id = ? AND direction = ? ORDER BY id DESC LIMIT 1)",
            (admin_msg_id, user_id, direction, user_id, direction),
        )
        await db.commit()
    finally:
        await db.close()


async def get_system_prompt() -> str:
    """获取当前 AI 系统提示词"""
    from bot.config import config

    db = await get_db()
    try:
        cursor = await db.execute("SELECT value FROM settings WHERE key = 'system_prompt'")
        row = await cursor.fetchone()
        if row:
            return row[0]
        return config.AI_SYSTEM_PROMPT
    finally:
        await db.close()


async def set_system_prompt(prompt: str):
    """设置 AI 系统提示词"""
    db = await get_db()
    try:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES ('system_prompt', ?) ON CONFLICT(key) DO UPDATE SET value = ?",
            (prompt, prompt),
        )
        await db.commit()
    finally:
        await db.close()