"""视频链接识别、抖音直链解析与音频下载。

链接提取不限于特定平台。非抖音链接交给 yt-dlp 原生解析；抖音链接
（douyin.com / v.douyin.com）先跟随短链拿到真实 video_id，再通过公开
解析接口获取无水印直链，用 requests 流式下载后用 ffmpeg 提取音频。
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

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
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 "
    "Mobile/15E148 Safari/604.1"
)

GENERIC_URL_RE = re.compile(
    r"https?://[^\s<>\"'`，。；、！？：）】》」』]+",
    re.IGNORECASE,
)

TRAILING_PUNCTUATION = "，。；、！？：）】》」』,;:!)"

DOUYIN_ID_PATTERNS = (
    re.compile(r"/(?:share/)?(?:video|note|slides)/(\d+)"),
    re.compile(r"[?&](?:modal_id|aweme_id|item_ids)=(\d+)"),
)

PARSER_TIMEOUT = (10.0, 25.0)
DOWNLOAD_TIMEOUT = (15.0, 60.0)


@dataclass(frozen=True)
class DownloadResult:
    audio_path: Path
    title: str
    video_url: str
    uploader: str | None
    duration: float | None


@dataclass(frozen=True)
class _DouyinMedia:
    video_id: str
    title: str
    uploader: str | None
    duration: float | None
    media_urls: tuple[str, ...]


def extract_url(text: str) -> str:
    """从分享文案或裸链接中提取第一个合法的 HTTP/HTTPS 链接。"""
    if not text or not text.strip():
        raise LinkParseError("没有收到内容，请输入视频分享链接或分享文案。")

    for match in GENERIC_URL_RE.finditer(text):
        candidate = match.group(0).rstrip(TRAILING_PUNCTUATION)
        if urlparse(candidate).netloc:
            return _canonicalize(candidate)

    raise LinkParseError(
        "未识别到有效的视频链接。请粘贴包含 http:// 或 https:// 地址的分享文案，"
        "例如抖音、B站、YouTube、微博等平台的视频链接。"
    )


def resolve_redirect(url: str, proxy: str | None = None, timeout: float = 15.0) -> str:
    """跟随抖音短链重定向并规范化；其他平台的链接原样交给 yt-dlp。"""
    netloc = urlparse(url).netloc.lower()
    if netloc not in {"v.douyin.com", "www.v.douyin.com"}:
        return _canonicalize(url)

    proxies = {"http": proxy, "https": proxy} if proxy else None
    try:
        response = requests.get(
            url,
            headers={"User-Agent": MOBILE_USER_AGENT},
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
    """下载音频到临时目录：抖音走解析接口，其他平台走 yt-dlp。"""
    if _is_douyin(link):
        return _download_douyin(link, settings, console)
    return _download_with_ytdlp(link, settings, console)


# ---------------------------------------------------------------- 抖音分支


def _is_douyin(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(
        host == domain or host.endswith(f".{domain}")
        for domain in ("douyin.com", "iesdouyin.com")
    )


def _extract_douyin_id(url: str) -> str | None:
    for pattern in DOUYIN_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    return None


def _download_douyin(
    link: str, settings: Settings, console: Console
) -> DownloadResult:
    try:
        resolved_url = resolve_redirect(link, proxy=settings.ytdlp_proxy)
    except DownloadError as exc:
        console.print(f"[yellow]提示：[/]{exc}，将直接把原始链接交给解析接口。")
        resolved_url = link

    video_id = _extract_douyin_id(resolved_url) or _extract_douyin_id(link)

    with console.status("[cyan]通过公开解析接口获取抖音直链...", spinner="dots"):
        media = _fetch_douyin_media(link, video_id, resolved_url, settings)

    video_id = video_id or media.video_id
    settings.temp_dir.mkdir(parents=True, exist_ok=True)
    video_path = settings.temp_dir / f"douyin_{video_id}.mp4"

    _stream_download(media.media_urls, video_path, settings, console)
    audio_path = _extract_audio(video_path, console)

    return DownloadResult(
        audio_path=audio_path,
        title=media.title,
        video_url=f"https://www.douyin.com/video/{media.video_id}",
        uploader=media.uploader,
        duration=media.duration,
    )


def _fetch_douyin_media(
    link: str,
    video_id: str | None,
    resolved_url: str,
    settings: Settings,
) -> _DouyinMedia:
    candidates = [link]
    canonical = (
        f"https://www.douyin.com/video/{video_id}" if video_id else None
    )
    if canonical and canonical != link:
        candidates.append(canonical)
    if resolved_url not in candidates:
        candidates.append(resolved_url)

    parsers = (_parse_with_bugpk, _parse_with_xingzhige)
    errors: list[str] = []
    for parser in parsers:
        for candidate in candidates:
            try:
                return parser(candidate, video_id, settings)
            except Exception as exc:
                errors.append(f"{parser.__name__}: {exc}")

    detail = "；".join(errors[-3:]) or "没有可用的解析接口"
    raise DownloadError(
        "抖音解析失败，所有公开解析接口都没有返回可用直链。"
        f"（{detail}）请稍后重试，或改用其他平台的链接。"
    )


def _parse_with_bugpk(
    url: str, video_id: str | None, settings: Settings
) -> _DouyinMedia:
    payload = _request_json(
        f"https://api.bugpk.com/api/douyin?url={quote(url, safe='')}", settings
    )
    if payload.get("code") != 200:
        raise ValueError(str(payload.get("msg") or "接口返回异常"))
    data = payload.get("data") or {}
    primary = data.get("url")
    backups = sorted(
        (item for item in data.get("video_backup") or [] if item.get("url")),
        key=lambda item: item.get("size") or 0,
    )
    urls = [item["url"] for item in backups]
    if primary:
        urls.append(primary)
    if not urls:
        raise ValueError("接口没有返回视频直链")

    return _DouyinMedia(
        video_id=str((data.get("extra") or {}).get("aweme_id") or video_id or ""),
        title=str(data.get("title") or data.get("desc") or "抖音视频"),
        uploader=(data.get("author") or {}).get("name"),
        duration=_as_float(data.get("duration")),
        media_urls=tuple(urls),
    )


def _parse_with_xingzhige(
    url: str, video_id: str | None, settings: Settings
) -> _DouyinMedia:
    payload = _request_json(
        f"https://api.xingzhige.com/API/douyin/?url={quote(url, safe='')}", settings
    )
    if payload.get("code") != 0:
        raise ValueError(str(payload.get("msg") or "接口返回异常"))
    data = payload.get("data") or {}
    item = data.get("item") or {}
    urls = [item.get("url"), item.get("ury")]
    urls = [candidate for candidate in urls if candidate]
    if not urls:
        raise ValueError("接口没有返回视频直链")

    return _DouyinMedia(
        video_id=str((data.get("jx") or {}).get("item_id") or video_id or ""),
        title=str(item.get("title") or "抖音视频"),
        uploader=(data.get("author") or {}).get("name"),
        duration=_as_float(item.get("duration")),
        media_urls=tuple(urls),
    )


def _request_json(url: str, settings: Settings) -> dict:
    proxies = (
        {"http": settings.ytdlp_proxy, "https": settings.ytdlp_proxy}
        if settings.ytdlp_proxy
        else None
    )
    response = requests.get(
        url,
        headers={
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "application/json, text/plain, */*",
        },
        timeout=PARSER_TIMEOUT,
        proxies=proxies,
    )
    response.raise_for_status()
    return json.loads(response.content.decode("utf-8"))


def _stream_download(
    urls: tuple[str, ...], dest: Path, settings: Settings, console: Console
) -> None:
    proxies = (
        {"http": settings.ytdlp_proxy, "https": settings.ytdlp_proxy}
        if settings.ytdlp_proxy
        else None
    )
    errors: list[str] = []

    for url in urls:
        try:
            with requests.get(
                url,
                headers={
                    "User-Agent": MOBILE_USER_AGENT,
                    "Referer": "https://www.douyin.com/",
                },
                timeout=DOWNLOAD_TIMEOUT,
                stream=True,
                proxies=proxies,
            ) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length") or 0) or None
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[cyan]下载视频"),
                    BarColumn(),
                    DownloadColumn(),
                    TransferSpeedColumn(),
                    TimeRemainingColumn(),
                    console=console,
                    transient=True,
                ) as progress:
                    task_id = progress.add_task("download", total=total)
                    with dest.open("wb") as handle:
                        for chunk in response.iter_content(chunk_size=256 * 1024):
                            if not chunk:
                                continue
                            handle.write(chunk)
                            progress.update(task_id, advance=len(chunk))
            if dest.stat().st_size > 0:
                return
            errors.append(f"{url[:60]}：下载内容为空")
        except requests.RequestException as exc:
            errors.append(f"{url[:60]}：{exc}")
        except OSError as exc:
            errors.append(f"写入文件失败：{exc}")
        dest.unlink(missing_ok=True)

    raise DownloadError("抖音视频直链下载失败：" + "；".join(errors[-2:]))


def _extract_audio(video_path: Path, console: Console) -> Path:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        console.print(
            "[yellow]提示：[/]未检测到 ffmpeg，直接使用视频文件进行转录。"
        )
        return video_path

    audio_path = video_path.with_suffix(".mp3")
    command = [
        ffmpeg,
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(video_path),
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-c:a",
        "libmp3lame",
        "-b:a",
        "64k",
        str(audio_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0 or not audio_path.is_file():
        console.print(
            "[yellow]提示：[/]音频提取失败，直接使用视频文件进行转录。"
        )
        audio_path.unlink(missing_ok=True)
        return video_path

    video_path.unlink(missing_ok=True)
    return audio_path


# ---------------------------------------------------------------- yt-dlp 分支


def _download_with_ytdlp(
    link: str, settings: Settings, console: Console
) -> DownloadResult:
    """用 yt-dlp 下载非抖音平台的最佳音质音频。"""
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

    raw_title = str(info.get("title") or "视频")
    title = re.sub(r"\s+", " ", raw_title).strip() or "视频"

    video_url = str(
        info.get("webpage_url") or info.get("original_url") or resolved_url
    )

    uploader = info.get("uploader") or info.get("creator")
    duration = info.get("duration")

    return DownloadResult(
        audio_path=audio_path,
        title=title,
        video_url=video_url,
        uploader=str(uploader) if uploader else None,
        duration=float(duration) if isinstance(duration, (int, float)) else None,
    )


# ---------------------------------------------------------------- 工具函数


def _canonicalize(url: str) -> str:
    if "douyin.com" not in (urlparse(url).hostname or "").lower():
        return url
    modal = re.search(r"[?&]modal_id=(\d+)", url)
    if modal:
        return f"https://www.douyin.com/video/{modal.group(1)}"
    return url


def _as_float(value) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


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
