# video-fianl

用代码批量制作“哲学 / 心理学知识类”横屏短视频（默认 90 秒，顶部水印 @好想一口吃掉）。

> **制作任何一期之前，必须先阅读参考库 [library/](library/README.md) 中与本期话题最接近的对标视频**（`meta.md` 标题与话题、`breakdown.md` 文案拆解、`frames.jpg` 场景帧），再动笔写逐字稿。经验沉淀见 [docs/lessons.md](docs/lessons.md)。

风格参考见 [开场拆解](docs/reference/jiangdongling-opening-style.md)、[正文段拆解](docs/reference/body-collage-style.md)、[多视频风格共性](docs/reference/common-style.md)。逐字稿写作规范见 [docs/script-style.md](docs/script-style.md)。

## 进度

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 碎片开场 | ✅ 完成 | 所有视频统一使用：玻璃碎片从上方坠落，底部先落位、逐渐向上拼合成背景图，配毛笔标题与黄色双语字幕；开场本身无声，配乐与口播在整片阶段加 |
| 参考库 / 成品库 | ✅ 完成 | `library/`：11 个对标视频（标题、话题、文案拆解、场景帧，中版有逐秒帧）；成品按发布标题归档 |
| 拼贴正文段 | 🚧 进行中 | 场景引擎已可用：抠图、底部撕边照片带、全屏照片、屏幕文字（可逐字打出）、对话气泡、概念清单、循环图，按口播时间轴出现；元素说明见 `docs/script-style.md` 第 5 节 |
| 口播 / 配乐 | 🚧 进行中 | 配音用 minimax-speech 技能（已复刻音色）；`video/align.py` 用本地 Whisper 把口播对齐到每行字幕；配乐待做 |
| 整片拼接 | 🚧 进行中 | `python3 -m video.episode episodes/<slug>/episode.json [--shots]`：配音 → 对齐 → 碎片开场 + 正文 → 提亮溶解拼接 + 混音 |

## 目录

```
video/                  # 代码
  config.py             # 画面尺寸 1280x720、30fps、字体路径、输出目录
  text.py               # 全片通用文字样式：黄色中英字幕、开场毛笔标题
  imagegen.py           # GPT Image 2.5 生图（背景图、透明底素材）
  episode.py            # 整期成片入口（配音、对齐、开场、正文、拼接）
  align.py              # 口播与字幕行对齐（本地 Whisper）
  library.py            # 参考库 / 成品库入库工具
  body/build.py         # 正文段：配置 JSON（素材 + 元素时间轴 + 字幕）→ 正文 mp4 / 关键帧截图
  opening/              # 碎片开场
    build.py            # 入口：配置 JSON → 开场 mp4
    shatter.py          # Blender 3D 碎片渲染（厚度、翻转、反光、景深、动态模糊）
    cuts.py             # 碎片切分（按裂纹遮罩图分块；可从红线标注图生成遮罩）
    assets/cuts_mask.png# 默认切法：中间一大块托住标题，四周逐渐变小
episodes/<slug>/        # 每期内容：episode.json（逐字稿、开场、场景、素材、发布标题）
library/                # 参考库 reference/（对标视频）与成品库 ours/（按发布标题）
docs/script-style.md    # 逐字稿、标题、封面、简介写作规范
docs/hooks.md           # 开头与前 30% 的写法（10 个对标总结）
docs/body-writing.md    # 正文写法与画面配合（对标逐秒拆解总结）
docs/lessons.md         # 制作经验沉淀
examples/               # 示例配置与素材
scripts/fetch_fonts.sh  # 下载字体
docs/reference/         # 参考视频拆解
.claude/.skills/        # 技能：media-parser（解析/转写抖音链接）、openai-image-25（生图）、minimax-speech（配音）
output/                 # 成片与渲染缓存（不入库）
```

## 每期制作流程（必须按顺序，每个审核点等用户确认）

1. **用户给话题**。
2. **读规范和参考库**：先读 [docs/hooks.md](docs/hooks.md) 和 [docs/body-writing.md](docs/body-writing.md)，再挑 1–2 个最接近的对标视频，读 `meta.md`、`breakdown.md`、逐秒帧 `frames_1s_p*.jpg`，以及本地完整转写稿 `output/library/<slug>/transcript.txt`。
3. **交第一稿（审核点 1）**：
   - 逐字稿：按 [docs/script-style.md](docs/script-style.md) 写 90 秒版（400–440 字，不含标点），原创；
   - 发布标题 3 个备选 + 话题标签（简介 = 标题 + 话题）；
   - 开场封面 3 张（生图 + 概念词大字 + 第一句字幕合成）。
4. **用户确认后**：写 `episodes/<slug>/episode.json`（逐字稿、开场、场景、素材、`publish`），配音一次，然后
   `python3 -m video.episode episodes/<slug>/episode.json --shots` 出**正文场景截图**（不渲染视频），**审核点 2**。
   等待审核时可在后台先渲染碎片开场（开场不依赖正文）。
5. **用户审核通过后**：`python3 -m video.episode episodes/<slug>/episode.json` 出完整视频 `output/<slug>/final.mp4`。
6. **归档**：`python3 -m video.library ours episodes/<slug>/episode.json`，并在 [library/README.md](library/README.md) 的成品表加一行；新经验补进 [docs/lessons.md](docs/lessons.md)。

## 环境

```sh
pip install -r requirements.txt   # bpy 需要 Python 3.13
bash scripts/fetch_fonts.sh       # 下载字体到 assets/fonts/
```

另需 `ffmpeg`。项目根目录 `.env`：生图 `OPENAI_API_KEY`、`OPENAI_BASE_URL`；配音 `MINIMAX_API_KEY`、`MINIMAX_VOICE_ID` 等（见 minimax-speech 技能）。

## 附：单独做一个开场

1. 复制 `examples/opening_solitude.json`，改 `name`、`title`、`subtitles`、`watermark`。
2. 背景：`background.image` 填已有图片；留空则按 `background.prompt` 自动生图（16:9，存到 `output/<name>/background.png`，再次运行直接复用）。
3. 先出关键帧截图确认效果（约 1 分钟）：
   ```sh
   python3 -m video.opening.build examples/opening_solitude.json --shots
   ```
   结果在 `output/<name>/shots.jpg`（0.3 → 1.7 秒共 8 帧）。
4. 出视频（首次渲染碎片约 10 分钟；之后只改文字会复用缓存，几秒完成）：
   ```sh
   python3 -m video.opening.build examples/opening_solitude.json
   ```
   结果在 `output/<name>/opening.mp4`。

### 开场时间线（默认 4.6 秒）

| 时间 | 画面 |
| --- | --- |
| 0–0.3s | 黑底，标题逐字淡入；一片细碎片横穿标题拉出亮光 |
| 0.3–1.5s | 碎片从上方翻滚坠落，底部先拼好，逐渐向上补齐 |
| 1.5–2.0s | 拼合完成，裂纹淡去 |
| 2.0s–结束 | 背景慢推镜；结束前 0.6 秒标题淡出 |

### 换一种碎片切法

在任意截图上用红笔画出裂纹线，然后：

```sh
python3 -m video.opening.cuts 标注图.png video/opening/assets/my_cuts.png
```

在配置里加 `"cuts": "video/opening/assets/my_cuts.png"`。只提取红线，原截图内容不会保存。
