"""调用 GPT Image 2.5 (Flare) 生成图片，遵循 .claude/.skills/openai-image-25 的约定。

命令行: python3 -m video.imagegen --prompt "..." --size 1536x864 --background opaque --out path.png
API 配置读取项目根目录 .env（OPENAI_API_KEY / OPENAI_BASE_URL）。
"""
import argparse
import base64
import time
from pathlib import Path

from .config import ROOT


def generate(prompt, out, size="1536x864", background="opaque", quality="high"):
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv(ROOT / ".env", override=False)
    client = OpenAI(timeout=600.0, max_retries=0)
    t0 = time.time()
    res = client.images.generate(
        model="gpt-image-2.5-flare",
        prompt=prompt,
        size=size,
        quality=quality,
        background=background,
        output_format="png",
        n=1,
    )
    if not res.data or not res.data[0].b64_json:
        raise RuntimeError("API 未返回图片")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(res.data[0].b64_json, validate=True))
    print(f"生图完成 {out}（{time.time() - t0:.0f}s，gpt-image-2.5-flare，{size}，{background}）")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--size", default="1536x864")
    ap.add_argument("--background", default="opaque", choices=["auto", "opaque", "transparent"])
    ap.add_argument("--quality", default="high")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    generate(a.prompt, a.out, a.size, a.background, a.quality)


if __name__ == "__main__":
    main()
