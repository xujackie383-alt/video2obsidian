# douyin2obsidian

把一条抖音分享链接，自动变成一篇结构化的 Obsidian 笔记。

下载音频 → 本地离线转录 → DeepSeek 深度重构 → 按模板写入知识库 → 清理临时文件，全流程一条命令完成。

> 仅用于个人学习与内容整理。请遵守平台规则与著作权法，不要用于批量抓取或二次分发他人作品。

---

## 功能特点

- **一条链接搞定**：直接粘贴抖音分享文案（带一堆表情和口令的那种也行），自动识别其中的链接。
- **本地转录，音频不出本机**：使用 `faster-whisper` 离线识别，支持 CPU / GPU 自动判断。
- **AI 深度重构，不是机械摘要**：交给 DeepSeek 消化整篇内容后重写为连贯解读，而不是「观点 / 论据 / 金句」的模板填空。
- **长视频自动分段**：转录文本超过阈值时，先分段提炼要点，再整体整合成一篇。
- **Obsidian 原生格式**：无 YAML frontmatter、无 tags，标题 + 元数据行 + 正文 + 可折叠逐字稿。
- **失败可回溯**：中途出错会保留临时音频并打印路径；成功后才清理。
- **配置全走 `.env`**：API Key、知识库路径、模型选择都不进代码仓库。

---

## 工作流程

```text
抖音分享链接
      │
      ▼
① 提取 v.douyin.com 短链并跟随重定向
      │
      ▼
② yt-dlp 以最佳音质下载音频 → temp/
      │
      ▼
③ faster-whisper 离线转录为中文文本
      │
      ▼
④ DeepSeek (deepseek-chat) 深度理解并重构正文
      │
      ▼
⑤ 生成 Markdown 写入 Obsidian 知识库 → 清理 temp/
```

---

## 环境依赖

### 1. Python

- Python **3.10 及以上**（开发与测试环境为 3.12）。

### 2. ffmpeg（必需）

`yt-dlp` 需要 ffmpeg 处理音频流。没有它，部分视频的音频会下载失败或无法转封装。

**Windows**

任选一种：

```powershell
winget install --id Gyan.FFmpeg -e
```

或到 [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) 下载 release 压缩包，解压后把 `bin` 目录加入系统 `PATH`。

**macOS**

```bash
brew install ffmpeg
```

**Linux**

```bash
sudo apt install ffmpeg      # Debian / Ubuntu
sudo dnf install ffmpeg      # Fedora
```

安装后验证：

```bash
ffmpeg -version
```

> 脚本启动时若检测不到 ffmpeg 会给出黄色提示，但不会直接中断——只是下载失败的概率会变高。

### 3. Python 依赖

```bash
pip install -r requirements.txt
```

| 包 | 作用 |
| --- | --- |
| `yt-dlp` | 解析抖音链接并下载音频 |
| `faster-whisper` | 本地离线语音转录 |
| `openai` | 以 OpenAI 兼容协议调用 DeepSeek |
| `python-dotenv` | 加载 `.env` 配置 |
| `rich` | 终端进度条与格式化输出 |
| `requests` | 短链重定向解析 |

> 首次运行会自动下载 Whisper 模型（`base` 模型约 140 MB），之后走本地缓存。

---

## 配置

复制示例配置并填写：

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

`.env` 中最少需要改这两项：

```dotenv
DEEPSEEK_API_KEY=sk-你的真实key
OBSIDIAN_VAULT_PATH=D:/Obsidian/MyVault
```

### 配置项说明

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 无（必填） | 在 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 创建 |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 兼容网关可改 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 整理模型 |
| `DEEPSEEK_TIMEOUT` | `180` | 单次请求超时（秒） |
| `OBSIDIAN_VAULT_PATH` | 无（必填） | 知识库**绝对路径**，笔记直接写入该目录 |
| `WHISPER_MODEL` | `base` | `tiny` / `base` / `small` / `medium` / `large-v3` |
| `WHISPER_DEVICE` | `auto` | `auto` / `cpu` / `cuda` |
| `WHISPER_COMPUTE_TYPE` | `auto` | `auto` 时 GPU 用 `float16`、CPU 用 `int8` |
| `WHISPER_LANGUAGE` | `zh` | `auto` 为自动检测语言 |
| `WHISPER_DOWNLOAD_ROOT` | 空 | 模型缓存目录，空则用 HuggingFace 默认缓存 |
| `YTDLP_PROXY` | 空 | 如 `http://127.0.0.1:7890` |
| `YTDLP_COOKIES_FILE` | 空 | 需要登录态时指向导出的 `cookies.txt` |
| `TEMP_DIR` | `temp` | 临时音频目录，相对路径以项目根目录为基准 |
| `SUMMARY_MAX_INPUT_CHARS` | `12000` | 转录超过该长度时分段提炼 |

> `.env` 已被 `.gitignore` 忽略，不会被误提交。

---

## 使用

### 直接传参

