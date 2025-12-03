# LiteIPTV

精简、稳定的 CCTV 直播源，专为国内用户设计。

## 前因后果

因当前电视盒子广告横行，家中老人屡被蒙骗，随购买Apple TV欲取代电视盒子，可惜网络上IPTV源繁杂且不稳定，所以起了这个念头，我想为国内老人也为我家里老人写一个项目，这个项目很简单，综合多个上流源来并且通过比较保留最稳定的源，且只保留18个CCTV频道，希望天下老人都有一个快乐安逸的晚年。

## 功能特点

- **精简**：只保留 CCTV 央视频道（1-17 + 5+）
- **高清**：只接受 1080p 源
- **稳定**：模拟真实播放测速，连续下载多个 ts 分片评估稳定性
- **双栈**：同时提供 IPv4 和 IPv6 源
- **自动更新**：每天凌晨自动检测，多轮测速取最优，仅在源变化时更新

## 订阅地址

在支持 m3u 的播放器中添加订阅地址（如失效请尝试其他线路）：

| 线路 | IPv4 | IPv6 |
|------|------|------|
| 线路1 | `https://mirror.ghproxy.com/https://raw.githubusercontent.com/MZSH-Tools/LiteIPTV/main/ipv4.m3u` | `https://mirror.ghproxy.com/https://raw.githubusercontent.com/MZSH-Tools/LiteIPTV/main/ipv6.m3u` |
| 线路2 | `https://ghfast.top/https://raw.githubusercontent.com/MZSH-Tools/LiteIPTV/main/ipv4.m3u` | `https://ghfast.top/https://raw.githubusercontent.com/MZSH-Tools/LiteIPTV/main/ipv6.m3u` |
| 线路3 | `https://gh-proxy.com/https://raw.githubusercontent.com/MZSH-Tools/LiteIPTV/main/ipv4.m3u` | `https://gh-proxy.com/https://raw.githubusercontent.com/MZSH-Tools/LiteIPTV/main/ipv6.m3u` |
| 线路4 | `https://ghproxy.net/https://raw.githubusercontent.com/MZSH-Tools/LiteIPTV/main/ipv4.m3u` | `https://ghproxy.net/https://raw.githubusercontent.com/MZSH-Tools/LiteIPTV/main/ipv6.m3u` |

> 目前仅收录 CCTV 央视频道

## 频道列表

| 频道 | 名称 |
|------|------|
| CCTV-1 | 综合 |
| CCTV-2 | 财经 |
| CCTV-3 | 综艺 |
| CCTV-4 | 中文国际 |
| CCTV-5 | 体育 |
| CCTV-5+ | 体育赛事 |
| CCTV-6 | 电影 |
| CCTV-7 | 国防军事 |
| CCTV-8 | 电视剧 |
| CCTV-9 | 纪录 |
| CCTV-10 | 科教 |
| CCTV-11 | 戏曲 |
| CCTV-12 | 社会与法 |
| CCTV-13 | 新闻 |
| CCTV-14 | 少儿 |
| CCTV-15 | 音乐 |
| CCTV-16 | 奥林匹克 |
| CCTV-17 | 农业农村 |

---

## 自建部署

如果你想自己部署这个项目，请按以下步骤操作。

### 环境要求

- macOS（使用 launchd 守护进程）
- Python 3.x
- curl
- ffprobe（用于检测分辨率，`brew install ffmpeg`）
- git

### 配置文件

编辑 `config.json`：

```json
{
  "设置": {
    "测速轮数": 3,
    "测速间隔秒": 300,
    "测速超时秒": 30,
    "最大并发数": 500,
    "自动禁用失效源": true
  },
  "上游源": [
    {
      "名称": "source-name",
      "地址": "https://example.com/iptv.m3u",
      "启用": true
    }
  ]
}
```

| 参数 | 说明 |
|------|------|
| 测速轮数 | 每个 URL 测试的次数 |
| 测速间隔秒 | 每轮测速之间的等待时间 |
| 测速超时秒 | 单次分片下载超时时间 |
| 最大并发数 | 同时测速的最大 URL 数量 |
| 自动禁用失效源 | 上游源所有频道失效时自动禁用 |

### 快速验证

```bash
# 方式一：使用测试脚本
./test.sh

# 方式二：直接运行（快速模式：1轮测速）
QUICK_TEST=1 python3 main.py

# 方式三：完整运行
python3 main.py
```

### 安装守护进程

1. 修改 `com.liteiptv.update.plist` 中的路径：
   - `ProgramArguments`: Python 路径和 main.py 路径
   - `WorkingDirectory`: 项目目录

2. 安装守护进程：

```bash
# 复制到 LaunchAgents
cp com.liteiptv.update.plist ~/Library/LaunchAgents/

# 加载
launchctl load ~/Library/LaunchAgents/com.liteiptv.update.plist

# 查看状态
launchctl list | grep liteiptv

# 查看日志
tail -f ~/Library/Logs/LiteIPTV/LiteIPTV.log
```

3. 卸载守护进程：

```bash
launchctl unload ~/Library/LaunchAgents/com.liteiptv.update.plist
rm ~/Library/LaunchAgents/com.liteiptv.update.plist
```

### 运行模式

launchd 定时调度，每天凌晨 3 点自动执行一次。程序执行完毕后退出，下次定时再启动。

## 许可证

MIT
