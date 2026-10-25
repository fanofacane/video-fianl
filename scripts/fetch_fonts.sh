#!/usr/bin/env bash
# 下载项目用到的开源字体到 assets/fonts/（字体较大，不入库）。
# 思源宋体 Noto Serif SC（字幕、水印）、马善政毛笔楷书 Ma Shan Zheng（开场标题），均为 OFL 授权。
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p assets/fonts
get() {
  [ -s "assets/fonts/$1" ] && { echo "已存在 $1"; return; }
  curl -sSfL -o "assets/fonts/$1" "$2"
  echo "已下载 $1"
}
get NotoSerifSC-Black.otf "https://cdn.jsdelivr.net/gh/notofonts/noto-cjk@main/Serif/SubsetOTF/SC/NotoSerifSC-Black.otf"
get MaShanZheng.ttf "https://cdn.jsdelivr.net/gh/google/fonts@main/ofl/mashanzheng/MaShanZheng-Regular.ttf"
