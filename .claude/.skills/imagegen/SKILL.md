---
name: imagegen
description: 生成或编辑照片、插画、产品图、视频素材、精灵图和透明背景等位图资产；融合 imagegen 提示词工作流与项目 GPT Image 2.5 API，默认 gpt-image-2.5-flare。用于文生图、参考图、局部修改和批量图片，不用于视频生成或适合直接编辑 SVG/HTML/CSS 的图形。
---

# Imagegen：项目生图与图片编辑

本技能复制自 OpenAI 系统 imagegen，并于 2026-10-25 在项目副本中整合原 openai-image-25。保留原提示词方法、场景模板、编辑约束、批量生成与文件保存功能；项目默认 API 模型为 `gpt-image-2.5-flare`。系统安装目录未修改。保留原 LICENSE.txt。

## 执行路径与默认配置

用户已为本项目选择 Flare API 路径；允许调用 API 的宿主中，使用本技能 `scripts/image_gen.py`，无需为已配置的路径反复确认。读取项目根目录 `.env` 的 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`，进程环境变量优先。当前基址为用户指定的 `https://hk.ergouzi.life/v1`，属于第三方兼容服务；参数依据官方文档整理，不等于已验证第三方全部支持。

如宿主更高优先级指令要求使用内置 `image_gen`，遵守宿主工具规则；如用户明确选用内置工具也可使用该路径。内置工具没有暴露模型选择时，不声称使用了 Flare，也不把 CLI 参数传给它。不能为规避宿主规则调用 API。缺少密钥或 API 失败时报告原因，不静默切换模型或服务。

API 默认：Flare、`n=1`、`size=auto`、`quality=auto`、`background=auto`、PNG。支持 Flare/Sunburst 及其 2026-09-08 快照，只有用户要求时改变模型；不保留旧模型兼容或降级逻辑。支持 `xhigh`、`max`，省略未经确认的 `input_fidelity`。

安装依赖与调用方法见 [CLI 说明](references/cli.md)。根据当前 SKILL.md 的实际目录定位脚本；不要调用系统目录的旧脚本。复制到其他位置时用 `--env-file` 明确配置路径。密钥不输出到日志或示例。

## 工作流程

1. 区分新图、参考图生成和已有图片编辑。检查本地输入图，明确每张图的角色与必须保留的部分。给定参考图时，API 使用 `edit --image` 输入图像，不能只写路径进文生图提示词。
2. 收集主体、用途、构图、准确文字、尺寸和约束；按下文方法组织提示词。具体需求不额外加戏，泛泛需求只补足有助于成品的细节。
3. 新图调用 `generate`；已有图修改或参考图输入调用 `edit`；多个不同提示词使用 `generate-batch`。`n` 仅用于同一提示词的多个版本。
4. 使用 `--dry-run` 验证请求。批量默认并发 1、最多尝试 1 次；SDK 关闭自动重试。超时后结果可能未知，先说明状态，避免重复计费。不要通过改模型、删必要参数或扩大重试掩盖失败。
5. 检查生成结果的主体、文字、构图和编辑不变量，单点调整再生成。保存用户选定版本，不覆盖源图；只有用户要求替换时使用 `--force`。
6. 项目素材保存到工作区（默认 `output/imagegen/`）；若供应用引用，放入实际资源目录并更新引用。内置工具结果先生成再复制入项目，不把 `$CODEX_HOME` 临时产物当成项目资源。
7. 最终展示图片，返回实际路径、关键参数、使用路径和提示词；未真实调用时明确说明。本技能整合本身不要求付费生图测试。

## 透明背景与尺寸

API 原生透明图设置 `--background transparent --output-format png`（也可 WebP），同时提示主体完整、留白、透明 alpha、不要棋盘格或底板。已有图去背景走 edit。JPEG 与透明要求冲突时先明确输出目标。

检查实际 alpha 通道及透明像素，在明暗背景上检查白边和主体残缺；RGB 转 RGBA 不等于去背景。不默认使用色键抠图，不为透明背景切换旧模型。复制保留的 `remove_chroma_key.py` 仅供用户明确要求色键后处理时使用，不进入默认流程。

自定义尺寸的宽高必须是 16 的倍数、最大边 3840、长短边比不超过 3，总像素 655360–8294400。16:9 可用 1536x864；1920x1080 不能直接原生生成。超过 2560x1440 的范围属实验性。详见 [API 参数](references/image-api.md)。

遮罩与第一张输入图同尺寸，使用带 alpha 的 PNG，alpha=0 为编辑区域；遮罩是引导，不保证外部像素绝对不变。连续会话编辑可参考 [Responses 与透明度示例](references/api-examples.md)，项目 CLI 本身只实现 Images API。

## 适用范围

适合照片、插画、角色、产品图、广告、信息图、位图素材和视觉探索。现有可编辑 SVG、代码图形或需要精确数据渲染的图表优先原生工具；不将生成图片当作可编辑矢量或应用实现。

## Prompt augmentation

Reformat user prompts into a structured, production-oriented spec. Make the user's goal clearer and more actionable, but do not blindly add detail.

Treat this as prompt-shaping guidance, not a closed schema. Use only the lines that help, and add a short extra labeled line when it materially improves clarity.

### Specificity policy

Use the user's prompt specificity to decide how much augmentation is appropriate:

- If the prompt is already specific and detailed, preserve that specificity and only normalize/structure it.
- If the prompt is generic, you may add tasteful augmentation when it will materially improve the result.

