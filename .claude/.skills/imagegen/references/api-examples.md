# 调用示例

示例依据[图像指南](https://developers.openai.com/api/docs/guides/image-generation)和[图像工具指南](https://developers.openai.com/api/docs/guides/tools-image-generation)整理，默认使用 Flare。以下是可适配的 Python 示例，不是已执行的生成结果。运行环境需要支持这些参数的 `openai` SDK 和 `python-dotenv`；透明度验证需要 Pillow。从项目根目录运行，示例读取该目录 `.env`，不覆盖进程中已设置的环境变量；OpenAI SDK 使用 `OPENAI_API_KEY` 和 `OPENAI_BASE_URL`。从其他目录执行时，将 dotenv 路径改为项目 `.env` 的绝对路径。

本项目基址为用户指定的第三方兼容接口 `https://hk.ergouzi.life/v1`。模型名称和参数支持尚未在该服务验证；不能把官方能力说明当作第三方服务的兼容保证。项目根目录 `.env` 提供配置；部署环境可通过同名环境变量覆盖文件中的值。

## 生成透明底 PNG

```python
import base64
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(Path.cwd() / ".env", override=False)
client = OpenAI(timeout=300.0, max_retries=0)
result = client.images.generate(
    model="gpt-image-2.5-flare",
    prompt=("一只橙色小狐狸贴纸，全身完整，居中，四周留白，精细毛发边缘。"
            "透明 alpha 背景，无地面、无投影、无白色底板、无棋盘格。"),
    size="1024x1024",
    quality="high",
    background="transparent",
    output_format="png",
    n=1,
)
if not result.data:
    raise RuntimeError("API 未返回图片")
out = Path("output/fox")
out.mkdir(parents=True, exist_ok=True)
for index, item in enumerate(result.data, 1):
    if not item.b64_json:
        raise RuntimeError("图片结果缺少 b64_json")
    path = out / f"fox-{index}.png"
    with path.open("xb") as target:
        target.write(base64.b64decode(item.b64_json, validate=True))
    print(path.resolve())
```

`xb` 防止覆盖已有成品；再次生成前选择新的输出目录或文件名。需要透明 WebP 时改 `output_format` 和后缀为 `webp`；可额外设置 `output_compression`。不透明 JPEG 则同时改背景为 `opaque`、格式为 `jpeg`、后缀为 `.jpg`。

## 编辑已有图片以去背景

```python
import base64
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(Path.cwd() / ".env", override=False)
client = OpenAI(timeout=300.0, max_retries=0)
with Path("input/product.png").open("rb") as source:
    result = client.images.edit(
        model="gpt-image-2.5-flare",
        image=source,
        prompt="移除背景，保留产品外形、标签文字、颜色和材质，完整保留产品；不增加投影。",
        background="transparent",
        output_format="png",
        quality="high",
        size="auto",
        n=1,
    )
if not result.data or not result.data[0].b64_json:
    raise RuntimeError("API 未返回图片")
out = Path("output/product-cutout.png")
out.parent.mkdir(parents=True, exist_ok=True)
with out.open("xb") as target:
    target.write(base64.b64decode(result.data[0].b64_json, validate=True))
```

局部编辑时再打开同尺寸的 `mask.png`，将文件对象传入 `mask=`；在请求结束前保持所有输入文件打开。多图参考可用 `image=[file1, file2]`，提示词明确各图角色。

## Responses 多轮改图

```python
import base64
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv(Path.cwd() / ".env", override=False)
client = OpenAI(timeout=300.0, max_retries=0)
tools = [{
    "type": "image_generation",
    "model": "gpt-image-2.5-flare",
    "background": "transparent",
    "output_format": "png",
    "quality": "high",
    "size": "1024x1024",
    "action": "generate",
}]
first = client.responses.create(
    model="gpt-6-astra",
    input="生成一只戴蓝色围巾的小狐狸，完整全身，透明背景。",
    tools=tools,
)

def save_image(response, path):
    images = [item.result for item in response.output
              if item.type == "image_generation_call" and item.result]
    if not images:
        raise RuntimeError("响应中没有图片生成结果")
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as file:
        file.write(base64.b64decode(images[0], validate=True))

save_image(first, "output/fox-v1.png")
second = client.responses.create(
    model="gpt-6-astra",
    previous_response_id=first.id,
    input="只把围巾改为红色，保持角色、姿态、构图与透明背景。",
    tools=[{**tools[0], "action": "edit"}],
)
save_image(second, "output/fox-v2.png")
```

主模型需在执行账号中可用且支持图像工具。若无权限，报告错误并选择账号支持的主模型后再请求；图像工具内仍保持用户指定的 Flare。

## 透明度验证

```python
from PIL import Image

with Image.open("output/fox/fox-1.png") as source:
    has_alpha = "A" in source.getbands() or "transparency" in source.info
    if not has_alpha:
        raise ValueError("没有 alpha 通道或透明信息")
    image = source.convert("RGBA")
    alpha = image.getchannel("A")
    minimum, maximum = alpha.getextrema()
    if minimum == 255:
        raise ValueError("图片完全不透明")
    if maximum == 0:
        raise ValueError("图片完全透明，主体不可见")
    print({"size": image.size, "alpha_range": (minimum, maximum)})
```

此检查只能证明存在透明与可见像素，不能证明背景已正确移除；仍需目视检查边缘、孔洞、毛发和主体完整性。
