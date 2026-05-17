"""
敏感词过滤工具模块
检测用户消息中是否包含敏感词，如包含则返回默认回复，不调用 AI。

支持通配符：
  * 匹配任意多个字符（包括零个）
  ? 匹配单个字符
例如：买*药  可以匹配 "买毒品药"、"买假药"、"买药"
"""
import fnmatch
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# 默认敏感词回复
DEFAULT_SENSITIVE_REPLY = "抱歉，您的问题我无法回答。"

# 敏感词文件路径
SENSITIVE_WORDS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "sensitive_words.txt"


def load_sensitive_words(filepath: str | None = None) -> list[str]:
    """
    从文件加载敏感词列表。

    Args:
        filepath: 敏感词文件路径，默认为 data/sensitive_words.txt

    Returns:
        敏感词列表
    """
    path = Path(filepath) if filepath else SENSITIVE_WORDS_FILE

    if not path.exists():
        logger.warning("敏感词文件不存在: %s", path)
        return []

    words = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith("#"):
                    continue
                words.append(line.lower())
    except Exception as e:
        logger.error("加载敏感词文件失败: %s", e)

    return words


def contains_sensitive_word(text: str, sensitive_words: list[str]) -> bool:
    """
    检测文本中是否包含敏感词。
    支持通配符 * 和 ?（使用 fnmatch 风格匹配）。

    - 纯文本敏感词：子串匹配（如 "炸弹" 匹配 "我想买炸弹"）
    - 含通配符的敏感词：全模式匹配（如 "买*药" 匹配 "买假药"、"买违禁药品"）

    Args:
        text: 待检测文本
        sensitive_words: 敏感词列表

    Returns:
        是否包含敏感词
    """
    if not sensitive_words or not text:
        return False

    text_lower = text.lower()
    for word in sensitive_words:
        if "*" in word or "?" in word:
            # 通配符模式：对整段文本做 fnmatch 匹配
            if fnmatch.fnmatch(text_lower, word):
                logger.info("检测到敏感词(通配符): %s", word)
                return True
        else:
            # 普通敏感词：子串匹配
            if word in text_lower:
                logger.info("检测到敏感词: %s", word)
                return True
    return False


def check_sensitive(text: str, filepath: str | None = None) -> tuple[bool, str]:
    """
    检查文本是否包含敏感词，返回检测结果和回复内容。

    Args:
        text: 待检测文本
        filepath: 敏感词文件路径（可选）

    Returns:
        (是否包含敏感词, 回复内容)
        - 如果包含敏感词: (True, 默认回复)
        - 如果不包含: (False, "")
    """
    words = load_sensitive_words(filepath)
    if contains_sensitive_word(text, words):
        return True, DEFAULT_SENSITIVE_REPLY
    return False, ""