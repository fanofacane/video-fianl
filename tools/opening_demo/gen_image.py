"""调用 GPT Image 2.5 (Flare) 生成一张图，按 openai-image-25 技能约定。

用法: python3 gen_image.py --prompt "..." --size 1536x864 --background opaque --out path.png [--quality high]
API 配置读取项目根目录 .env（OPENAI_API_KEY / OPENAI_BASE_URL）。
"""
import argparse, base64, time
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

ROOT = Path(__file__).resolve().parents[2]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--size", default="1024x1024")
    ap.add_argument("--background", default="auto", choices=["auto", "opaque", "transparent"])
    ap.add_argument("--quality", default="high")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    load_dotenv(ROOT / ".env", override=False)
    client = OpenAI(timeout=600.0, max_retries=0)
    t0 = time.time()
    res = client.images.generate(
        model="gpt-image-2.5-flare",
        prompt=args.prompt,
        size=args.size,
        quality=args.quality,
        background=args.background,
        output_format="png",
        n=1,
    )
    if not res.data or not res.data[0].b64_json:
        raise RuntimeError("API 未返回图片")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(res.data[0].b64_json, validate=True))
    print(f"saved {out} in {time.time() - t0:.0f}s; usage={getattr(res, 'usage', None)}")


if __name__ == "__main__":
    main()
