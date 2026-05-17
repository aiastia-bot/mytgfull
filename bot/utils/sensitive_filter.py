"""
敏感词过滤工具模块
检测用户消息中是否包含敏感词，如包含则返回默认回复，不调用 AI。

支持三种模式：
  1. 纯文本：子串匹配（如 "炸弹" 匹配 "我想买炸弹"）
  2. 通配符：* 匹配任意多个字符，? 匹配单个字符（如 "买*药"）
  3. 正则表达式：以 re: 开头（如 re:\\w+_[pvd]:[A-Za-z0-9]{32}）
"""
import fnmatch
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 默认敏感词回复（从 config 读取）
def _get_sensitive_reply() -> str:
    from bot.config import config
    return config.SENSITIVE_REPLY

# 敏感词文件路径
SENSITIVE_WORDS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "sensitive_words.txt"


# 敏感词类型前缀
REGEX_PREFIX = "re:"


def load_sensitive_words(filepath: str | None = None) -> tuple[list[str], list[str]]:
    """
    从文件加载敏感词列表。

    Args:
        filepath: 敏感词文件路径，默认为 data/sensitive_words.txt

    Returns:
        (普通敏感词列表, 正则表达式敏感词列表)
    """
    path = Path(filepath) if filepath else SENSITIVE_WORDS_FILE

    if not path.exists():
        logger.warning("敏感词文件不存在: %s", path)
        return [], []

    words = []
    regex_patterns = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                # 跳过空行和注释
                if not line or line.startswith("#"):
                    continue
                if line.startswith(REGEX_PREFIX):
                    # 正则表达式模式（保持原始大小写）
                    pattern = line[len(REGEX_PREFIX):]
                    regex_patterns.append(pattern)
                else:
                    words.append(line.lower())
    except Exception as e:
        logger.error("加载敏感词文件失败: %s", e)

    return words, regex_patterns


def contains_sensitive_word(text: str, sensitive_words: list[str], regex_patterns: list[str] | None = None) -> bool:
    """
    检测文本中是否包含敏感词。

    支持三种模式：
    - 纯文本敏感词：子串匹配（如 "炸弹" 匹配 "我想买炸弹"）
    - 含通配符的敏感词：全模式匹配（如 "买*药" 匹配 "买假药"、"买违禁药品"）
    - 正则表达式：以 re: 开头的行，使用 re.search 搜索匹配

    Args:
        text: 待检测文本
        sensitive_words: 敏感词列表（纯文本和通配符）
        regex_patterns: 正则表达式列表

    Returns:
        是否包含敏感词
    """
    if not text:
        return False

    text_lower = text.lower()

    # 检查纯文本和通配符
    for word in sensitive_words:
        if "*" in word or "?" in word:
            if fnmatch.fnmatch(text_lower, word):
                logger.info("检测到敏感词(通配符): %s", word)
                return True
        else:
            if word in text_lower:
                logger.info("检测到敏感词: %s", word)
                return True

    # 检查正则表达式
    if regex_patterns:
        for pattern in regex_patterns:
            try:
                if re.search(pattern, text):
                    logger.info("检测到敏感词(正则): %s", pattern)
                    return True
            except re.error as e:
                logger.warning("正则表达式无效: %s, 错误: %s", pattern, e)

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
    words, regex_patterns = load_sensitive_words(filepath)
    if contains_sensitive_word(text, words, regex_patterns):
        return True, _get_sensitive_reply()
    return False, ""
