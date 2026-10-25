---
name: minimax-speech
description: 使用 MiniMax 将文本、文案或脚本合成为配音，默认使用已复刻音色和 speech-2.8-hd；也支持上传参考音频创建新音色。用于语音合成、朗读、配音和音色克隆，不用于音频转写或歌曲翻唱。
---

# MiniMax 语音合成与音色复刻

日常优先复用已存在的音色生成配音，不重新克隆。默认模型为 `speech-2.8-hd`；当前音色为 `video_audio01_5adc3d9c2bea`，从项目根目录 `.env` 的 `MINIMAX_VOICE_ID` 读取。用户指定其他音色或模型时使用命令行覆盖。

## 配置与脚本定位

客户端为本技能目录的 `scripts/client.py`。从加载器提供的本文件位置定位脚本，不依赖执行时工作目录。Python 依赖见 `requirements.txt`；克隆本地音频还需要 `ffprobe`。安装依赖：

```powershell
python -m pip install -r .claude/.skills/minimax-speech/requirements.txt
```

脚本默认根据自身位置找到项目根目录 `.env`；迁移到其他目录或服务器时，用全局选项 `--env-file /绝对路径/.env`（放在 `tts` / `clone` 前）。进程环境变量优先于文件。

- `MINIMAX_API_KEY`：用户提供的 MiniMax 密钥；不得打印或写入请求记录。
- `MINIMAX_BASE_URL`：`https://api.minimax.cn/v1`。客户端限定这一已核实地址，不复用 OpenAI 的第三方基址。
- `MINIMAX_MODEL`：`speech-2.8-hd`。
- `MINIMAX_VOICE_ID`：已复刻音色 ID。

缺少密钥时让用户通过本地 `.env` 配置；不要将示例中的 `<token>` 当作密钥。不要覆盖已有 OpenAI 配置。

## 日常合成（主流程）

1. 保留用户指定的完整文案，不擅自改写；长文案、换行或特殊符号通过 UTF-8 文件输入。确定音色、语速和输出位置；没有特别要求时用默认音色、原速、原音调、自动情绪。
2. 默认输出 MP3、32 kHz、128 kbps、单声道。需要不同情绪、停顿、发音、字幕时读取 [参数说明](references/api.md)。
3. 以下示例从项目根目录执行；其他位置使用脚本的绝对路径：

```powershell
python .claude/.skills/minimax-speech/scripts/client.py tts --text-file output/narration.txt --output output/narration.mp3
python .claude/.skills/minimax-speech/scripts/client.py tts --text "今天是不是很开心呀(laughs)，当然了！" --emotion happy --speed 1 --output output/happy.mp3
```

`--voice-id`、`--model` 可覆盖默认值；`--vol`、`--pitch` 调整音量与音调。`--subtitles` 请求字幕，返回链接位于输出 JSON 和元数据；需要字幕文件时及时下载到音频旁，字幕下载失败不能掩盖已经完成的音频。`--settings` 接收高级参数 JSON。

用 `--dry-run` 检查最终请求，不发送网络请求、不收费。实际调用前拒绝已有输出路径，避免付费后发现不能保存。每次选择新文件名。

4. 成功必须同时满足 HTTP 成功、`base_resp.status_code=0`、`data.status=2` 且包含有效 hex 音频。客户端将 hex 解码为二进制，不能按 Base64 解码。保存同名 `.mp3.json` 等元数据，含请求、trace_id 和用量，不含密钥或音频 hex。
5. 用 `ffprobe` 检查成品可解码、时长和格式，展示可播放的本地音频。接口成功不代表音色相似度已通过听感验证；听不出或没有试听时不要声称完美复刻。

本客户端使用非流式输出，文本限 1–9999 字符。超过 3000 字符时，官方推荐流式；本客户端没有实现流式，不应假装支持。可按用户认可的自然段分段生成并交付片段，或按官方文档另行实现流式；不要默默截断、改写或将多个文件直接当一个完整成品。

## 创建新音色（按需）

只有用户要求克隆新声音时才执行。MP3/M4A/WAV，10–300 秒，最多 20 MB；客户端会用 ffprobe 检查。源音频应尽量是单人清晰声音，噪声、混响和分离伪影会影响相似度。

```powershell
python .claude/.skills/minimax-speech/scripts/client.py clone --audio "input/reference.mp3" --voice-id video_narrator_20261025 --output-dir output/clone-new --normalize --demo-text "你好，这是新音色的试听。"
```

音色 ID 必须唯一、8–256 字符、字母开头、字母或数字结尾，中间允许字母、数字、下划线、连字符。输出目录必须是新目录。复刻不自动替换默认音色；用户要求设为默认后再更新 `.env` 的 `MINIMAX_VOICE_ID`。

上传使用 `purpose=voice_clone` 和标准 multipart 文件字段，让 requests 自动生成 Content-Type/boundary。客户端先保存 `upload.json`，再调用 `/voice_clone`；请求保存在 `request.json`，成功结果保存在 `result.json`。上传成功而复刻失败时，可从记录取出 file_id，以 `clone --file-id ID` 续接，使用新输出目录。音色 ID 是否已被创建不确定时先查询，不能盲目重试或换 ID 重复付费。

`--noise-reduction` 默认关闭，`--normalize` 默认关闭；仅在需要时开启。`--demo-text` 会产生试听合成费用；默认不生成试听。试听链接是返回结果，不等于文件已下载。

复刻音色 7 天内未正式调用会被删除；复刻附带试听与正式 `/t2a_v2` 合成分开。音色首次正式使用可能产生音色费用，读取 `usage_voice_count`，不要承诺固定单价。

## 失败处理与已验证范围

无自动重试：超时后服务端可能已处理；保留记录并说明状态。鉴权、余额、音色权限、参数或内容审核失败应报告真实错误，不替换音色、不循环发送。合成失败后可能留下空的输出/元数据占位文件，用于标识该请求状态不确定，不把它们交付为成品。

2026-10-25 已在当前账号完成：上传约 149 秒参考音频、创建上述音色、复刻试听、使用 `speech-2.8-hd` 正式合成 MP3（happy 情绪及 laughs 标签）。正式请求返回 status_code=0、status=2、usage_voice_count=1。其他格式、字幕、语言、长文本与高级参数没有逐项线上验证。

详细参数及官方来源：[references/api.md](references/api.md)。
