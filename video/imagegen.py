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
    item = res.data[0] if res.data else None
    if item and item.b64_json:
        data = base64.b64decode(item.b64_json, validate=True)
    elif item and item.url:  # 第三方兼容接口有时只返回图片链接
        import urllib.request
        for attempt in range(4):  # 只重试下载，不重新生图（不重复计费）
            try:
                with urllib.request.urlopen(item.url, timeout=120) as r:
                    data = r.read()
                break
            except OSError:
                if attempt == 3:
                    raise
                time.sleep(2 * 2 ** attempt)
    else:
        raise RuntimeError(f"API 未返回图片：{str(res)[:300]}")
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(data)
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