Allowed augmentations:
- composition or framing hints
- polish level or intended-use hints
- practical layout guidance
- reasonable scene concreteness that supports the stated request

Not allowed augmentations:
- extra characters or objects that are not implied by the request
- brand names, slogans, palettes, or narrative beats that are not implied
- arbitrary side-specific placement unless the surrounding layout supports it

## Use-case taxonomy (exact slugs)

Classify each request into one of these buckets and keep the slug consistent across prompts and references.

Generate:
- photorealistic-natural — candid/editorial lifestyle scenes with real texture and natural lighting.
- product-mockup — product/packaging shots, catalog imagery, merch concepts.
- ui-mockup — app/web interface mockups and wireframes; specify the desired fidelity.
- infographic-diagram — diagrams/infographics with structured layout and text.
- scientific-educational — classroom explainers, scientific diagrams, and learning visuals with required labels and accuracy constraints.
- ads-marketing — campaign concepts and ad creatives with audience, brand position, scene, and exact tagline/copy.
- productivity-visual — slide, chart, workflow, and data-heavy business visuals.
- logo-brand — logo/mark exploration, vector-friendly.
- illustration-story — comics, children’s book art, narrative scenes.
- stylized-concept — style-driven concept art, 3D/stylized renders.
- historical-scene — period-accurate/world-knowledge scenes.

Edit:
- text-localization — translate/replace in-image text, preserve layout.
- identity-preserve — try-on, person-in-scene; lock face/body/pose.
- precise-object-edit — remove/replace a specific element (including interior swaps).
- lighting-weather — time-of-day/season/atmosphere changes only.
- background-extraction — transparent background / clean cutout. Request actual alpha transparency via the selected execution path.
- style-transfer — apply reference style while changing subject/scene.
- compositing — multi-image insert/merge with matched lighting/perspective.
- sketch-to-render — drawing/line art to photoreal render.

## Shared prompt schema

Use the following labeled spec as shared prompt scaffolding for both execution paths:

```text
Use case: <taxonomy slug>
Asset type: <where the asset will be used>
Primary request: <user's main prompt>
Input images: <Image 1: role; Image 2: role> (optional)
Scene/backdrop: <environment>
Subject: <main subject>
Style/medium: <photo/illustration/3D/etc>
Composition/framing: <wide/close/top-down; placement>
Lighting/mood: <lighting + mood>
Color palette: <palette notes>
Materials/textures: <surface details>
Text (verbatim): "<exact text>"
Constraints: <must keep/must avoid>
Avoid: <negative constraints>
```

Notes:
- `Asset type` and `Input images` are prompt scaffolding, not dedicated CLI flags.
- `Scene/backdrop` refers to the visual setting. It is not the same as the project CLI `background` parameter, which controls output transparency behavior.
- API-only execution notes such as `Quality:`, `Input fidelity:`, masks, output format, and output paths belong in the CLI path only. Do not treat them as built-in `image_gen` tool arguments.

Augmentation rules:
- Keep it short.
- Add only the details needed to improve the prompt materially.
- For edits, explicitly list invariants (`change only X; keep Y unchanged`).
- If any critical detail is missing and blocks success, ask a question; otherwise proceed.

## Examples

### Generation example (hero image)
```text
Use case: product-mockup
Asset type: landing page hero
Primary request: a minimal hero image of a ceramic coffee mug
Style/medium: clean product photography
Composition/framing: wide composition with usable negative space for page copy if needed
Lighting/mood: soft studio lighting
Constraints: no logos, no text, no watermark
```

### Edit example (invariants)
```text
Use case: precise-object-edit
Asset type: product photo background replacement
Primary request: replace only the background with a warm sunset gradient
Constraints: change only the background; keep the product and its edges unchanged; no text; no watermark
```

## Prompting best practices
- Structure prompt as scene/backdrop -> subject -> details -> constraints.
- Include intended use (ad, UI mock, infographic) to set the mode and polish level.
- Use camera/composition language for photorealism.
- Only use SVG/vector stand-ins when the user explicitly asked for vector output or a non-image placeholder.
- Quote exact text and specify typography + placement.
- For tricky words, spell them letter-by-letter and require verbatim rendering.
- For multi-image inputs, reference images by index and describe how they should be used.
- For edits, repeat invariants every iteration to reduce drift.
- Iterate with single-change follow-ups.
- If the prompt is generic, add only the extra detail that will materially help.
- If the prompt is already detailed, normalize it instead of expanding it.
- For project CLI only, see `references/cli.md` and `references/image-api.md` for model, `quality`, `input_fidelity`, masks, output format, and output-path guidance.
- For transparent images, use the selected path’s native transparency option and preserve its alpha.

More principles shared by both modes: `references/prompting.md`.
Copy/paste specs shared by both modes: `references/sample-prompts.md`.

## Guidance by asset type
Asset-type templates (website assets, game assets, wireframes, logo) are consolidated in `references/sample-prompts.md`.


## 参考文件

- [prompting.md](references/prompting.md)：提示词、构图、文字和编辑约束。
- [sample-prompts.md](references/sample-prompts.md)：保留系统版的场景模板。
- [cli.md](references/cli.md)：项目脚本、批量、编辑和输出用法。
- [image-api.md](references/image-api.md)：合并后的 GPT Image 2.5 参数与官方来源。
- [api-examples.md](references/api-examples.md)：多轮 Responses、透明度检测等补充示例；单次 Images 调用优先复用项目 CLI。
- [codex-network.md](references/codex-network.md)：连接失败排查。
