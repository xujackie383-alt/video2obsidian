"""抖音链接识别、短链重定向解析与音频下载。"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import requests
from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from config import Settings
from core import DownloadError, LinkParseError

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

SHORT_LINK_RE = re.compile(
    r"https?://v\.douyin\.com/[A-Za-z0-9_\-]+/?(?:\?[A-Za-z0-9_\-=&%.?]*)?",
    re.IGNORECASE,
)
LONG_LINK_RE = re.compile(
    r"https?://(?:(?:www|m)\.)?(?:douyin\.com|iesdouyin\.com)/"
    r"(?:video|note|share/video|share/note|share/slides)/\d+"
    r"(?:\?[A-Za-z0-9_\-=&%.?]*)?",
    re.IGNORECASE,
)
MODAL_LINK_RE = re.compile(
    r"https?://(?:(?:www|m)\.)?douyin\.com/"
    r"[A-Za-z0-9_\-/.?=&%]*?[?&]modal_id=(\d+)",
    re.IGNORECASE,
)

TRAILING_PUNCTUATION = "，。；、！？）】》」』,;!)"


@dataclass(frozen=True)
class DownloadResult:
    audio_path: Path
    title: str
    video_url: str
    uploader: str | None
    duration: float | None


def extract_douyin_url(text: str) -> str:
    """从分享文案或裸链接中提取第一个抖音 URL。"""
    if not text or not text.strip():
        raise LinkParseError("没有收到内容，请输入抖音分享链接或分享文案。")

    matches = [
        match
        for match in (SHORT_LINK_RE.search(text), LONG_LINK_RE.search(text))
        if match is not None
    ]
    if matches:
        best = min(matches, key=lambda item: item.start())
        return best.group(0).rstrip(TRAILING_PUNCTUATION)

    modal = MODAL_LINK_RE.search(text)
    if modal:
        return f"https://www.douyin.com/video/{modal.group(1)}"

    raise LinkParseError(
        "未识别到有效的抖音链接。支持 v.douyin.com 短链，"
        "或 douyin.com/video/... 长链，请检查后重试。"
    )


def resolve_redirect(url: str, proxy: str | None = None, timeout: float = 15.0) -> str:
    """跟随短链重定向，返回最终地址；非短链则直接返回规范化地址。"""
    netloc = urlparse(url).netloc.lower()
    if netloc not in {"v.douyin.com", "www.v.douyin.com"}:
        return _canonicalize(url)

    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        response = requests.get(
            url,
            headers={"User-Agent": DEFAULT_USER_AGENT},
            allow_redirects=True,
            timeout=timeout,
            stream=True,
            proxies=proxies,
        )
        try:
            final_url = response.url or url
        finally:
            response.close()
    except requests.RequestException as exc:
        raise DownloadError(f"短链重定向解析失败：{exc}") from exc

    return _canonicalize(final_url)


def download_audio(link: str, settings: Settings, console: Console) -> DownloadResult:
    """下载最佳音质的音频到临时目录。"""
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise DownloadError(
            "缺少依赖 yt-dlp，请先执行：pip install -r requirements.txt"
        ) from exc

    if shutil.which("ffmpeg") is None:
        console.print(
            "[yellow]提示：[/]未检测到 ffmpeg，部分音频格式可能下载失败，"
            "建议安装后重试（详见 README）。"
        )

    try:
        resolved_url = resolve_redirect(link, proxy=settings.ytdlp_proxy)
    except DownloadError as exc:
        console.print(f"[yellow]提示：[/]{exc}，将直接把原始链接交给 yt-dlp。")
        resolved_url = link

    settings.temp_dir.mkdir(parents=True, exist_ok=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[cyan]下载音频"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
        transient=True,
    ) as progress:
        task_id = progress.add_task("download", total=None)

        def on_progress(data: dict) -> None:
            status = data.get("status")
            if status == "downloading":
                total = data.get("total_bytes") or data.get("total_bytes_estimate")
                progress.update(
                    task_id,
                    completed=data.get("downloaded_bytes") or 0,
                    total=total,
                )
            elif status == "finished":
                total = data.get("total_bytes") or data.get("downloaded_bytes") or 0
                progress.update(task_id, completed=total, total=total)

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(settings.temp_dir / "%(id)s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "socket_timeout": 30,
            "retries": 3,
            "fragment_retries": 3,
            "progress_hooks": [on_progress],
            "http_headers": {"User-Agent": DEFAULT_USER_AGENT},
        }
        if settings.ytdlp_proxy:
            ydl_opts["proxy"] = settings.ytdlp_proxy
        if settings.ytdlp_cookies_file:
            ydl_opts["cookiefile"] = str(settings.ytdlp_cookies_file)

        try:
            with YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(resolved_url, download=True)
                if info is None:
                    raise DownloadError("yt-dlp 没有返回视频信息。")
                if info.get("_type") == "playlist":
                    entries = [entry for entry in (info.get("entries") or []) if entry]
                    if not entries:
                        raise DownloadError("该链接不包含可下载的视频。")
                    info = entries[0]
                audio_path = _locate_audio_file(ydl, info)
        except DownloadError:
            raise
        except Exception as exc:
            raise DownloadError(f"音频下载失败：{exc}") from exc

    if audio_path.stat().st_size == 0:
        raise DownloadError(f"下载的音频文件为空：{audio_path}")

    raw_title = str(info.get("title") or "抖音视频")
    title = re.sub(r"\s+", " ", raw_title).strip() or "抖音视频"

    video_id = str(info.get("id") or "")
    if video_id.isdigit():
        video_url = f"https://www.douyin.com/video/{video_id}"
    else:
        video_url = str(info.get("webpage_url") or resolved_url)

    uploader = info.get("uploader") or info.get("creator")
    duration = info.get("duration")

    return DownloadResult(
        audio_path=audio_path,
        title=title,
        video_url=video_url,
        uploader=str(uploader) if uploader else None,
        duration=float(duration) if isinstance(duration, (int, float)) else None,
    )


def _canonicalize(url: str) -> str:
    if "douyin.com" not in urlparse(url).netloc.lower():
        return url
    modal = re.search(r"[?&]modal_id=(\d+)", url)
    if modal:
        return f"https://www.douyin.com/video/{modal.group(1)}"
    return url


def _locate_audio_file(ydl, info: dict) -> Path:
    candidates: list[Path] = []
    try:
        candidates.append(Path(ydl.prepare_filename(info)))
    except Exception:
        pass
    for item in info.get("requested_downloads") or []:
        filepath = item.get("filepath")
        if filepath:
            candidates.append(Path(filepath))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise DownloadError("下载似乎完成了，但没有找到音频文件。")
