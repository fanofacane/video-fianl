# video-fianl

用代码批量制作“哲学 / 心理学知识类”横屏短视频（默认 90 秒，顶部水印 @好想一口吃掉）。

> **写逐字稿之前，必须先读 `library/reference/` 下全部认可稿**（我们自己的标准答案，见 [library/README.md](library/README.md)）。经验沉淀见 [docs/lessons.md](docs/lessons.md)。

逐字稿规范见 [docs/script-style.md](docs/script-style.md)，开头见 [docs/hooks.md](docs/hooks.md)，正文画面见 [docs/body-writing.md](docs/body-writing.md)，封面样张在 `docs/reference/covers/`。

## 进度

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 碎片开场 | ✅ 完成 | 所有视频统一使用：玻璃碎片从上方坠落，底部先落位、逐渐向上拼合成背景图，配毛笔标题与黄色双语字幕；开场本身无声，配乐与口播在整片阶段加 |
| 参考库 / 成品库 | ✅ 完成 | `library/`：对标口播全文、用户认可的逐字稿（reference/）、成片归档（ours/） |
| 拼贴正文段 | 🚧 进行中 | 场景引擎已可用：抠图、底部撕边照片带、全屏照片、屏幕文字（可逐字打出）、对话气泡、概念清单、循环图，按口播时间轴出现；元素说明见 `docs/script-style.md` 第 5 节 |
| 口播 / 配乐 | 🚧 进行中 | 配音用 minimax-speech 技能（已复刻音色）；`video/align.py` 用本地 Whisper 把口播对齐到每行字幕；配乐待做 |
| 整片拼接 | 🚧 进行中 | 已拆分文案确认、显式配音、正文截图确认、成片；截图和成片入口不再自动配音 |

## 目录

```
video/                  # 代码
  config.py             # 画面尺寸 1280x720、30fps、字体路径、输出目录
  text.py               # 全片通用文字样式：黄色中英字幕、开场毛笔标题
  imagegen.py           # GPT Image 2.5 生图（背景图、透明底素材）
  episode.py            # 整期成片入口（配音、对齐、开场、正文、拼接）
  review.py             # 按内容版本绑定文案/截图审核及配音记录
  align.py              # 口播与字幕行对齐（本地 Whisper）
  library.py            # 成品归档；对标研究（只存本地 output/library/）
  body/build.py         # 正文段：配置 JSON（素材 + 元素时间轴 + 字幕）→ 正文 mp4 / 关键帧截图
  opening/              # 碎片开场
    build.py            # 入口：配置 JSON → 开场 mp4
    shatter.py          # Blender 3D 碎片渲染（厚度、翻转、反光、景深、动态模糊）
    cuts.py             # 碎片切分（按裂纹遮罩图分块；可从红线标注图生成遮罩）
    assets/cuts_mask.png# 默认切法：中间一大块托住标题，四周逐渐变小
episodes/<slug>/        # 每期内容：episode.json（逐字稿、开场、场景、素材、发布标题）
library/                # reference/（用户认可的逐字稿）、ours/（成片归档）
docs/script-style.md    # 逐字稿、标题、封面、简介写作规范
docs/hooks.md           # 开头 2 句与前 30% 的写法（对标原句对照）
docs/body-writing.md    # 正文画面：场景层、大元素、逐句叠加、退场（对标逐秒拆解总结）
docs/lessons.md         # 制作经验沉淀
scripts/fetch_fonts.sh  # 下载字体
docs/reference/covers/  # 封面质感样张（只看质感，不临摹）
.claude/.skills/        # 技能：media-parser（解析/转写抖音链接）、imagegen（生图）、minimax-speech（配音）
output/                 # 成片与渲染缓存（不入库）
```

## 每期制作流程（必须按顺序，每个审核点等用户确认）

1. **用户给话题**。
2. **读规范和参考**：先读 [docs/script-style.md](docs/script-style.md)（第 0 节必做）、[docs/hooks.md](docs/hooks.md)、[docs/body-writing.md](docs/body-writing.md)；再读 `library/reference/` 下全部认可稿，**写出仿写对照表**。
3. **交第一稿（审核点 1）**：
   - 逐字稿 + 仿写对照表：按 [docs/script-style.md](docs/script-style.md) 写 90 秒版（约 370–410 字，不含标点，允许上下浮动），可适当引用、化用对标视频的好句子；
   - 发布标题 3 个备选 + 话题标签（简介 = 标题 + 话题）；
   - 开场封面 3–4 张，**每张一种不同风格**（风格库见 docs/script-style.md 第 7 节，样张在 docs/reference/covers/）：生图 + 概念词大字 + 第一句字幕合成。
