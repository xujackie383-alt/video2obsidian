---
name: video2obsidian
description: 把视频转成 Obsidian 笔记。当用户说「转视频为笔记」「把这个视频转成笔记」「视频转 Obsidian」「整理这条视频」，或直接发来抖音 / B站 / YouTube / 微博等视频链接（含 App 分享文案）时使用。执行 python main.py "<链接>"，自动完成下载、本地离线转写、AI 重构并写入 Obsidian 知识库。
allowed-tools: Bash, Read
---

# video2obsidian

一条视频链接 → 一篇 Obsidian 笔记。下载、转写、重构、落库全部由项目自带的 `main.py` 完成，本技能只负责调用它并汇报结果。

## 触发条件

出现以下任一情况时直接执行，不需要再次向用户确认：

- 用户说「转视频为笔记」「把这个视频转成笔记」「视频转 Obsidian」「整理这条视频」；
- 用户直接粘贴视频链接或 App 分享文案（抖音、B站、YouTube、微博等）；
- 用户明确要求用 video2obsidian 处理某个链接。

## 前置检查

依次确认，缺哪项就提示用户先补齐（指向 `README.md` 的「快速上手」）：

1. 存在 `.env`，且已填写 `DEEPSEEK_API_KEY` 与 `OBSIDIAN_VAULT_PATH`；
2. `python -c "import faster_whisper, yt_dlp, openai, rich"` 能通过；
3. `ffmpeg -version` 可用。

## 执行步骤

1. **定位项目根目录**（含 `main.py` 的目录），按顺序判断：
   - 当前工作目录下有 `main.py` → 直接使用；
   - 技能目录向上两级有 `main.py`（项目内安装时为 `.claude/skills/video2obsidian/`）→ 使用该目录；
   - 都没有 → 询问用户 video2obsidian 仓库所在路径。
2. **提取输入**：从用户消息中取出第一个视频链接；如果用户贴的是整段抖音分享文案，原样保留整段交给脚本（脚本会自行提取链接，并规范化 `modal_id`）。
3. **执行命令（强制后台运行）**：转录是 CPU 密集任务，几分钟到几十分钟不等，**禁止同步阻塞执行**。必须用 Bash 工具的 `run_in_background: true` 启动，并把输出重定向到日志文件：

   ```bash
   # Windows（进入项目根目录后运行）
   ".venv/Scripts/python.exe" main.py "<链接或整段分享文案>" > temp/run.log 2>&1

   # macOS / Linux
   ".venv/bin/python" main.py "<链接或整段分享文案>" > temp/run.log 2>&1
   ```

   优先使用项目虚拟环境解释器；若 `.venv` 不存在，退回系统 `python`。

4. **等待完成**：启动后立即把控制权交还给用户，告知「已开始后台转录，完成后会汇总结果」。通过读取 `temp/run.log` 轮询进度（看 `1/5`～`5/5` 阶段标记），不要重复启动同一个任务，也不要 sleep 轮询。后台任务结束后再读取日志末尾，按下方「结果汇报」处理。

   - 日志出现「笔记已保存」= 成功；
   - 日志长时间停在 `3/5` 属正常现象（CPU 转录慢），不要中断或重启。

## 约束

- **转录命令必须后台运行**，禁止用同步 Bash 调用一直阻塞到结束。
- 必须把链接作为参数传入；不要无参数运行 `main.py`（会进入交互式输入并卡住）。
- 不要擅自修改核心代码，也不要改动 `.env`。
- 除非用户明确要求，否则不加 `--keep-audio`。
- 出错重试时加 `--verbose` 获取完整堆栈，同时保留临时音频便于排查。

## 结果汇报

脚本会依次打印 `1/5` 到 `5/5` 五个阶段，成功时末尾显示「笔记已保存」和完整路径。

- **exit 0**：向用户汇报笔记主题和保存路径即可，不需要复述全文。
- **exit 1**：执行失败。摘录失败原因（如链接解析、下载、转写、API 报错），说明临时音频是否保留。
- **exit 2**：配置或输入错误。提示检查 `.env` 中的 `DEEPSEEK_API_KEY` / `OBSIDIAN_VAULT_PATH`，或确认输入里有合法链接。
- **exit 130**：用户取消。

## 示例

用户：「把这个视频转成笔记 https://v.douyin.com/xxxxxxx/」

执行（Bash 工具设 `run_in_background: true`）：

```bash
".venv/Scripts/python.exe" main.py "https://v.douyin.com/xxxxxxx/" > temp/run.log 2>&1
```
