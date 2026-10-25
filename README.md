# video-fianl

用代码批量制作“哲学 / 心理学知识类”横屏短视频。风格参考见 [开场拆解](docs/reference/jiangdongling-opening-style.md)、[正文段拆解](docs/reference/body-collage-style.md)。

## 进度

| 模块 | 状态 | 说明 |
| --- | --- | --- |
| 碎片开场 | ✅ 完成 | 所有视频统一使用：玻璃碎片从上方坠落，底部先落位、逐渐向上拼合成背景图，配毛笔标题与黄色双语字幕；开场本身无声，配乐与口播在整片阶段加 |
| 拼贴正文段 | ⏳ 待做 | 米色纸纹底 + 透明底抠图素材，一句台词出一个元素 |
| 口播 / 配乐 | ⏳ 待做 | |
| 整片拼接 | ⏳ 待做 | |

## 目录

```
video/                  # 代码
  config.py             # 画面尺寸 1280x720、30fps、字体路径、输出目录
  text.py               # 全片通用文字样式：黄色中英字幕、顶部水印、开场毛笔标题
  imagegen.py           # GPT Image 2.5 生图（背景图、透明底素材）
  opening/              # 碎片开场
    build.py            # 入口：配置 JSON → 开场 mp4
    shatter.py          # Blender 3D 碎片渲染（厚度、翻转、反光、景深、动态模糊）
    cuts.py             # 碎片切分（按裂纹遮罩图分块；可从红线标注图生成遮罩）
    assets/cuts_mask.png# 默认切法：中间一大块托住标题，四周逐渐变小
examples/               # 示例配置与素材
scripts/fetch_fonts.sh  # 下载字体
docs/reference/         # 参考视频拆解
.claude/.skills/        # 技能：media-parser（解析抖音链接）、openai-image-25（生图）
output/                 # 成片与渲染缓存（不入库）
```

## 环境

```sh
pip install -r requirements.txt   # bpy 需要 Python 3.13
bash scripts/fetch_fonts.sh       # 下载字体到 assets/fonts/
```

另需 `ffmpeg`。生图需要项目根目录 `.env` 里的 `OPENAI_API_KEY`、`OPENAI_BASE_URL`。

## 做一个开场

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
