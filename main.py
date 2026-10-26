#!/usr/bin/env python3
"""video2obsidian：把视频语音转成结构化 Obsidian 笔记。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.prompt import Prompt

from config import ConfigError, Settings
from core import V2OError
from core.downloader import download_audio, extract_url
from core.summarizer import Summarizer
from core.transcriber import transcribe
from core.vault_writer import write_note

__version__ = "0.2.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="video2obsidian",
        description="从视频分享链接下载音频，离线转录并用 DeepSeek 重构为 Obsidian 笔记。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            '  python main.py "https://www.bilibili.com/video/BVxxxxxxxxxx"\n'
            '  python main.py "https://www.youtube.com/watch?v=xxxxxxxxxxx"\n'
            '  python main.py "7.89 复制打开抖音... https://v.douyin.com/xxxx/" --keep-audio\n'
            "  python main.py          # 回车后粘贴分享链接\n"
        ),
    )
    parser.add_argument(
        "url",
        nargs="*",
        help="视频分享链接或完整分享文案（抖音 / B站 / YouTube / 微博等）",
    )
    parser.add_argument(
        "--keep-audio", action="store_true", help="成功后保留 temp/ 中的音频文件"
    )
    parser.add_argument("--verbose", action="store_true", help="出错时打印完整堆栈")
    parser.add_argument(
        "--version", action="version", version=f"%(prog)s {__version__}"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_stdio()
    args = build_parser().parse_args(argv)
    console = Console()

    try:
        settings = Settings.load()
    except ConfigError as exc:
        console.print(f"[bold red]配置错误：[/]{escape(str(exc))}")
        console.print("[dim]请对照 .env.example 检查 .env 中的配置。[/]")
        return 2

    console.print()
    console.print(
        Panel.fit(
            f"[bold]video2obsidian[/] v{__version__}\n"
            f"语音模型：{escape(settings.whisper_model)}"
            f"（{escape(settings.whisper_device)}）\n"
            f"整理模型：{escape(settings.deepseek_model)}\n"
            f"知识库：{escape(str(settings.vault_path))}",
            border_style="cyan",
        )
    )

    try:
        if args.url:
            raw_input = " ".join(args.url).strip()
        else:
            raw_input = Prompt.ask(
                "[bold]请粘贴视频分享链接或分享文案[/]", console=console
            ).strip()
    except (KeyboardInterrupt, EOFError):
        console.print("\n[yellow]已取消。[/]")
        return 130

    if not raw_input:
        console.print("[yellow]没有输入内容，已退出。[/]")
        return 2

    return _run(
        raw_input,
        settings,
        console,
        keep_audio=args.keep_audio,
        verbose=args.verbose,
    )


def _run(
    raw_input: str,
    settings: Settings,
    console: Console,
    *,
    keep_audio: bool,
    verbose: bool,
) -> int:
    audio_path: Path | None = None

    try:
        console.rule("[bold cyan]1/5  解析链接[/]", align="left")
        link = extract_url(raw_input)
        console.print(f"识别到链接：[cyan]{escape(link)}[/]")

        console.rule("[bold cyan]2/5  下载音频[/]", align="left")
        media = download_audio(link, settings, console)
        audio_path = media.audio_path
        console.print(f"视频标题：{escape(media.title)}")
        if media.uploader:
            console.print(f"作者：{escape(media.uploader)}")
        console.print(f"音频文件：[dim]{escape(str(audio_path))}[/]")

        console.rule("[bold cyan]3/5  语音转录[/]", align="left")
        transcription = transcribe(audio_path, settings, console)
        console.print(
            f"转录完成：{len(transcription.text)} 字"
            f"（语言 {escape(transcription.language)}）"
        )

        console.rule("[bold cyan]4/5  AI 深度重构[/]", align="left")
        with console.status("[cyan]DeepSeek 正在消化并重构内容...", spinner="dots"):
            summary = Summarizer(settings).summarize(
                transcription.text, media.title
            )
        console.print(f"笔记主题：{escape(summary.title)}")

        console.rule("[bold cyan]5/5  写入 Obsidian[/]", align="left")
        note_path = write_note(
            title=summary.title,
            video_title=media.title,
            video_url=media.video_url,
            body=summary.body,
            transcript=transcription.text,
            settings=settings,
        )

        if keep_audio:
            console.print(f"[dim]已保留临时音频：{escape(str(audio_path))}[/]")
        else:
            try:
                audio_path.unlink(missing_ok=True)
                console.print(
                    f"[dim]已清理临时音频：{escape(audio_path.name)}[/]"
                )
            except OSError as exc:
                console.print(
                    f"[yellow]清理临时音频失败：[/]{escape(str(exc))}"
                )

        console.print(
            Panel(
                f"[bold green]笔记已保存[/]\n{escape(str(note_path))}",
                title="完成",
                border_style="green",
            )
        )
        return 0

    except (ConfigError, V2OError) as exc:
        console.print(f"\n[bold red]执行失败：[/]{escape(str(exc))}")
        _report_retained_audio(console, audio_path)
        return 1
    except KeyboardInterrupt:
        console.print("\n[yellow]已取消。[/]")
        _report_retained_audio(console, audio_path)
        return 130
    except Exception as exc:
        if verbose:
            console.print_exception(show_locals=False)
        else:
            console.print(f"\n[bold red]发生未预期的错误：[/]{escape(str(exc))}")
            console.print("[dim]可加 --verbose 查看完整堆栈。[/]")
        _report_retained_audio(console, audio_path)
        return 1


def _report_retained_audio(console: Console, audio_path: Path | None) -> None:
    if audio_path is not None and audio_path.exists():
        console.print(
            f"[yellow]临时音频已保留，便于排查：[/]"
            f"{escape(str(audio_path))}"
        )


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError, ValueError):
            pass


if __name__ == "__main__":
    sys.exit(main())
