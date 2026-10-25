# MiniMax 语音参数与接口

资料：用户提供的同步合成 OpenAPI，以及 [同步语音合成](https://platform.minimax.cn/docs/api-reference/speech-t2a-http)、[上传复刻音频](https://platform.minimax.cn/docs/api-reference/voice-cloning-uploadcloneaudio)、[音色复刻](https://platform.minimax.cn/docs/api-reference/voice-cloning-clone)。核对日期 2026-10-25。

## 合成

`POST https://api.minimax.cn/v1/t2a_v2`，Bearer 认证、JSON 请求。

| 参数 | 用法 |
| --- | --- |
| `model` | 默认 `speech-2.8-hd`；可按需选择 `speech-2.8-turbo` |
| `text` | 少于 10000 字符；换行标记段落；保留用户文本 |
| `voice_setting.voice_id` | 默认从 MINIMAX_VOICE_ID 读取 |
| `voice_setting.speed` | 0.5–2，默认 1 |
| `voice_setting.vol` | 大于 0 且不超过 10，默认 1 |
| `voice_setting.pitch` | 整数 -12–12，默认 0 |
| `voice_setting.emotion` | 本客户端支持 happy/sad/angry/fearful/disgusted/surprised/calm；默认省略由模型判断 |
| `audio_setting.sample_rate` | 8000/16000/22050/24000/32000/44100，默认 32000 |
| `audio_setting.bitrate` | MP3 使用 32000/64000/128000/256000，默认 128000 |
| `audio_setting.format` | 客户端支持 mp3/wav/flac/pcm；PCM 为裸音频，应保留采样率与声道元数据 |
| `audio_setting.channel` | 1 或 2，默认 1 |
| `output_format` | API 的输出传输形式 hex/url，不是文件格式；客户端固定 hex |
| `stream` | 客户端固定 false；不接受流式设置 |
| `subtitle_enable` | `--subtitles` 开启；非流式字幕链接在 data.subtitle_file |

官方文档还列出 Opus 和 μ-law 等格式，但本客户端未实现对应封装参数。不要把模型可选值等同于本脚本已支持的功能。文档对 `fluent` 的模型支持表述不够一致，`whisper` 不支持 2.8，本客户端不暴露这两项。

## 停顿、发音与语气

- 停顿：`前一句。<#0.5#>后一句。`，0.01–99.99 秒、最多两位小数；放在可发音文本之间，不连续放多个标记。
- 2.8 的语气标签例如 `(laughs)`、`(chuckle)`、`(breath)`、`(sighs)`、`(coughs)`、`(crying)`。只按文案表现需要加入，不自动在每句插入。
- 拼音修正：`处理/(chu3)(li3)`；英文或词替换：`危险/dangerous`。后者会改变实际朗读内容，必须符合用户意图。

高级选项写入 UTF-8 JSON 后通过 `--settings` 传入，例如：

```json
{
  "pronunciation_dict": {"tone": ["处理/(chu3)(li3)"]},
  "language_boost": "Chinese",
  "text_normalization_mode": "quality",
  "subtitle_type": "sentence"
}
```

客户端允许的高级顶层字段仅为 `pronunciation_dict`、`language_boost`、`text_normalization_mode`、`voice_modify`、`subtitle_type`、`aigc_watermark`。高级字段内部值按官方 schema 校验，未知值可能由服务器拒绝。

- `language_boost` 可用 `auto`、`Chinese`、`Chinese,Yue` 等受支持语言；不要将任意语言名当成合法值。
- `text_normalization_mode=basic|quality`；quality 对 2.8 非流式请求生效，可能增加延迟。不要使用已废弃的 `voice_setting.text_normalization`。
- `subtitle_type=sentence|word`；必须同时启用字幕。客户端不支持 word_streaming。字幕时间单位是毫秒，不是秒，原文件是 JSON，不是 SRT。
- `voice_modify.pitch/intensity/timbre`：整数 -100–100，区别于 `voice_setting.pitch`。需要保留克隆原音色时不设置。
- `voice_modify.sound_effects`：spacious_echo/auditorium_echo/lofi_telephone/robotic，每次一种。
- `aigc_watermark` 为布尔值，控制末尾音频节奏标识，不作为绕过平台标识的保证。

混合音色需 `timbre_weights`（最多 4 个，weight 1–100）及相应 voice_id 设置；本客户端专注单一克隆音色，未开放混合音色选项。流式还需正确处理最终事件是否包含整段音频，不能直接重复拼接。本客户端不实现这两条路径。

## 复刻

先上传 `/files/upload`，表单 `purpose=voice_clone`、`file=文件`；响应 `file.file_id` 是整数。然后向 `/voice_clone` 发送 `file_id` 与唯一 `voice_id`。

可选 `need_noise_reduction`、`need_volume_normalization`；要试听需同时提供 `text`（不超过1000字符）和 `model`。当前脚本支持这些字段。

官方还支持 `clone_prompt`（小于 8 秒示例音频及准确 prompt_text）、`text_validation`、`accuracy`。本客户端没有实现这组高级校验流程；不要把未经核实的转写文本当成准确参考。提供 clone_prompt 时两个子字段都必须齐全。

## 返回与错误

HTTP 200 仍需检查 base_resp.status_code。合成 status=2 才完成，data 可能为空。音频 hex 用 `bytes.fromhex` 解码；输出路径、实际格式及扩展名一致。

保留 trace_id 与 extra_info，关注 usage_characters（计费字符）、usage_voice_count（音色首次使用计费数量）。不要用 word_count 推断账单。下载 URL 可能过期（合成 URL 文档标注 24 小时），及时保存所需产物。客户端默认 hex 不依赖音频下载链接。

常见失败：1002 限流、1004/2049 鉴权、1008 余额、2013 参数、2038 复刻权限。账号认证及音色访问权限需在实际账号中满足；不通过自动改模型或音色隐藏失败。
