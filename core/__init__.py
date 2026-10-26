"""douyin2obsidian 核心模块与统一异常体系。"""

from __future__ import annotations


class D2OError(Exception):
    """所有业务异常的基类，由 CLI 统一捕获并友好展示。"""


class ConfigError(D2OError):
    """环境变量缺失或配置不合法。"""


class LinkParseError(D2OError):
    """输入内容中找不到合法的抖音链接。"""


class DownloadError(D2OError):
    """短链解析或音频下载失败。"""


class TranscriptionError(D2OError):
    """语音转录失败。"""


class SummaryError(D2OError):
    """调用 DeepSeek 或解析其结果失败。"""


class VaultWriteError(D2OError):
    """写入 Obsidian 知识库失败。"""


__all__ = [
    "D2OError",
    "ConfigError",
    "LinkParseError",
    "DownloadError",
    "TranscriptionError",
    "SummaryError",
    "VaultWriteError",
]
