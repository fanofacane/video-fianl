# 参数参考

核对日期：2026-10-25。以下面向 `gpt-image-2.5-flare`。资料来源：[生成接口](https://developers.openai.com/api/reference/resources/images/methods/generate)、[编辑接口](https://developers.openai.com/api/reference/resources/images/methods/edit)、[生成指南](https://developers.openai.com/api/docs/guides/image-generation)、[Responses 工具](https://developers.openai.com/api/docs/guides/tools-image-generation)。

## Images API

官方基址：`https://api.openai.com/v1`。认证：`Authorization: Bearer` 加环境中的 API 密钥。

| 参数 | 值与限制 | 使用说明 |
| --- | --- | --- |
| `model` | `gpt-image-2.5-flare` | 本技能显式指定；固定快照为 `gpt-image-2.5-flare-2026-09-08` |
| `prompt` | 文本，最长 32,000 字符 | 描述主体、构图、风格、文字和保留约束 |
| `size` | `auto` 或 `WIDTHxHEIGHT` | 受下述尺寸约束限制 |
| `quality` | `auto`、`low`、`medium`、`high`、`xhigh`、`max` | API 默认 `auto`；更高档需评估延迟与成本 |
| `background` | `auto`、`opaque`、`transparent` | 默认 `auto`；透明必须搭配 PNG/WebP |
| `output_format` | `png`、`jpeg`、`webp` | 默认 PNG；返回内容需 Base64 解码 |
| `output_compression` | 0–100 | 仅 JPEG/WebP；生成接口默认 100，不用于 PNG；不代表文件大小百分比保证 |
| `n` | 整数 1–10 | 本技能默认 1；保存全部返回图片 |
| `moderation` | `auto`、`low` | 默认 `auto`，不为解决拒绝而自动修改 |
| `stream` | 布尔值 | 默认 false；开启后按事件消费，不能当普通 JSON 处理 |
| `partial_images` | 整数 0–3 | 用于流式中间图；0 不请求中间图，最终图可能先于全部中间图完成 |
| `safety_identifier` | 最多 128 字符 | 面向终端用户的应用可提供稳定匿名标识；不发明或传入明文个人信息 |

### 尺寸约束

宽高都必须是 16 的倍数；长边不超过 3840；长短边之比不超过 3；总像素介于 655,360 与 8,294,400。高于 `2560x1440` 的分辨率属实验范围。不要只检查长边而忽略总像素。

| 用途 | 合法示例 |
| --- | --- |
| 方形素材 | `1024x1024` |
| 横版 / 竖版 | `1536x1024` / `1024x1536` |
| 16:9 / 9:16 | `1536x864` / `864x1536` |
| 2K 方形 | `2048x2048`（实验范围） |
| 4K 横版 / 竖版 | `3840x2160` / `2160x3840`（实验范围） |

例如 `1920x1080` 的高度不是 16 的倍数，不能直接传入；`512x512` 像素不足。用户必须得到某个不支持的最终尺寸时，先解释原生生成限制，再根据用户需求裁剪或缩放，区分原生与后处理尺寸。

### 编辑输入

`POST /images/edits` 支持参考图及可选遮罩。官方指南包含 SDK `image` 文件上传示例，接口参考也提供 JSON `images` 引用格式。按所选传输方式构造请求，不能混成同一套字段。

- JSON：`images` 是最多 16 个图像引用组成的数组，每项提供 `image_url`（完整 URL 或 Base64 data URL）或 `file_id`。不要同时给同一项两种来源。
- SDK 文件上传：`image` 接受输入文件或文件列表，`mask` 为可选遮罩文件；使用支持该调用形式的 OpenAI SDK。
- JSON `mask` 使用单个图像引用对象。遮罩应包含 alpha，与第一张输入图保持相同尺寸；为避免格式差异，将原图和遮罩准备成同尺寸 PNG，均小于 50 MB。
- alpha=0 标识需要编辑的位置；不透明位置表示保留意图。提示词仍需说明期望的完整结果。遮罩不保证像素级锁定。
- `input_fidelity`：参考页只明确列出其他模型的支持情况，没有明确给出 Flare 的可调支持。本技能省略此参数；不能把其他模型的设置推断为 Flare 能力。

### 返回与不使用的字段

非流式 Images 响应从 `data[*].b64_json` 解码；保留 `usage`（若返回）用于统计。不要打印整段 Base64 或将其当作 URL。扩展名应跟随实际输出格式。

不发送旧接口的 `response_format`、`style`、`user`，不使用 variations 端点来模拟参考图编辑。风格放在提示词，用户标识使用 `safety_identifier`。`seed`、`steps`、`cfg_scale`、`negative_prompt`、`aspect_ratio` 不是本技能确认支持的参数。

## Responses API 的参数位置

| 位置 | 参数及作用 |
| --- | --- |
| 顶层 `model` | 支持图像工具的主模型，官方指南示例使用 `gpt-6-astra`；不能在这里放 Flare |
| 顶层 `input` | 用户文本及图像上下文；图片可用 URL、data URL 或文件 ID |
| `tools[]` | `type: image_generation`，其 `model` 显式设为 `gpt-image-2.5-flare` |
| 图像工具内 | `size`、`quality`、`background`、`output_format`、`output_compression`、`partial_images` 等已确认输出选项 |
| 工具内 `action` | `auto`（默认）、`generate` 或 `edit`；强制编辑需要输入图 |
| 顶层 `previous_response_id` | 延续上一轮对话；后续请求仍声明工具和图像模型 |
| 顶层 `stream` | 开启流式事件；`partial_images` 留在图像工具内 |
| 顶层 `safety_identifier` | 匿名终端用户标识，不放进图像工具 |

不要把 Images 的 `n` 或 `prompt` 原样搬进 Responses 图像工具；提示文本放在 `input`。遍历 `output`，只对 `type=image_generation_call` 且包含有效 `result` 的项解码。没有图像调用结果时不得报告图片生成成功。

## 成本与等待

尺寸、质量、参考图和中间图会影响消耗。Responses 还包含主模型用量。请求可能耗时数分钟，应使用足够的客户端超时；超时不等于服务端未执行。费率另见[官方定价](https://developers.openai.com/api/docs/pricing#image-generation)，本技能不固定每张图片价格。
