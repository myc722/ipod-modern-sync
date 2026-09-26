#!/bin/bash
# 下载音乐一键脚本
# 用法：双击运行后粘贴 Apple Music 链接；或在终端 ./下载音乐.command "链接"

cd "$(dirname "$0")"

# 获取链接：优先用双击时输入的，其次提示粘贴
if [ -n "$1" ]; then
  url="$1"
else
  echo "把 Apple Music 链接粘贴到这里，然后按回车："
  read url
fi

if [ -z "$url" ]; then
  echo "没有输入链接，退出。"
  exit 1
fi

echo ""
echo "开始下载：$url"
echo ""

./amdl "$url"

echo ""
if [ $? -eq 0 ]; then
  echo "下载完成，正在打开文件夹..."
  open "AM-DL downloads"
else
  echo "下载过程有错误，以上方输出为准。"
fi
echo ""
echo "提示：如果是要导入 iPod，关闭本窗口后双击运行「转iPod格式.command」修封面。"
echo "按任意键关闭窗口..."
read -n 1
