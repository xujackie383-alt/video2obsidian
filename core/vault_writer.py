"""按 Obsidian 笔记模板生成 Markdown 并写入知识库。"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from config import Settings
from core import VaultWriteError

_INVALID_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
_WINDOWS_RESERVED = (
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{index}" for index in range(1, 10)}
    | {f"LPT{index}" for index in range(1, 10)}
)


def write_note(
    *,
    title: str,
    video_title: str,
    video_url: str,
    body: str,
    transcript: str,
    settings: Settings,
    created_at: datetime | None = None,
) -> Path:
    notes_dir = _resolve_notes_dir(settings)
    try:
        notes_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise VaultWriteError(f"无法创建笔记目录 {notes_dir}：{exc}") from exc

    note_path = _unique_path(notes_dir, _sanitize_filename(title))
    content = build_markdown(
        title=title,
        video_title=video_title,
        video_url=video_url,
        body=body,
        transcript=transcript,
        created_at=created_at,
    )

    try:
        note_path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise VaultWriteError(f"写入笔记失败 {note_path}：{exc}") from exc

    return note_path


def build_markdown(
    *,
    title: str,
    video_title: str,
    video_url: str,
    body: str,
    transcript: str,
    created_at: datetime | None = None,
) -> str:
    created = (created_at or datetime.now()).strftime("%Y-%m-%d %H:%M")
    link_title = _escape_link_text(video_title or "原视频")

    blocks = [
        f"# {title.strip()}",
        f"> 原视频：[{link_title}]({video_url}) | 记录时间：{created}",
        "",
        body.strip(),
        "",
        "## 原始逐字稿",
        "",
        "> [!note]- 展开查看原文",
    ]

    transcript = transcript.strip()
    if transcript:
        for line in transcript.splitlines():
            stripped = line.rstrip()
            blocks.append(f"> {stripped}" if stripped else ">")
    else:
        blocks.append("> （无转录内容）")

    return "\n".join(blocks).rstrip() + "\n"


def _resolve_notes_dir(settings: Settings) -> Path:
    """笔记直接写入知识库根目录，不再使用固定子目录。"""
    vault = settings.vault_path.resolve()
    if not vault.is_dir():
        raise VaultWriteError(f"知识库目录不存在：{vault}")
    return vault


def _sanitize_filename(name: str, max_len: int = 80) -> str:
    cleaned = _INVALID_FILENAME.sub(" ", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .")
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len].rstrip(" .")
    if cleaned.upper() in _WINDOWS_RESERVED:
        cleaned = f"_{cleaned}"
    return cleaned or "未命名笔记"


def _unique_path(directory: Path, stem: str) -> Path:
    path = directory / f"{stem}.md"
    index = 2
    while path.exists():
        path = directory / f"{stem} ({index}).md"
        index += 1
    return path


def _escape_link_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")
