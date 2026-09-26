# ipod-modern-sync

**Headless iPod sync for modern macOS — no iTunes, no Finder sync, artwork intact.**

Since macOS Catalina (10.15), Finder took over iPod management through a background agent
(`AMPDevicesAgent`). In practice it means: your iPod's database is validated and **rewritten on
every connection**, artwork gets silently wiped, and one bad write away from a
*"cannot read the contents of this iPod"* dialog whose only offered button is **Restore**
(= full erase).

This repo takes the opposite approach: **keep macOS away from the iPod entirely**, and sync
with a script that rebuilds the device's database itself — covers included.

Tested on: iPod nano 5G + macOS 15 (Sequoia/Tahoe-era). Should work on most click-wheel iPods
(mini / nano / classic) supported by [iOpenPod].

[简体中文](#简体中文) below.

---

## What you get

| Piece | What it does |
|---|---|
| `install_guard.sh` | Installs a tiny watchdog (~1.6 MB RAM) that neutralizes `AMPDevicesAgent` / `AMPDeviceDiscoveryAgent` **only while an iPod is connected**. Your iPod then mounts as a plain USB disk. iPhones and other devices are untouched. |
| `sync_ipod.py` | Mirrors a local music folder into the iPod: copies new files, reuses existing ones (MD5-matched, so re-syncs are fast), removes files you deleted, rebuilds the full library database — **and extracts embedded cover art into the iPod's ArtworkDB/ithmb cache**. |

The sync script is **source-agnostic**: anything in your folder (`.m4a` / `.mp3`) goes in —
rips, store purchases, files from any downloader you like. No downloader is bundled.

## Requirements

- macOS 10.15+ (Apple Silicon and Intel both fine)
- Python ≥ 3.10
- `ffprobe` (install ffmpeg: `brew install ffmpeg`)
- `pip install iopenpod`

## Setup (one time)

```bash
./install_guard.sh                 # 1. the guard
pip3 install iopenpod              # 2. the sync engine
brew install ffmpeg                # 3. metadata probing
```

Also recommended (stops Finder from trying to auto-sync):

```bash
defaults write com.apple.AMPDevicesAgent dontAutomaticallySyncIPods -bool true
```

## Daily use

1. Plug in the iPod. It appears in Finder as a **plain disk icon** — no device page, no sync
   UI, no popup. *That is the intended behavior.*
2. Run:

```bash
python3 sync_ipod.py --music-dir ~/Music/iPod
```

3. Eject, then **restart the iPod** (hold MENU + center button ~6 s) so it re-reads the database.

Covers show up. Every time.

## How it works (short version)

- The iPod's firmware reads `iPod_Control/iTunes/iTunes Library.itlp/Library.itdb` (SQLite),
  while Finder validates the parallel binary `iTunesCDB`. Finder *always* rewrites both on
  connect and drops artwork links it doesn't understand — that's why covers kept disappearing.
- The guard simply kills Finder's device agents while an iPod is plugged in, so the databases
  are never touched by macOS.
- `sync_ipod.py` uses [iOpenPod] to write all database formats the device needs (iTunesCDB,
  SQLite itlp, ArtworkDB, ithmb) in one commit, extracting artwork from the embedded images in
  your audio files. MD5 matching makes repeated syncs incremental.

## Rules to live by

- **Never click "Restore"** on the iPod's Finder page (there shouldn't be one anymore).
- Don't manually delete files inside `iPod_Control`. Remove music from your source folder and
  re-sync instead.
- Videos you record on a nano 5G still land in `DCIM/` — copy them out like from any camera.

## Uninstall

```bash
launchctl unload ~/Library/LaunchAgents/com.ipod-sync.guard.plist
rm ~/Library/LaunchAgents/com.ipod-sync.guard.plist
rm -rf "$HOME/Library/Application Support/ipod-modern-sync"
```

## Credits & license

Sync engine: [iOpenPod]. Everything else: this repo. MIT License.
Not affiliated with or endorsed by Apple. Use it with music you have the right to keep.

[iOpenPod]: https://github.com/mercurialworld/iopenpod

---

## 简体中文

> 📖 **第一次使用？先看 [零基础完整教程](GUIDE-zh.md)**：从装环境、装下载器到日常导歌的每一步，
> 含常见问题排查。仓库 `amdl-helpers/` 里有三个双击即用的小脚本（启动解密服务 / 下载音乐 / 修封面）。

### 问题背景

macOS 从 Catalina（10.15）开始把 iPod 管理交给了访达的后台代理（`AMPDevicesAgent`）。实际体验是：
每次插上 iPod，它都会**校验并重写机身上的数据库**，封面会被静默抹掉，运气不好还弹出
「未能读取 iPod 的内容」——唯一的按钮是**恢复**（= 全盘清空）。本仓库的思路完全相反：
**让 macOS 彻底别碰 iPod，用脚本自己重建数据库**，封面一次到位。

已在 iPod nano 5G + macOS 15 上实测；理论上支持 iOpenPod 能识别的转盘 iPod（mini/nano/classic）。

### 一分钟上手

```bash
./install_guard.sh                 # 1. 安装看门狗（常驻仅 1.6MB，iPod 不插时几乎零开销）
pip3 install iopenpod              # 2. 安装同步引擎
brew install ffmpeg                # 3. 安装 ffprobe

# 可选：禁止访达自动同步
defaults write com.apple.AMPDevicesAgent dontAutomaticallySyncIPods -bool true
```

日常三步：

1. 插上 iPod —— 访达里它显示为**普通磁盘图标**，没有设备页、不弹窗，这是正常的
2. 运行 `python3 sync_ipod.py --music-dir ~/Music/iPod`（把 `~/Music/iPod` 换成你的音乐文件夹，
   结构随意，推荐 `歌手/专辑/NN. 歌名.m4a`）
3. 推出 iPod，**重启它**（菜单键 + 中键按住 6 秒）—— 封面全回来了

脚本是**增量同步**：按 MD5 复用已存在的文件，删掉的文件下次同步时自动清理；
没有内嵌标签的文件会按「文件夹名 = 专辑、上层文件夹 = 歌手、文件名前缀 = 曲目号」自动补全。

### 铁律

- 永远不要在访达里对 iPod 点「恢复」
- 不要手动进 `iPod_Control` 删文件；从源文件夹删歌再重新同步即可
- nano 5G 拍的视频在 `DCIM` 文件夹里，像数码相机一样直接拷出来即可
