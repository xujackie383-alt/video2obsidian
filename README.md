<div align="center">

# video2obsidian

**把一条视频链接，变成一篇可以放进知识库的 Obsidian 笔记。**

本地转写 · AI 深度重构 · 免登录解析 · 一键落库

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB)
![License](https://img.shields.io/badge/License-MIT-green)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey)
![Claude Code Skill](https://img.shields.io/badge/Claude%20Code-Skill-blueviolet)

</div>

> 仅用于个人学习与内容整理。请遵守平台规则与著作权法，不要用于批量抓取或二次分发他人作品。

---

## 以 Claude Code Skill 模式运行

本项目已封装为 **Claude Code Agent Skill**（`.claude/skills/video2obsidian/`）。在仓库目录中打开 Claude Code，直接说一句「把这个视频转成笔记」并附上链接，Agent 就会自动执行：

```bash
python main.py "<视频链接>"
```

**一句话调用示例**

> 把这个视频转成笔记 https://v.douyin.com/xxxxxxx/

触发词：「转视频为笔记」「把这个视频转成笔记」「视频转 Obsidian」「整理这条视频」；也可以直接粘贴视频链接或 App 分享文案，Agent 会自动识别。完成后会汇报笔记主题与保存路径，无需手动搬运。

**安装到用户级（可选）**：默认仅在项目内生效；若希望任意目录都能调用，把技能目录复制到用户技能目录：

```powershell
# Windows PowerShell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills" | Out-Null
Copy-Item -Recurse .claude\skills\video2obsidian "$env:USERPROFILE\.claude\skills\"
```

```bash
# macOS / Linux
mkdir -p ~/.claude/skills
cp -r .claude/skills/video2obsidian ~/.claude/skills/
```

> Skill 模式仍然复用同一套 `main.py` 和 `.env` 配置，首次使用前请先完成下方「快速上手」中的环境准备（Python 依赖、FFmpeg、`.env`）。

---

## 核心特性

- **一键流水线**：粘贴视频链接或整段分享文案，下载 → 转写 → 重构 → 落库 → 清理，一条命令全部完成。
- **Agent Skill 封装**：自带 Claude Code 技能声明，一句「把这个视频转成笔记」即可自动执行，无需记命令。
- **本地离线转写**：使用 `faster-whisper` 在本机识别语音，音频文件不上传；支持 CPU / CUDA 自动选择。
- **AI 深度重构**：交给 DeepSeek 通读全文后重写为连贯解读，而不是「观点 / 论据 / 金句」的模板化摘要；长视频自动分段提炼再整合。
- **免登录解析**：抖音短链自动跟随重定向拿到真实 `video_id`，通过公开解析接口获取无水印直链，不需要 Cookie 或账号登录。
- **Obsidian 直连**：按固定模板生成 Markdown 并直接写入知识库根目录，无需手动搬运。
- **多平台支持**：抖音、B站、YouTube、微博等 `yt-dlp` 可解析的平台；`v.douyin.com`、`b23.tv`、`youtu.be` 等短链无需手动展开。
- **失败可回溯**：中途出错会保留临时音频并打印路径；只有成功后才清理。

## 支持平台

| 平台 | 下载方式 | 登录 / Cookie |
| --- | --- | --- |
| 抖音 | 公开解析接口取无水印直链 | 不需要 |
| B站、YouTube、微博等 | `yt-dlp` 原生解析 | 不需要（会员 / 年龄限制内容暂不支持） |

> 链接提取不限定域名：分享文案里只要含有合法的 `http://` 或 `https://` 地址，就会取第一个交给后续流程。

---

## 快速上手

### 1. 克隆项目并准备 Python 环境

需要 **Python 3.10 及以上**（开发与测试环境为 3.12）。

```bash
git clone https://github.com/<your-name>/video2obsidian.git
cd video2obsidian

python -m venv .venv
```

激活虚拟环境：

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# macOS / Linux
source .venv/bin/activate
```

### 2. 安装 FFmpeg

FFmpeg 用于处理音频流，以及从抖音视频中提取音轨。

**Windows（winget）**

```powershell
winget install --id Gyan.FFmpeg -e
```

**macOS（Homebrew）**

```bash
brew install ffmpeg
```

**Linux**

```bash
sudo apt install ffmpeg      # Debian / Ubuntu
sudo dnf install ffmpeg      # Fedora
```

安装后重新打开终端，确认可用：

```bash
ffmpeg -version
```

### 3. 安装 Python 依赖

```bash
python -m pip install -U pip
pip install -r requirements.txt
```

| 依赖 | 作用 |
| --- | --- |
| `yt-dlp` | 解析 B站 / YouTube 等平台的视频链接并下载音频 |
| `faster-whisper` | 本地离线语音转写 |
| `openai` | 以 OpenAI 兼容协议调用 DeepSeek |
| `python-dotenv` | 加载 `.env` 配置 |
| `rich` | 终端进度条与格式化输出 |
| `requests` | 抖音短链重定向与直链流式下载 |

### 4. 配置 `.env`

复制示例配置：

```powershell
# Windows
copy .env.example .env
```

```bash
# macOS / Linux
cp .env.example .env
```

打开 `.env`，至少填写下面两项：

```dotenv
DEEPSEEK_API_KEY=sk-你的DeepSeek密钥
OBSIDIAN_VAULT_PATH=D:/Obsidian/MyVault
```

- `DEEPSEEK_API_KEY`：在 [DeepSeek 开放平台](https://platform.deepseek.com/api_keys) 创建。
- `OBSIDIAN_VAULT_PATH`：Obsidian 知识库的**绝对路径**，目录必须已存在；笔记会直接写入该目录。

> `.env` 已被 `.gitignore` 忽略，不会进入版本库。

### 5. 运行

**常规视频 URL**

```bash
# B站
python main.py "https://www.bilibili.com/video/BVxxxxxxxxxx"

# YouTube
python main.py "https://www.youtube.com/watch?v=xxxxxxxxxxx"
```

**抖音分享文案（长文本）**

直接把 App 里复制的内容整段粘贴进来，表情、口令和多余文字都不用清理：

```bash
python main.py "7.89 复制打开抖音，看看【某某的作品】为什么学历越来越高…#工作 #学历 https://v.douyin.com/xxxxxxx/"
```

**交互式输入**

不带参数运行，按提示粘贴链接后回车：

```bash
python main.py
```

Windows 下建议用双引号包裹参数，避免 `&` 等字符被 shell 解释。

---

## 工作流原理

```text
视频分享链接（抖音 / B站 / YouTube / 微博 …）
        │
        ▼
① 从输入文本中提取第一个 HTTP/HTTPS 链接
   （抖音短链自动跟随 302，拿到真实 video_id）
        │
        ▼
② 获取媒体
   抖音：公开解析接口 → 无水印直链 → requests 流式下载
   其他：yt-dlp 以最佳音质下载
   └─→ ffmpeg 提取 16 kHz 单声道音频 → temp/
        │
        ▼
③ faster-whisper 本地离线转写
        │
        ▼
④ DeepSeek 深度理解并重构正文
   （超过阈值时先分段提炼，再整体整合）
        │
        ▼
⑤ 生成 Markdown 写入 Obsidian 知识库 → 清理 temp/
```

1. **链接提取**：用正则从任意文本中取第一个合法 URL，并去掉末尾的中英文标点；抖音的 `modal_id` 链接会规范化为 `/video/<id>`。
2. **媒体下载**：抖音分支先跟随短链重定向，再依次请求公开解析接口（主接口失败时自动切换备用接口），拿到无水印直链后用 `requests` 流式下载，最后用 FFmpeg 提取音频；其他平台直接交给 `yt-dlp`。
3. **语音转写**：`faster-whisper` 通过 VAD 过滤静音段，按 `WHISPER_LANGUAGE` 指定的语言输出带标点文本。
4. **AI 重构**：DeepSeek 消化整篇内容后重写为连贯解读；转录长度超过 `SUMMARY_MAX_INPUT_CHARS` 时，先分段提炼要点，再整合成一篇。
5. **写入知识库**：按模板生成 Markdown，文件名取自提炼出的主题标题；同名文件自动追加 `(2)`、`(3)`，不会覆盖旧笔记。

---

## 命令行选项

| 选项 | 说明 |
| --- | --- |
| `--keep-audio` | 成功后保留 `temp/` 中的音频文件 |
| `--verbose` | 出错时打印完整堆栈 |
| `--version` | 显示版本号 |

运行时会依次显示 5 个阶段，完成后打印笔记的完整保存路径：

```text
1/5  解析链接
2/5  下载音频
3/5  语音转录
4/5  AI 深度重构
5/5  写入 Obsidian
```

---

## 配置项

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | 无（必填） | DeepSeek API Key |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | 兼容网关可修改 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 内容整理模型 |
| `DEEPSEEK_TIMEOUT` | `180` | 单次请求超时（秒） |
| `OBSIDIAN_VAULT_PATH` | 无（必填） | 知识库绝对路径，笔记直接写入该目录 |
| `WHISPER_MODEL` | `base` | `tiny` / `base` / `small` / `medium` / `large-v3` |
| `WHISPER_DEVICE` | `auto` | `auto` / `cpu` / `cuda` |
| `WHISPER_COMPUTE_TYPE` | `auto` | `auto` 时 GPU 用 `float16`、CPU 用 `int8` |
| `WHISPER_LANGUAGE` | `zh` | `auto` 为自动检测语言 |
| `WHISPER_DOWNLOAD_ROOT` | 空 | 模型缓存目录，空则使用 HuggingFace 默认缓存 |
| `YTDLP_PROXY` | 空 | 代理地址，如 `http://127.0.0.1:7890` |
| `TEMP_DIR` | `temp` | 临时音频目录，相对路径以项目根目录为基准 |
| `SUMMARY_MAX_INPUT_CHARS` | `12000` | 转录超过该长度时分段提炼 |

---

## 生成的笔记

文件名取自 AI 提炼出的主题标题；同名文件已存在时自动追加序号，不会覆盖旧内容。

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

模板约定：

- 没有 YAML frontmatter，也没有 tags，标题直接是一级标题；
- 元数据行固定为 `> 原视频：[标题](链接) | 记录时间：YYYY-MM-DD HH:mm`；
- 正文是 AI 消化后的连贯解读，重要洞见用 `> [!tip]` / `> [!important]` / `> [!quote]` 高亮（全文不超过 3 处）；
- 末尾用折叠 Callout 收纳完整逐字稿。

---

## 项目结构

```text
video2obsidian/
├─ .claude/
│  └─ skills/video2obsidian/
│     ├─ SKILL.md          技能声明：触发条件、调用方式与结果汇报
│     └─ skill.json        技能清单：名称、版本、入口命令、依赖
├─ main.py                 CLI 入口：参数解析、流程编排、错误展示
├─ config.py               读取并校验 .env，产出 Settings
├─ core/
│  ├─ __init__.py          统一异常体系
│  ├─ downloader.py        链接提取、抖音直链解析、音频下载与提取
│  ├─ transcriber.py       faster-whisper 封装（设备 / 精度自动选择）
│  ├─ summarizer.py        DeepSeek 调用、分段提炼、结果解析与清洗
│  └─ vault_writer.py      Markdown 模板生成与知识库写入
├─ .env.example            配置示例
├─ .gitignore
├─ requirements.txt
├─ LICENSE                 MIT
└─ README.md
```

---

## 注意事项

- **首次运行会下载 Whisper 权重**：`base` 模型约 140 MB，之后从本地缓存加载；`medium`、`large-v3` 体积更大。若访问 HuggingFace 缓慢，可通过 `HF_ENDPOINT` 指向可用镜像，或用 `WHISPER_DOWNLOAD_ROOT` 指定缓存目录。
- **抖音依赖第三方公开解析接口**：项目本身不实现抖音签名或登录逻辑，而是请求公开解析服务获取无水印直链（内置主备接口自动切换）。这些服务的可用性、限流和返回格式不受本项目控制；分享链接会发送给对应服务，介意的话请改用其他平台链接或自行部署解析服务。
- **FFmpeg 建议安装**：缺少 FFmpeg 时，抖音分支会退化为直接使用视频文件转写，`yt-dlp` 对部分格式也可能下载失败。
- **PyAV 版本已固定**：`requirements.txt` 中约束 `av>=14,<19`。PyAV 19 移除了 `metadata_errors` 参数，而当前 `faster-whisper` 仍会传入，升级会导致转录启动失败。
- **语音数据本地处理，文本会发往 DeepSeek**：音频转写在本机完成；转写文本会发送给 DeepSeek 用于生成笔记，请留意内容隐私。
- **CUDA 需要完整运行库**：`WHISPER_DEVICE=auto` 检测到 NVIDIA 显卡后会尝试 CUDA；若缺少 cuBLAS / cuDNN，会出现 `cublas64_12.dll` 相关错误，此时设置 `WHISPER_DEVICE=cpu`，或安装 CUDA 12 运行库。
- **笔记写入知识库根目录**：不会创建额外子目录；临时音频在成功时自动清理，失败或中断时保留并打印路径。

---

## 常见问题

**下载失败，提示需要登录或返回空信息**

抖音链接由公开解析接口取直链，不需要登录 Cookie；若接口临时不可用，脚本会依次尝试备用接口，仍失败时请稍后重试。B站会员视频、YouTube 年龄限制视频等需要登录态的内容暂不支持。

**短链解析超时**

抖音短链解析失败时，脚本会自动把原始链接交给解析接口。若属于普遍网络问题，可设置 `YTDLP_PROXY` 后重试。

**输入里没有可识别的链接**

脚本只提取第一个合法的 `http://` 或 `https://` 地址。请确认分享文案中包含完整链接，而不是只有口令或纯文字。

**ffmpeg 找不到**

确认 `ffmpeg -version` 能在**新开的终端**里执行（安装后需要重开终端让 `PATH` 生效）。

**转录很慢**

`base` 模型在 CPU 上处理 10 分钟音频通常需要 1–3 分钟。追求速度可换 `WHISPER_MODEL=small` 并启用 GPU；追求准确度可用 `medium` 或 `large-v3`。

**没有识别到有效语音**

纯音乐、无人声或音质过低时会主动报错。可换更大的模型重试。

**知识库路径报错**

`OBSIDIAN_VAULT_PATH` 必须是已存在的**绝对路径**，脚本启动时会校验目录是否存在。

**临时音频去哪了**

成功时自动删除；失败或中断时保留并在终端打印路径。加 `--keep-audio` 可强制保留。

---

## 免责声明

本项目仅供个人学习、研究与个人知识管理使用。使用者应自行确保：

- 仅处理自己有权访问的内容；
- 不进行批量抓取、爬取或对平台造成压力；
- 不将生成的转录稿与笔记用于商业传播或侵犯他人著作权。

因使用本工具产生的一切后果由使用者自行承担。

---

## License

本项目基于 [MIT License](LICENSE) 开源。

Copyright (c) 2026 video2obsidian contributors
