# 零基础完整教程：新款 Mac + Apple Music + 老 iPod 全自动导歌

> 本教程配套仓库 [ipod-modern-sync](https://github.com/myc722/ipod-modern-sync)。
> 适合「会复制粘贴、敢照着敲命令」的初学者。全程图形化操作只有一步（拖文件），其余都是复制粘贴。
>
> 已在 **iPod nano 5G + macOS 15** 上实测，累计导入 480+ 首、封面零丢失。
> 理论上支持 iOpenPod 能识别的所有转盘 iPod（mini / nano 1-5G / classic / video）。

---

## 整套流程长什么样

```
Apple Music 链接
      │
      ▼
① 下载器（amdl）        ← 需要 Apple Music 付费订阅账号，输出 .m4a，封面内嵌
      │
      ▼
② 同步脚本（本仓库）     ← 插着 iPod 跑一条命令：拷歌 + 重建数据库 + 写封面
      │
      ▼
   推出、重启 iPod → 有歌、有封面 ✅
```

**② 是这个仓库解决的**：macOS 从 Catalina（10.15）起，访达每次插 iPod 都会重写机身上的数据库并抹掉封面，还可能弹「未能读取」逼你恢复出厂。本仓库的看门狗让访达彻底不碰 iPod，同步脚本自己写数据库（含封面）。

**① 用社区开源下载器** [zhaarey/apple-music-downloader](https://github.com/zhaarey/apple-music-downloader)（amdl），音质可选，AAC 格式 iPod 直接认。这是全程最难装的一步，照着下面做。

---

## 开始前你需要

| 项目 | 说明 |
|---|---|
| Mac | macOS 10.15 及以上，Intel / Apple 芯片都行 |
| iPod | 转盘机型（nano、classic、mini、video），电量最好充到一半以上 |
| Apple Music **付费订阅** | 下载器要登录你的账号才能取流，任何区都行 |
| 数据线 | 一根能传数据的（有些便宜线只能充电） |
| 耐心 | 安装步骤一次性，装完以后每次导歌只要两条命令 |

---

## 第 0 步：装 Homebrew（Mac 的软件管家）

打开「终端」（访达 → 应用程序 → 实用工具 → 终端），粘贴：

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

装完按它最后两行提示，把 brew 加进环境变量（屏幕上会给出确切命令，照抄即可）。验证：

```bash
brew --version
```

显示版本号就 OK。

## 第 1 步：装看门狗 + 同步引擎（5 分钟）

终端里依次粘贴：

```bash
# 1. 进入你放本仓库的文件夹（按实际路径改）
cd ~/Downloads/ipod-modern-sync

# 2. 装看门狗（常驻仅占 1.6MB 内存，iPod 不插时几乎零开销）
./install_guard.sh

# 3. 装同步引擎和依赖
pip3 install iopenpod
brew install ffmpeg
```

再运行一条（禁止访达自动同步）：

```bash
defaults write com.apple.AMPDevicesAgent dontAutomaticallySyncIPods -bool true
```

> **验证**：插上 iPod，访达里它显示为**普通磁盘图标**，没有设备页、不弹窗。
> 这是正常且**必要**的形态——说明看门狗生效了，访达不会再乱动你的 iPod。

## 第 2 步：装下载器 amdl（最难的一步，20-30 分钟）

amdl 本身是个命令行程序，但它解密音乐需要一个跑在虚拟机里的授权服务（wrapper-lite）。好在都有预编译版本，不用自己编译。

### 2.1 装 wrapper-lite-qemu（解密服务）

1. 打开 [wrapper-lite 的 GitHub Releases 页](https://github.com/itouakirai/wrapper-lite/releases)，下载带 `qemu` 的 macOS 预编译包（Apple 芯片选 arm64，Intel 选 x86_64），解压到用户目录：

   ```bash
   mkdir -p ~/wrapper-lite-qemu
   # 把解压出来的 qemu/ 文件夹和 wrapper-lite-qemu 程序放进 ~/wrapper-lite-qemu
   ```

2. 首次登录（用你的 Apple Music 账号）：

   ```bash
   cd ~/wrapper-lite-qemu
   ./wrapper-lite-qemu --login 你的账号:你的密码 --code-from-file
   ```

   开了双重验证的话，把收到的 6 位验证码写进 `data/2fa.txt` 文件，服务会自己去读。登录成功后会缓存令牌，以后不用反复登录。

3. 启动服务。仓库里提供了一个双击即用的小脚本（`amdl-helpers/启动服务.command`），也可以手动：

   ```bash
   ./wrapper-lite-qemu --base-dir data --port 12340
   ```

   服务启动后要 **等 1-2 分钟**（它在后台启动虚拟机）。判断就绪的唯一标准：

   ```bash
   curl -s http://127.0.0.1:12340/status
   ```

   输出里出现 `SUCCESS` 才算好了。**只看端口通不通会误判**——虚拟机没起来的时候端口会 connection reset，这是正常现象，不是装坏了。

> wrapper 服务运行时占约 512MB 内存。电脑内存紧张的话，不用时按 Ctrl+C 停掉，下次下载前再启动。

### 2.2 装 amdl 主程序

1. 打开 [zhaarey/apple-music-downloader 的 Releases 页](https://github.com/zhaarey/apple-music-downloader/releases)下载对应芯片的 `amdl` 二进制；或者如果你有 Go 环境：

   ```bash
   git clone https://github.com/zhaarey/apple-music-downloader.git ~/apple-music-downloader
   cd ~/apple-music-downloader && go build -o amdl .
   ```

2. 首次运行会生成 `config.yaml`，默认配置基本不用改。给 iPod 用注意这两行：

   ```yaml
   aac-type: aac-lc      # iPod 兼容性最好的 AAC 规格
   embed-cover: true     # 封面内嵌进文件（同步时封面来源就是它）
   ```

3. 下载一首歌测试（记得先确认 wrapper 服务是 SUCCESS 状态）：

   ```bash
   cd ~/apple-music-downloader
   ./amdl --aac "https://music.apple.com/cn/album/xxxxxxxx"
   ```

   看到 `Completed` 横幅、文件夹里出现 `AM-DL-AAC downloads/歌手/专辑/` 就成功了。

> 仓库 `amdl-helpers/` 里有两个双击即用的小脚本（macOS 下 .command 文件双击就能跑）：
> **下载音乐.command**（粘贴链接即下载）和 **转iPod格式.command**（把封面统一修成老 iPod 认的纯净 600x600 JPEG）。
> 把它们拷进 amdl 文件夹里用，不用记命令。

## 第 3 步：日常导歌（每次只要这两条）

```bash
# ① 下载（链接从 Apple Music App / 网页右键复制）
cd ~/apple-music-downloader && ./amdl --aac "专辑链接"

# ② 同步进 iPod（iPod 要插着）
cd ~/ipod-modern-sync && python3 sync_ipod.py --music-dir ~/apple-music-downloader/"AM-DL-AAC downloads"
```

同步脚本会自动：拷贝新歌（已存在的按 MD5 秒过）→ 清理你删掉的 → 重建数据库 → **从文件内嵌封面提取图片写进 iPod 的封面库**。

然后推出 iPod（访达里点推出，或 `diskutil eject /Volumes/iPod`），**重启 iPod**（菜单键 + 中间圆键按住 6 秒），开机即有歌有封面。

---

## 常见问题（都是实测踩过的）

| 症状 | 原因 & 解法 |
|---|---|
| `curl : (7) connection reset`，amdl 报连不上 | 虚拟机还没起来。**等 1-2 分钟**，以 `/status` 返回 SUCCESS 为准，别急着重装 |
| 下载数量比专辑曲目少 | 多半是**该地区下架**的曲目，谁都下不了，正常现象。以 amdl 的 Completed 横幅为准，网页写的"N 首歌曲"可能虚高 |
| iPod 里歌有、封面没有 | 先**重启 iPod**（菜单+中键 6 秒）；还不行就重跑一次同步脚本，它是幂等的，重跑只会修不会坏 |
| 访达里 iPod 显示成普通磁盘 | **这是看门狗生效的正常形态**，不是坏了 |
| 弹「未能读取 iPod 的内容」 | 看门狗没装上或没生效。千万别点「恢复」，先跑 `./install_guard.sh`，再重跑同步 |
| wrapper 占内存 | 不用时 Ctrl+C 或 `launchctl unload ~/Library/LaunchAgents/com.wrapper-lite.service.plist`，下次用再启动 |
| 同步脚本报错找不到 iPod | 确认 iPod 已挂载（访达侧边栏能看到盘符）、看门狗已装 |
| 想删歌 | 从电脑的音乐文件夹里删，再跑一次同步，iPod 里自动清掉。**永远不要手删 iPod_Control 里的文件** |

## 三条铁律（违反任何一条都可能清空 iPod）

1. **永远不要在访达里对 iPod 点「恢复」**——那是全盘格式化，歌全没。
2. **不要手动进 `iPod_Control` 文件夹删东西**。
3. 想删歌 → 从源文件夹删 → 重跑同步。

## 卸载

```bash
launchctl unload ~/Library/LaunchAgents/com.ipod-sync.guard.plist
rm ~/Library/LaunchAgents/com.ipod-sync.guard.plist
rm -rf "$HOME/Library/Application Support/ipod-modern-sync"
```

## 免责声明

本项目仅供个人学习与备份自己有权收藏的音乐，请支持正版。与 Apple 无关，未获 Apple 认可。下载器部分请遵守其各自仓库的许可条款。
