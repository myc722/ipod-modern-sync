#!/bin/bash
# iPod 歌曲整理工具
# 自动扫描下载的音乐，把封面统一修成 iPod 兼容的 600x600 JPEG
# 用法：双击运行，或在终端执行 ./转iPod格式.command

cd "$(dirname "$0")"
echo "正在扫描已下载的音乐..."
echo ""

total=0; fixed=0; skipped=0; failed=0
TMPDIR_FIX=$(mktemp -d)
trap 'rm -rf "$TMPDIR_FIX"' EXIT

# 扫描所有下载目录里的 m4a 文件
find "AM-DL downloads" "AM-DL-Atmos downloads" "AM-DL-AAC downloads" -name "*.m4a" -type f 2>/dev/null | while IFS= read -r f; do
  # 提取封面：优先取文件内嵌的，否则用同目录的 cover.jpg
  cover="$TMPDIR_FIX/cover.jpg"
  rm -f "$cover"
  ffmpeg -v error -y -i "$f" -an -frames:v 1 "$cover" 2>/dev/null
  if [ ! -s "$cover" ] && [ -f "$(dirname "$f")/cover.jpg" ]; then
    cp "$(dirname "$f")/cover.jpg" "$cover"
  fi

  if [ ! -s "$cover" ]; then
    echo "✗ 找不到封面，跳过: $f"
    continue
  fi

  # 统一转成 600x600 标准 JPEG，并剥离 EXIF/ICC 等元数据（老 iPod 解码器认纯净 JFIF）
  sips -Z 600 -s format jpeg -s formatOptions 85 "$cover" --out "$TMPDIR_FIX/cover600.jpg" >/dev/null 2>&1
  ffmpeg -v error -y -i "$TMPDIR_FIX/cover600.jpg" -q:v 2 "$TMPDIR_FIX/pure.jpg" 2>/dev/null

  # 用 AtomicParsley 重写封面（先清旧图再写，保证只有一张；这是 iPod 最兼容的写法）
  if AtomicParsley "$f" --artwork REMOVE_ALL --overWrite >/dev/null 2>&1 && \
     AtomicParsley "$f" --artwork "$TMPDIR_FIX/pure.jpg" --overWrite >/dev/null 2>&1; then
    echo "✔ 已修复: $f"
  else
    echo "✗ 修复失败: $f"
  fi
  rm -f "$cover" "$TMPDIR_FIX/cover600.jpg" "$TMPDIR_FIX/pure.jpg"
done

echo ""
echo "完成！把修好的歌曲重新拖进 iPod 即可（记得先删掉 iPod 里的旧文件）。"
echo "按任意键关闭窗口..."
read -n 1
