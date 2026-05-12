"""Bot 工具函数"""


def escape_html(text: str) -> str:
    """转义 HTML 特殊字符，防止用户内容破坏 HTML 格式"""
    text = text.replace("&", "&")
    text = text.replace("<", "<")
    text = text.replace(">", ">")
    return text