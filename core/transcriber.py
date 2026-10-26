"""基于 faster-whisper 的离线语音转录。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from config import Settings
from core import TranscriptionError


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    language: str
    duration: float


def transcribe(
    audio_path: Path, settings: Settings, console: Console
) -> TranscriptionResult:
    if not audio_path.is_file():
        raise TranscriptionError(f"音频文件不存在：{audio_path}")

    model, _ = _load_model(settings, console)

    language = settings.whisper_language.strip().lower()
    language_arg = None if language in {"", "auto"} else language

    kwargs = {
        "beam_size": 5,
        "vad_filter": True,
        "vad_parameters": {
            "min_silence_duration_ms": 500,
            "speech_pad_ms": 200,
        },
    }
    if language_arg:
        kwargs["language"] = language_arg
    if language_arg in (None, "zh"):
        kwargs["initial_prompt"] = (
            "以下是一段普通话视频的语音，请用简体中文转写，并补全标点符号。"
        )

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]语音识别"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_id = progress.add_task("transcribe", total=None)

        try:
            segments, info = model.transcribe(str(audio_path), **kwargs)
        except Exception as exc:
            raise TranscriptionError(f"启动语音转录失败：{exc}") from exc

        duration = float(getattr(info, "duration", 0) or 0)
        progress.update(task_id, total=duration if duration > 0 else None)

        lines: list[str] = []
        try:
            for segment in segments:
                piece = segment.text.strip()
                if piece:
                    lines.append(piece)
                if duration > 0:
                    progress.update(
                        task_id, completed=min(float(segment.end), duration)
                    )
        except Exception as exc:
            raise TranscriptionError(f"语音转录过程中断：{exc}") from exc

        progress.update(
            task_id,
            completed=duration if duration > 0 else 1,
            total=duration if duration > 0 else 1,
        )

    transcript = _normalize("\n".join(lines))
    if len(re.sub(r"\s+", "", transcript)) < 5:
        raise TranscriptionError(
            "没有识别到有效语音，可能是纯音乐、无人声或音质过低。"
        )

    detected = str(getattr(info, "language", None) or language_arg or "unknown")
    return TranscriptionResult(
        text=transcript,
        language=detected,
        duration=duration,
    )


def _load_model(settings: Settings, console: Console):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise TranscriptionError(
            "缺少依赖 faster-whisper，请先执行：pip install -r requirements.txt"
        ) from exc

    download_root = settings.whisper_download_root
    if download_root is not None:
        download_root.mkdir(parents=True, exist_ok=True)
    download_root_arg = str(download_root) if download_root else None

    device = _pick_device(settings.whisper_device)
    compute_type = _pick_compute_type(settings.whisper_compute_type, device)

    console.print(
        f"[dim]Whisper 模型：{settings.whisper_model} | "
        f"设备：{device} | 计算精度：{compute_type}[/]"
    )

    with console.status("[cyan]加载语音模型（首次运行会自动下载）...", spinner="dots"):
        try:
            model = WhisperModel(
                settings.whisper_model,
                device=device,
                compute_type=compute_type,
                download_root=download_root_arg,
            )
            return model, device
        except Exception as exc:
            if device != "cuda":
                raise TranscriptionError(f"加载 Whisper 模型失败：{exc}") from exc
            console.print(f"[yellow]CUDA 初始化失败，自动回退到 CPU：{exc}[/]")
            try:
                model = WhisperModel(
                    settings.whisper_model,
                    device="cpu",
                    compute_type="int8",
                    download_root=download_root_arg,
                )
            except Exception as cpu_exc:
                raise TranscriptionError(
                    f"加载 Whisper 模型失败：{cpu_exc}"
                ) from cpu_exc
            return model, "cpu"


def _pick_device(configured: str) -> str:
    if configured != "auto":
        return configured
    try:
        import ctranslate2
    except ImportError:
        return "cpu"
    try:
        return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
    except Exception:
        return "cpu"


def _pick_compute_type(configured: str, device: str) -> str:
    if configured != "auto":
        return configured
    return "float16" if device == "cuda" else "int8"


def _normalize(text: str) -> str:
    text = text.replace("​", "").replace("﻿", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
