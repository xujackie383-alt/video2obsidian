"""读取并校验 .env 中的配置。"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from core import ConfigError

PROJECT_ROOT = Path(__file__).resolve().parent
ENV_FILE = PROJECT_ROOT / ".env"

load_dotenv(ENV_FILE)

SUPPORTED_DEVICES = {"auto", "cpu", "cuda"}
SUPPORTED_COMPUTE_TYPES = {
    "auto",
    "int8",
    "int8_float16",
    "int8_float32",
    "int16",
    "float16",
    "float32",
    "bfloat16",
}


def _get(name: str) -> str | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    raw = raw.strip()
    return raw or None


def _require(name: str) -> str:
    value = _get(name)
    if value is None:
        raise ConfigError(
            f"缺少环境变量 {name}。请复制 .env.example 为 .env，并填写完整配置。"
        )
    return value


def _optional_path(name: str) -> Path | None:
    raw = _get(name)
    if raw is None:
        return None
    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _parse_float(name: str, default: float, minimum: float) -> float:
    raw = _get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是数字，当前值为：{raw}") from exc
    if value < minimum:
        raise ConfigError(f"{name} 不能小于 {minimum}，当前值为：{value}")
    return value


def _parse_int(name: str, default: int, minimum: int) -> int:
    raw = _get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} 必须是整数，当前值为：{raw}") from exc
    if value < minimum:
        raise ConfigError(f"{name} 不能小于 {minimum}，当前值为：{value}")
    return value


@dataclass(frozen=True)
class Settings:
    """运行期配置。只从环境变量读取，避免敏感信息进入代码。"""

    deepseek_api_key: str
    deepseek_base_url: str
    deepseek_model: str
    deepseek_timeout: float
    vault_path: Path
    whisper_model: str
    whisper_device: str
    whisper_compute_type: str
    whisper_language: str
    whisper_download_root: Path | None
    temp_dir: Path
    ytdlp_proxy: str | None
    summary_max_input_chars: int

    @classmethod
    def load(cls) -> "Settings":
        api_key = _require("DEEPSEEK_API_KEY")
        if api_key.startswith("sk-your") or api_key == "sk-xxx":
            raise ConfigError("DEEPSEEK_API_KEY 仍是示例占位符，请填写真实可用的 Key。")

        base_url = (
            _get("DEEPSEEK_BASE_URL") or "https://api.deepseek.com"
        ).rstrip("/")
        model = _get("DEEPSEEK_MODEL") or "deepseek-chat"
        timeout = _parse_float("DEEPSEEK_TIMEOUT", 180.0, minimum=10.0)

        vault_raw = _require("OBSIDIAN_VAULT_PATH")
        vault_path = Path(vault_raw).expanduser()
        if not vault_path.is_absolute():
            raise ConfigError(
                "OBSIDIAN_VAULT_PATH 必须是绝对路径，例如 D:/Obsidian/MyVault。"
            )
        vault_path = vault_path.resolve()
        if not vault_path.exists():
            raise ConfigError(f"知识库路径不存在：{vault_path}")
        if not vault_path.is_dir():
            raise ConfigError(f"知识库路径不是文件夹：{vault_path}")

        device = (_get("WHISPER_DEVICE") or "auto").lower()
        if device not in SUPPORTED_DEVICES:
            raise ConfigError(
                f"WHISPER_DEVICE 只能是 {', '.join(sorted(SUPPORTED_DEVICES))}，"
                f"当前值为：{device}"
            )

        compute_type = (_get("WHISPER_COMPUTE_TYPE") or "auto").lower()
        if compute_type not in SUPPORTED_COMPUTE_TYPES:
            raise ConfigError(
                "WHISPER_COMPUTE_TYPE 取值不合法，可选："
                f"{', '.join(sorted(SUPPORTED_COMPUTE_TYPES))}"
            )

        return cls(
            deepseek_api_key=api_key,
            deepseek_base_url=base_url,
            deepseek_model=model,
            deepseek_timeout=timeout,
            vault_path=vault_path,
            whisper_model=_get("WHISPER_MODEL") or "base",
            whisper_device=device,
            whisper_compute_type=compute_type,
            whisper_language=_get("WHISPER_LANGUAGE") or "zh",
            whisper_download_root=_optional_path("WHISPER_DOWNLOAD_ROOT"),
            temp_dir=_optional_path("TEMP_DIR") or (PROJECT_ROOT / "temp"),
            ytdlp_proxy=_get("YTDLP_PROXY"),
            summary_max_input_chars=_parse_int(
                "SUMMARY_MAX_INPUT_CHARS", 12000, minimum=2000
            ),
        )