```bash
python main.py "https://v.douyin.com/xxxxxxx/"
```

### 粘贴完整分享文案

分享文案里夹带的文字、表情、口令都不用处理：

```bash
python main.py "7.89 复制打开抖音，看看【某某的作品】...# 话题 https://v.douyin.com/xxxxxxx/"
```

Windows 下建议用双引号包裹，避免 `&` 等字符被 shell 解释。

### 交互输入

不带参数运行，按提示粘贴链接后回车：

```bash
python main.py
```

### 命令行选项

| 选项 | 说明 |
| --- | --- |
| `--keep-audio` | 成功后保留 `temp/` 中的音频文件 |
| `--verbose` | 出错时打印完整堆栈 |
| `--version` | 显示版本号 |

运行过程中的输出形如：

```text
1/5  解析链接
2/5  下载音频
3/5  语音转录
4/5  AI 深度重构
5/5  写入 Obsidian
```

完成后会打印笔记的完整保存路径。

---

## 生成的笔记长什么样

文件名取自提炼出的主题标题；同名文件已存在时自动追加 `(2)`、`(3)`，不会覆盖旧笔记。

```markdown
# 为什么大多数人做副业都失败了

> 原视频：[某某某的作品](https://www.douyin.com/video/7xxxxxxxxxxxxxxxxx) | 记录时间：2026-10-26 11:30

作者真正想说的并不是「副业难做」，而是大多数人把副业当成了一份更辛苦的主业……

> [!important] 关键前提
> 副业的第一目标不是赚钱，而是验证「有人愿意为你的能力付费」。

第二段继续展开论证，保持连贯叙述，不做机械分点……

## 原始逐字稿

> [!note]- 展开查看原文
> 大家好，今天想聊聊……
> （完整转写文本，方便人工对照与修改）
```

要点：

- **没有 YAML frontmatter，没有 tags**，标题直接是一级标题；
- 标题下的元数据行固定为 `> 原视频：[标题](链接) | 记录时间：YYYY-MM-DD HH:mm`；
- 正文是 AI 消化后的连贯解读，重要洞见用 `> [!tip]` / `> [!important]` / `> [!quote]` 高亮（全文不超过 3 处）；
- 末尾 `## 原始逐字稿` 用折叠 Callout 收纳完整转录稿。

---

## 项目结构

```text
douyin2obsidian/
├─ main.py                 CLI 入口：参数解析、流程编排、错误展示
├─ config.py               读取并校验 .env，产出 Settings
├─ core/
│  ├─ __init__.py          统一异常体系
│  ├─ downloader.py        链接识别、短链重定向、yt-dlp 音频下载
│  ├─ transcriber.py       faster-whisper 封装（设备/精度自动选择）
│  ├─ summarizer.py        DeepSeek 调用、分段提炼、结果解析与清洗
│  └─ vault_writer.py      Markdown 模板生成与知识库写入
├─ .env.example            配置示例
├─ .gitignore
├─ requirements.txt
├─ LICENSE                 MIT
└─ README.md
```

---

## 常见问题

**下载失败，提示需要登录或返回空信息**

抖音部分内容需要登录态。用浏览器导出 `cookies.txt`，在 `.env` 中设置 `YTDLP_COOKIES_FILE` 指向它。

**短链解析超时**

多半是网络问题。设置 `YTDLP_PROXY` 后重试；脚本在短链解析失败时会自动把原始链接直接交给 yt-dlp。

**ffmpeg 找不到**

确认 `ffmpeg -version` 在**新开的终端**里能执行（安装后需要重开终端让 `PATH` 生效）。

**转录很慢**

`base` 模型在 CPU 上处理 10 分钟音频通常需要 1–3 分钟。追求速度可换 `WHISPER_MODEL=small` + GPU；追求准确用 `medium` 或 `large-v3`。

**CUDA 初始化失败**

脚本会自动回退到 CPU 并给出提示。若想彻底避开，可在 `.env` 中固定 `WHISPER_DEVICE=cpu`。

**没有识别到有效语音**

纯音乐、无人声或音质过低时会主动报错。可换更大的模型重试。

**知识库路径报错**

`OBSIDIAN_VAULT_PATH` 必须是已存在的**绝对路径**，脚本会校验目录是否存在。

**笔记会放在库里的哪个目录**

直接放在 `OBSIDIAN_VAULT_PATH` 指向的知识库根目录下，不会额外创建子目录。

**临时音频去哪了**

成功时自动删除；失败或中断时会保留并在终端打印路径，方便排查。加 `--keep-audio` 可强制保留。

---

## 免责声明

本项目仅供个人学习、研究与个人知识管理使用。使用者应自行确保：

- 仅处理自己有权访问的内容；
- 不进行批量抓取、爬取或对平台造成压力；
- 不将生成的转录稿与笔记用于商业传播或侵犯他人著作权。

因使用本工具产生的一切后果由使用者自行承担。

---

## License

[MIT](LICENSE)