4. **用户确认稿件后**：将已展示的准确逐字稿、标题和发布信息写入 `episodes/<slug>/episode.json`。先执行 `--status` 得到 `script_id`，仅在用户确实确认了这版内容后执行 `--approve-script <script_id>`。该操作只记录确认，不生成配音。修改逐字稿、标题或发布信息后必须重新确认，不能拿旧确认套新内容。
5. **显式生成配音**：执行 `--voice`，只为已确认稿件调用 MiniMax。生成后展示配音试听；若用户要求调整则处理后再继续。配音按中文全文和音色/模型参数保存版本；同一版本复用，改稿不删除旧配音、不自动产生费用。
6. **出正文场景截图（审核点 2）**：执行 `--shots`，仅读取已完成配音、做本地字幕对齐，再生成截图。缺配音直接停止，不调用 TTS。此步骤可能生成缺失的画面素材；“不配音”不等于所有服务都免费。同时用 `python3 scripts/perline_shots.py <name>` 出逐句截图一起给用户看（看元素是否逐句叠加、画面是否饱满）。展示截图及输出的审核 ID，等待用户确认。等待审核时可在后台先渲染碎片开场。
7. **用户确认截图后**：执行 `--approve-shots <截图ID>`，然后不带阶段参数运行入口，输出 `output/<slug>/final.mp4`。配置、素材、配音或截图变化会使画面确认失效，必须重新出截图并确认。
8. **归档**：`python3 -m video.library ours episodes/<slug>/episode.json`，并在 [library/README.md](library/README.md) 的成品表加一行；用户认可的逐字稿放进 `library/reference/`；新经验补进 [docs/lessons.md](docs/lessons.md)。

### 分阶段命令

```sh
python -m video.episode episodes/<slug>/episode.json --status
# 只有用户确认当前稿件后，才填入 status 给出的 script_id：
python -m video.episode episodes/<slug>/episode.json --approve-script <script_id>
python -m video.episode episodes/<slug>/episode.json --voice
python -m video.episode episodes/<slug>/episode.json --shots
# 只有用户确认当前截图后，才填入截图步骤给出的 ID：
python -m video.episode episodes/<slug>/episode.json --approve-shots <shots_id>
python -m video.episode episodes/<slug>/episode.json
```

审核命令由操作者在收到用户确认后执行，不是自动推断用户已同意。程序校验的是“确认记录是否与当前内容一致”，不是身份认证系统。阶段选项互斥，确认不会顺带发起付费请求或渲染。

记录存放于 `output/<slug>/reviews/`；配音及完成记录存放于 `output/<slug>/voices/<版本ID>/`。历史的根目录 `narration.mp3` 保留，但不会被默认为已经审核的新流程产物。不自动迁移或授权旧缓存。

请求失败或超时后保留请求记录，禁止自动重发。先核实服务端结果；只有确认失败且允许重试后，才人工清理该版本的失败请求/空文件；不要删除其他已完成版本。切换音色或模型会要求生成对应版本的配音。改英文字幕或中文分行但中文全文相同时仍需重新确认稿件，可复用音频并按新分行对齐。

## 环境

```sh
pip install -r requirements.txt   # bpy 需要 Python 3.13
bash scripts/fetch_fonts.sh       # 下载字体到 assets/fonts/
```

另需 `ffmpeg`。项目根目录 `.env`：生图 `OPENAI_API_KEY`、`OPENAI_BASE_URL`；配音 `MINIMAX_API_KEY`、`MINIMAX_VOICE_ID`（当前 `video_narrator_20261026`）、`MINIMAX_SPEED`（当前 1）等（见 minimax-speech 技能）。

## 附：单独调试碎片开场

整期入口会生成 `output/<name>/opening_gen.json`，可单独调试开场：

```sh
python3 -m video.opening.build output/<name>/opening_gen.json --shots   # 关键帧截图（约 1 分钟）
python3 -m video.opening.build output/<name>/opening_gen.json           # 出视频（首次碎片渲染约 10 分钟，之后复用缓存）
```

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
