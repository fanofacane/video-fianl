---
name: openai-image-25
description: 使用 OpenAI GPT Image 2.5 生成或编辑图片，默认 gpt-image-2.5-flare。适用于文生图、参考图改图、局部编辑、透明背景素材，以及图片 API 参数配置；不用于视频生成。
---

# GPT Image 2.5 图像生成与编辑

默认模型为 `gpt-image-2.5-flare`，每次请求显式指定；不依赖服务端默认值，不自动换成其他模型。需要固定版本且用户同意时，可用 `gpt-image-2.5-flare-2026-09-08`。官方资料核对日期：2026-10-25。

## 工作方式

1. 从需求确定主体、用途、构图、尺寸、背景、输出格式，以及必须保留的文字或参考图细节。编辑前先查看输入图，区分必须保留与允许修改的内容。
2. 单次生成或编辑优先 Images API；需连续对话改图时使用 Responses API。参数范围与接口差异见 [参数参考](references/parameters.md)，具体请求见 [调用示例](references/examples.md)。
3. 使用当前环境允许的调用工具。只有工具实际暴露模型选择时才能声明使用 Flare；不可向不支持的工具传入虚构参数，也不可声称本技能能改变宿主内置图片工具的模型。需精确指定模型时，使用允许的官方 API 调用路径。
4. API 配置来自环境变量或项目根目录的本地 `.env`：`OPENAI_API_KEY` 提供密钥，`OPENAI_BASE_URL` 提供接口基址。本项目配置为用户指定的第三方兼容接口 `https://hk.ergouzi.life/v1`，不是 OpenAI 官方域名；本文官方参数是否全部被该服务支持，需实际调用验证，不能预先承诺。密钥不写进技能、请求示例或日志；本项目按用户明确要求跟踪根目录 `.env`。模型无权限、额度不足、参数不支持时报告真实错误，不静默降级或循环重试。网络超时后结果可能未知，先说明状态再决定是否重发，避免重复计费。
5. 保存解码后的图片，文件扩展名与 `output_format` 一致。检查实际尺寸、主体、文字和边缘；返回成品路径或预览，并说明实际使用的模型与关键参数。没有执行真实请求时明确说明，不把示例当作生成成功。

## 默认选择

- 未指定参数时：`model=gpt-image-2.5-flare`、`n=1`、`quality=auto`、`size=auto`、`output_format=png`、`background=auto`。其中模型和数量是本技能约定。
- 用户要草稿时可用 `quality=low`；成品按需求选 `high`、`xhigh` 或 `max`，不把最高档自动当成必需条件。
- 指定宽高比时转换为合法像素尺寸，例如 16:9 使用 `1536x864`，9:16 使用 `864x1536`。不传 `aspect_ratio`，不通过拉伸成品冒充目标比例。
- 风格、负面约束、镜头和排版写入 `prompt`；不要发明 `negative_prompt`、`seed`、`steps`、`cfg_scale` 等未确认参数。

## 透明背景与去背景

用户要求透明底、抠图、贴纸或独立素材时，显式设置 `background="transparent"`，输出 PNG（默认）或 WebP。JPEG 不支持透明度；用户同时要求 JPEG 与透明时说明冲突并确认优先项。

提示词还应描述独立主体、完整轮廓、主体周围留白，以及是否保留投影。要求透明 alpha 背景，避免生成棋盘格、白底或地面作为背景。已有图片去背景应使用编辑接口，明确保留身份、颜色、构图及所需细节。

交付前检查 alpha 通道是否存在且包含实际透明像素；仅将 RGB 转成 RGBA 并不能去掉背景。还应在浅色和深色底上预览边缘，检查白边、残留背景与主体误删。透明度检查示例见 [调用示例](references/examples.md#透明度验证)。

## 编辑与连续迭代

参考图编辑使用 `/v1/images/edits`；遮罩 alpha 为 0 的区域表示要编辑的区域。遮罩是引导，不保证遮罩外像素完全不变。多张参考图时明确每张的角色；遮罩作用于第一张图。

连续迭代保留原始输入与每轮输出，说明本轮变更；Responses API 可用 `previous_response_id` 延续上下文，并重新声明图像工具及 Flare 模型。`action=edit` 必须有可编辑图像上下文。

## 官方资料

- [Flare 模型页](https://developers.openai.com/api/docs/models/gpt-image-2.5-flare)
- [图像生成指南](https://developers.openai.com/api/docs/guides/image-generation)
- [Responses 图像工具](https://developers.openai.com/api/docs/guides/tools-image-generation)

此技能保存文档核对结果，不保证账号开通状态。遇到接口变化时重新核对官方参数；不添加旧模型兼容或自动回退逻辑。
