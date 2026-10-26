# Project imagegen CLI

此文件为项目副本的调用说明（2026-10-25），替代复制源中的旧模型说明。脚本 `scripts/image_gen.py` 保留 generate、edit、generate-batch、结构化提示词和缩略图功能，默认 Flare。先遵守 SKILL.md 中的宿主工具约束。

## 环境与默认值

从项目根目录安装：

```powershell
python -m pip install -r .claude/.skills/imagegen/requirements.txt
```

脚本从自身位置定位项目 `.env`；读取 OPENAI_API_KEY、OPENAI_BASE_URL，环境变量优先。当前配置为 https://hk.ergouzi.life/v1。迁移目录后用 `--env-file` 指定路径，该选项放在子命令后。不会读取或修改系统技能。

默认 model=gpt-image-2.5-flare，size=auto，quality=auto，background=auto，output_format=png，n=1。默认输出 output/imagegen/output.png；通常用 --out 选择明确文件名。SDK 不自动重试，批量默认并发 1、最多尝试 1 次；不要在未知超时后盲目增加尝试次数。

## 生图、编辑与透明图

以下示例从项目根目录运行；其他目录使用当前技能脚本的绝对路径。--dry-run 只校验并输出请求，不调用接口，不打印密钥。

```powershell
python .claude/.skills/imagegen/scripts/image_gen.py generate --prompt "一只完整的小狐狸贴纸，透明背景，不画棋盘格" --background transparent --output-format png --quality high --out output/imagegen/fox.png --dry-run
python .claude/.skills/imagegen/scripts/image_gen.py generate --prompt-file output/prompt.txt --quality xhigh --size 1536x864 --out output/imagegen/hero.png
python .claude/.skills/imagegen/scripts/image_gen.py edit --image input/product.png --prompt "仅去掉背景，保留产品形状和标签" --background transparent --out output/imagegen/product-cutout.png
```

确认请求后去掉 --dry-run 执行。多个参考图重复 --image；最多 16 张。局部编辑加 --mask input/mask.png。Flare 不设置 --input-fidelity，此选项如显式传入会被拒绝。参考图生成在概念上可视为生成，API 传输仍使用 edit。

输出可用 png/jpeg/webp；JPEG 不支持透明。--output-compression 0–100 仅用于 JPEG/WebP。--moderation 可按 API 文档设置，不为绕过失败自动修改。

## 提示词字段

保留系统 imagegen 的 --use-case、--scene、--subject、--style、--composition、--lighting、--palette、--materials、--text、--constraints、--negative。这些字段拼入 prompt，不是 API 的独立字段。--negative 不会发送 negative_prompt。

默认进行结构化拼接；已经完整写好的提示词可用 --no-augment。--text 是图片中要出现的准确文字，不是提示词来源，提示词使用 --prompt 或 --prompt-file。

## 批量

保存 UTF-8 JSONL，每行一个任务：

```jsonl
{"prompt":"蓝色小鸟，透明底，完整轮廓","background":"transparent","quality":"high","out":"bird.png"}
{"prompt":"黄昏山谷的横版插画","size":"1536x864","quality":"xhigh","out":"valley.png"}
```

```powershell
python .claude/.skills/imagegen/scripts/image_gen.py generate-batch --input output/prompts.jsonl --out-dir output/imagegen/batch --dry-run
```

每条支持 model/n/size/quality/background/output_format/output_compression/moderation 及提示词字段覆盖。out 作为 out-dir 内文件名。--n 是同一提示词的变体，不代替多个不同资产任务。批量目录应是新目录，避免重复文件名或覆盖已有结果。--concurrency 可调并发，--fail-fast 遇到失败取消剩余任务；取消不保证服务端已停止计费。

## 输出与检查

--out-dir 使用 image_1.png 等命名；--n 大于 1 时自动编号。默认不覆盖，--force 仅在用户要求替换时使用。--downscale-max-dim 额外保存缩小版本，默认后缀 -web。不能将缩放后的尺寸称为原生生成尺寸。

使用 Pillow 检查图片大小、格式、alpha 和透明像素，并目视检查文字与主体。透明度检查以及 Responses 多轮编辑见 api-examples.md；项目 CLI 仅实现 Images API，不能声称支持 Responses 会话、流式或所有官方参数。

完整参数范围见 image-api.md，创意模板见 sample-prompts.md。
