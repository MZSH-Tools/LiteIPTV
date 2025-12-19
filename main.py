#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LiteIPTV - 精简稳定的 CCTV 直播源
每小时运行，多轮测速取最优，仅在源变化时更新
"""

import asyncio
import json
import os
import random
import re
import subprocess
import tempfile
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

import aiohttp

# 项目根目录
RootDir = Path(__file__).parent

# 日志目录（跨平台）
import sys
if sys.platform == "win32":
    LogDir = RootDir / "Logs"
else:
    LogDir = Path.home() / "Library/Logs/LiteIPTV"
LogFile = LogDir / "LiteIPTV.log"


def Log(msg):
    """输出日志到终端和日志文件"""
    print(msg, flush=True)
    with open(LogFile, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


# CCTV 频道配置
Channels = {
    "CCTV-1": {"name": "CCTV-1 综合", "tvg_name": "CCTV1", "logo": "https://live.fanmingming.cn/tv/CCTV1.png"},
    "CCTV-2": {"name": "CCTV-2 财经", "tvg_name": "CCTV2", "logo": "https://live.fanmingming.cn/tv/CCTV2.png"},
    "CCTV-3": {"name": "CCTV-3 综艺", "tvg_name": "CCTV3", "logo": "https://live.fanmingming.cn/tv/CCTV3.png"},
    "CCTV-4": {"name": "CCTV-4 中文国际", "tvg_name": "CCTV4", "logo": "https://live.fanmingming.cn/tv/CCTV4.png"},
    "CCTV-5": {"name": "CCTV-5 体育", "tvg_name": "CCTV5", "logo": "https://live.fanmingming.cn/tv/CCTV5.png"},
    "CCTV-5+": {"name": "CCTV-5+ 体育赛事", "tvg_name": "CCTV5+", "logo": "https://live.fanmingming.cn/tv/CCTV5+.png"},
    "CCTV-6": {"name": "CCTV-6 电影", "tvg_name": "CCTV6", "logo": "https://live.fanmingming.cn/tv/CCTV6.png"},
    "CCTV-7": {"name": "CCTV-7 国防军事", "tvg_name": "CCTV7", "logo": "https://live.fanmingming.cn/tv/CCTV7.png"},
    "CCTV-8": {"name": "CCTV-8 电视剧", "tvg_name": "CCTV8", "logo": "https://live.fanmingming.cn/tv/CCTV8.png"},
    "CCTV-9": {"name": "CCTV-9 纪录", "tvg_name": "CCTV9", "logo": "https://live.fanmingming.cn/tv/CCTV9.png"},
    "CCTV-10": {"name": "CCTV-10 科教", "tvg_name": "CCTV10", "logo": "https://live.fanmingming.cn/tv/CCTV10.png"},
    "CCTV-11": {"name": "CCTV-11 戏曲", "tvg_name": "CCTV11", "logo": "https://live.fanmingming.cn/tv/CCTV11.png"},
    "CCTV-12": {"name": "CCTV-12 社会与法", "tvg_name": "CCTV12", "logo": "https://live.fanmingming.cn/tv/CCTV12.png"},
    "CCTV-13": {"name": "CCTV-13 新闻", "tvg_name": "CCTV13", "logo": "https://live.fanmingming.cn/tv/CCTV13.png"},
    "CCTV-14": {"name": "CCTV-14 少儿", "tvg_name": "CCTV14", "logo": "https://live.fanmingming.cn/tv/CCTV14.png"},
    "CCTV-15": {"name": "CCTV-15 音乐", "tvg_name": "CCTV15", "logo": "https://live.fanmingming.cn/tv/CCTV15.png"},
    "CCTV-16": {"name": "CCTV-16 奥林匹克", "tvg_name": "CCTV16", "logo": "https://live.fanmingming.cn/tv/CCTV16.png"},
    "CCTV-17": {"name": "CCTV-17 农业农村", "tvg_name": "CCTV17", "logo": "https://live.fanmingming.cn/tv/CCTV17.png"},
}

# 频道匹配正则
ChannelPatterns = [
    (r"CCTV[-\s]?1(?:[^\d+]|$)", "CCTV-1"),
    (r"CCTV[-\s]?2(?:[^\d]|$)", "CCTV-2"),
    (r"CCTV[-\s]?3(?:[^\d]|$)", "CCTV-3"),
    (r"CCTV[-\s]?4(?:[^\d]|$)", "CCTV-4"),
    (r"CCTV[-\s]?5\+|CCTV[-\s]?5加|CCTV5\+", "CCTV-5+"),
    (r"CCTV[-\s]?5(?:[^\d+]|$)", "CCTV-5"),
    (r"CCTV[-\s]?6(?:[^\d]|$)", "CCTV-6"),
    (r"CCTV[-\s]?7(?:[^\d]|$)", "CCTV-7"),
    (r"CCTV[-\s]?8(?:[^\d]|$)", "CCTV-8"),
    (r"CCTV[-\s]?9(?:[^\d]|$)", "CCTV-9"),
    (r"CCTV[-\s]?10(?:[^\d]|$)", "CCTV-10"),
    (r"CCTV[-\s]?11(?:[^\d]|$)", "CCTV-11"),
    (r"CCTV[-\s]?12(?:[^\d]|$)", "CCTV-12"),
    (r"CCTV[-\s]?13(?:[^\d]|$)", "CCTV-13"),
    (r"CCTV[-\s]?14(?:[^\d]|$)", "CCTV-14"),
    (r"CCTV[-\s]?15(?:[^\d]|$)", "CCTV-15"),
    (r"CCTV[-\s]?16(?:[^\d]|$)", "CCTV-16"),
    (r"CCTV[-\s]?17(?:[^\d]|$)", "CCTV-17"),
]


def LoadConfig():
    """加载配置文件"""
    path = RootDir / "config.json"
    if not path.exists():
        Log("错误: 未找到 config.json")
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def SaveConfig(cfg):
    """保存配置文件，内容相同则跳过"""
    path = RootDir / "config.json"
    content = json.dumps(cfg, ensure_ascii=False, indent=2)
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def GetSourceName(url):
    """从 URL 提取源名称"""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        # GitHub 链接显示用户名
        if "githubusercontent.com" in host or "github.com" in host:
            parts = parsed.path.split("/")
            if len(parts) >= 2:
                return parts[1]
        # 其他链接显示域名
        return host.replace("www.", "")
    except:
        pass
    return url[:30]


async def FetchSource(url, maxRetry, retryDelay):
    """抓取单个上游源，失败时重试，返回 (url, items, success)"""
    name = GetSourceName(url)

    for attempt in range(maxRetry):
        try:
            connector = aiohttp.TCPConnector()
            async with aiohttp.ClientSession(connector=connector, trust_env=False) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30), ssl=False) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        if content:
                            items = ParseM3U(content)
                            for item in items:
                                item["source"] = name
                            Log(f"已抓取 {name}: {len(items)} 个频道")
                            return url, items, True
            if attempt < maxRetry - 1:
                await asyncio.sleep(retryDelay)
        except:
            if attempt < maxRetry - 1:
                await asyncio.sleep(retryDelay)

    Log(f"抓取失败 {name}: {maxRetry} 次尝试均失败")
    return url, [], False


async def FetchAllSources(sources, maxRetry, retryDelay):
    """并行抓取所有上游源"""
    tasks = [FetchSource(url, maxRetry, retryDelay) for url in sources]
    results = await asyncio.gather(*tasks)

    allItems = []
    for url, items, success in results:
        allItems.extend(items)

    return allItems


def ParseM3U(content):
    """解析 m3u 文件"""
    items = []
    lines = content.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            match = re.search(r',(.+)$', line)
            if match and i + 1 < len(lines):
                name = match.group(1).strip()
                url = lines[i + 1].strip()
                if "#" in url:
                    url = url.split("#")[0]
                if url and not url.startswith("#"):
                    items.append({"name": name, "url": url})
                i += 1
        i += 1
    return items


def MatchChannel(name):
    """匹配频道名到标准频道 ID"""
    upper = name.upper()
    for pattern, chId in ChannelPatterns:
        if re.search(pattern, upper, re.IGNORECASE):
            return chId
    return None


def IsBlacklisted(url, blacklist):
    """检查 URL 是否在黑名单中"""
    for pattern in blacklist:
        if pattern in url:
            return True
    return False


def IsIPv6Url(url):
    """检查是否为 IPv6 地址"""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if host.startswith("[") or ":" in host:
            return True
    except:
        pass
    return False


def FilterChannels(allItems, blacklist=None):
    """筛选 CCTV 频道，返回 {chId: [(url, source), ...]}"""
    if blacklist is None:
        blacklist = []
    result = {ch: [] for ch in Channels}
    blacklisted = 0
    ipv6Filtered = 0
    for item in allItems:
        url = item["url"]
        if IsBlacklisted(url, blacklist):
            blacklisted += 1
            continue
        # 过滤 IPv6 源
        if IsIPv6Url(url):
            ipv6Filtered += 1
            continue
        chId = MatchChannel(item["name"])
        if chId:
            result[chId].append((url, item.get("source", "unknown")))
    if blacklisted > 0:
        Log(f"黑名单过滤: {blacklisted} 个源")
    if ipv6Filtered > 0:
        Log(f"IPv6 过滤: {ipv6Filtered} 个源")
    return result


# ==================== 测速模块（参考 iptv-api 优化） ====================

async def AioFetch(url, timeout=10):
    """使用 aiohttp 获取内容"""
    connector = aiohttp.TCPConnector()
    try:
        async with aiohttp.ClientSession(connector=connector, trust_env=False) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), ssl=False) as resp:
                if resp.status == 200:
                    return await resp.text()
    except:
        pass
    return None


async def AioDownload(url, timeout=10):
    """使用 aiohttp 下载并返回指标"""
    connector = aiohttp.TCPConnector()
    try:
        startTime = time.time()
        async with aiohttp.ClientSession(connector=connector, trust_env=False) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), ssl=False) as resp:
                ttfb = time.time() - startTime
                if resp.status == 200:
                    data = await resp.read()
                    totalTime = time.time() - startTime
                    size = len(data)
                    speed = size / totalTime if totalTime > 0 else 0
                    return {"bytes": size, "speed": speed, "ttfb": ttfb, "total": totalTime}
    except:
        pass
    return None


def ParseM3u8Segments(content, baseUrl):
    """解析 m3u8 获取 ts 分片地址"""
    segments = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            if line.startswith("http"):
                segments.append(line)
            elif line.startswith("/"):
                parsed = urlparse(baseUrl)
                segments.append(f"{parsed.scheme}://{parsed.netloc}{line}")
            else:
                segments.append(urljoin(baseUrl, line))
    return segments


def ParseResolution(content):
    """从 Master Playlist 解析最高分辨率，返回高度值（如 1080, 720）"""
    if "#EXT-X-STREAM-INF" not in content:
        return 0

    maxHeight = 0
    for line in content.strip().split("\n"):
        if "#EXT-X-STREAM-INF" in line:
            match = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
            if match:
                height = int(match.group(2))
                maxHeight = max(maxHeight, height)
    return maxHeight


async def GetResolutionFromSegment(segUrl, timeout=10):
    """从 ts 分片获取分辨率（使用 ffprobe）
    返回值：
        > 0: 视频高度（如 1080, 720）
        0: 未知（ffprobe 失败但可能有视频）
        -1: 确认无视频流（只有音频）
    """
    try:
        # 下载分片到临时文件
        connector = aiohttp.TCPConnector()
        async with aiohttp.ClientSession(connector=connector, trust_env=False) as session:
            async with session.get(segUrl, timeout=aiohttp.ClientTimeout(total=timeout), ssl=False) as resp:
                if resp.status != 200:
                    return 0
                data = await resp.read()
                if len(data) < 1000:
                    return 0

        # 写入临时文件
        with tempfile.NamedTemporaryFile(suffix=".ts", delete=False) as f:
            f.write(data)
            tmpPath = f.name

        try:
            # 先检查是否有视频流
            checkResult = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v",
                 "-show_entries", "stream=codec_type", "-of", "csv=p=0", tmpPath],
                capture_output=True, text=True, timeout=5
            )
            # 没有视频流（只有音频）
            if checkResult.returncode == 0 and not checkResult.stdout.strip():
                return -1

            # 有视频流，获取分辨率
            result = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=height", "-of", "csv=p=0", tmpPath],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip())
        finally:
            os.unlink(tmpPath)
    except:
        pass
    return 0


async def TestUrl(url, timeout=30):
    """测试单个 URL：下载前 5 个 ts 分片（参考 iptv-api）"""
    # 获取 m3u8 内容
    content = await AioFetch(url, timeout=10)
    if not content:
        return None

    # 处理 Master Playlist
    if "#EXT-X-STREAM-INF" in content:
        lines = content.strip().split("\n")
        for i, line in enumerate(lines):
            if "#EXT-X-STREAM-INF" in line and i + 1 < len(lines):
                subUrl = lines[i + 1].strip()
                if not subUrl.startswith("http"):
                    subUrl = urljoin(url, subUrl)
                content = await AioFetch(subUrl, timeout=10)
                if not content:
                    return None
                url = subUrl
                break

    # 验证有分片
    if "#EXTINF" not in content:
        return None

    # 解析分片
    segments = ParseM3u8Segments(content, url)
    if not segments:
        return None

    # 并发下载前 5 个分片
    testSegs = segments[:5]
    tasks = [AioDownload(seg, timeout=10) for seg in testSegs]
    segResults = await asyncio.gather(*tasks)
    results = [r for r in segResults if r]

    if len(results) < 2:  # 至少 2 个分片成功
        return None

    # 计算指标
    avgSpeed = sum(r["speed"] for r in results) / len(results)
    avgTtfb = sum(r["ttfb"] for r in results) / len(results)
    totalBytes = sum(r["bytes"] for r in results)

    # 计算稳定性（速率标准差）
    speeds = [r["speed"] for r in results]
    avgSpd = sum(speeds) / len(speeds)
    variance = sum((s - avgSpd) ** 2 for s in speeds) / len(speeds) if len(speeds) > 1 else 0
    speedStd = variance ** 0.5

    return {
        "speed": avgSpeed,
        "ttfb": avgTtfb,
        "bytes": totalBytes,
        "segments": len(results),
        "speedStd": speedStd
    }


async def DeepVerify(url, timeout=10):
    """深度验证：下载 3 个随机分片，返回 (是否通过, 分辨率高度)
    分辨率返回值：
        > 0: 有视频，返回高度
        0: 未知（可能有视频）
        -1: 只有音频，无视频（会被过滤）
    """
    content = await AioFetch(url, timeout=5)
    if not content:
        return False, 0

    # 尝试从 Master Playlist 解析分辨率
    resolution = ParseResolution(content)

    # 处理 Master Playlist
    if "#EXT-X-STREAM-INF" in content:
        lines = content.strip().split("\n")
        for i, line in enumerate(lines):
            if "#EXT-X-STREAM-INF" in line and i + 1 < len(lines):
                subUrl = lines[i + 1].strip()
                if not subUrl.startswith("http"):
                    subUrl = urljoin(url, subUrl)
                content = await AioFetch(subUrl, timeout=5)
                if not content:
                    return False, 0
                url = subUrl
                break

    if "#EXTINF" not in content:
        return False, 0

    segments = ParseM3u8Segments(content, url)
    if len(segments) < 3:
        return False, 0

    # 随机选择 3 个不同分片
    testSegs = random.sample(segments, min(3, len(segments)))

    # 并发下载，全部成功才算通过
    tasks = [AioDownload(seg, timeout=timeout) for seg in testSegs]
    results = await asyncio.gather(*tasks)

    for r in results:
        if not r or r["bytes"] < 1000:
            return False, 0

    # 如果没有从 Master Playlist 获取到分辨率，用 ffprobe 解析分片
    if resolution == 0 and segments:
        resolution = await GetResolutionFromSegment(segments[0], timeout=10)
        # 只有音频没有视频，标记为失败
        if resolution == -1:
            return False, -1

    return True, resolution


async def SelectBestSources(chDict, timeout=30, maxConcur=100, hdLatencyLimit=2):
    """为每个频道选择最优源"""
    # 构建 URL -> [(chId, src), ...] 映射，实现全局去重
    urlMap = {}
    for chId, urlList in chDict.items():
        for url, src in urlList:
            if url not in urlMap:
                urlMap[url] = []
            urlMap[url].append((chId, src))

    if not urlMap:
        return {}

    allUrls = list(urlMap.keys())
    Log(f"待测试: {len(allUrls)} 个唯一 URL")
    sem = asyncio.Semaphore(maxConcur)

    # 第一步：快速测试（m3u8 有内容）
    Log(f"--- 快速测试 ---")

    async def quickCheck(url):
        async with sem:
            content = await AioFetch(url, timeout=5)
            return content is not None and ("#EXTINF" in content or "#EXT-X-STREAM-INF" in content)

    tasks = [quickCheck(url) for url in allUrls]
    results = await asyncio.gather(*tasks)
    quickUrls = [url for url, ok in zip(allUrls, results) if ok]
    Log(f"通过: {len(quickUrls)}/{len(allUrls)}")

    if not quickUrls:
        Log("没有可用源")
        return {}

    # 第二步：连通+测速（下载分片验证连通性，同时测速）
    Log(f"--- 连通测速 ---")

    async def connectAndTest(url):
        """下载分片验证连通性，同时返回测速数据"""
        async with sem:
            return await TestUrl(url, timeout)

    tasks = [connectAndTest(url) for url in quickUrls]
    results = await asyncio.gather(*tasks)

    urlScores = {}
    for url, result in zip(quickUrls, results):
        if result:
            urlScores[url] = {"ttfb": result["ttfb"], "speed": result["speed"]}

    Log(f"通过: {len(urlScores)}/{len(quickUrls)}")

    if not urlScores:
        Log("没有可连接的源")
        return {}

    # 第三步：所有频道并行深度验证（优先 1080p）
    Log(f"--- 深度验证 ---")

    audioOnlyCount = 0  # 统计纯音频源数量

    async def verifyChannel(chId):
        """单频道验证：按延迟排序，优先 1080p，延迟超限用备选"""
        nonlocal audioOnlyCount
        candidates = []
        for url, src in chDict.get(chId, []):
            if url in urlScores:
                data = urlScores[url]
                candidates.append((data["ttfb"], url))

        if not candidates:
            return None

        # 按延迟升序排序
        candidates.sort(key=lambda x: x[0])

        backup = None

        for ttfb, url in candidates:
            # 延迟超过阈值且有备选，停止找 1080p
            if ttfb > hdLatencyLimit and backup:
                break

            passed, resolution = await DeepVerify(url, timeout=10)
            if passed:
                if resolution >= 1080:
                    return (chId, url, resolution)
                elif backup is None:
                    backup = (chId, url, resolution)
            elif resolution == -1:
                # 纯音频源，统计但不使用
                audioOnlyCount += 1

        return backup

    # 所有频道并行验证
    tasks = [verifyChannel(chId) for chId in Channels]
    results = await asyncio.gather(*tasks)

    best = {}
    bestResolutions = {}
    for r in results:
        if r:
            chId, url, resolution = r
            best[chId] = url
            bestResolutions[chId] = resolution

    # 输出统计
    if audioOnlyCount > 0:
        Log(f"过滤纯音频源: {audioOnlyCount} 个")

    resStats = {}
    for chId, res in bestResolutions.items():
        label = f"{res}p" if res > 0 else "未知"
        resStats[label] = resStats.get(label, 0) + 1
    resInfo = ", ".join(f"{k}:{v}" for k, v in sorted(resStats.items(), reverse=True))
    Log(f"选出最优源: {len(best)}/{len(Channels)} 个频道 ({resInfo})")

    return best


def LoadExistingM3U(filename):
    """读取现有的 m3u 文件，返回 {chId: url}"""
    path = RootDir / filename
    if not path.exists():
        return {}

    existing = {}
    content = path.read_text(encoding="utf-8")
    lines = content.strip().split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            # 匹配频道名
            match = re.search(r',(.+)$', line)
            if match and i + 1 < len(lines):
                name = match.group(1).strip()
                url = lines[i + 1].strip()
                # 从频道名匹配 chId
                chId = MatchChannel(name)
                if chId and url and not url.startswith("#"):
                    existing[chId] = url
                i += 1
        i += 1
    return existing


def GenerateM3U(sources, filename):
    """生成 m3u 文件，保留旧源（新源未覆盖的频道）"""
    # 读取现有源
    existing = LoadExistingM3U(filename)
    preserved = 0

    # 合并：新源优先，无新源则保留旧源
    merged = {}
    for chId in Channels:
        if chId in sources:
            merged[chId] = sources[chId]
        elif chId in existing:
            merged[chId] = existing[chId]
            preserved += 1

    if not merged:
        Log(f"跳过 {filename}: 无可用源")
        return False

    if preserved > 0:
        Log(f"保留旧源: {preserved} 个频道")

    lines = ['#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"']
    for chId in Channels:
        if chId in merged:
            info = Channels[chId]
            lines.append(f'#EXTINF:-1 tvg-name="{info["tvg_name"]}" tvg-logo="{info["logo"]}" group-title="央视频道",{info["name"]}')
            lines.append(merged[chId])

    content = "\n".join(lines) + "\n"
    path = RootDir / filename

    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def HasChanges():
    """检查 iptv.m3u 是否有变化"""
    diff = subprocess.run(
        ["git", "diff", "--name-only", "iptv.m3u"],
        capture_output=True, text=True, cwd=RootDir
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "iptv.m3u"],
        capture_output=True, text=True, cwd=RootDir
    )
    return bool(diff.stdout.strip() or untracked.stdout.strip())


def CommitAndPush():
    """提交并推送 iptv.m3u"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"update: {now}"
    subprocess.run(["git", "add", "iptv.m3u"], cwd=RootDir)
    subprocess.run(["git", "commit", "-m", msg], cwd=RootDir)
    subprocess.run(["git", "push"], cwd=RootDir)
    Log(f"已推送: {msg}")


async def RunOnce():
    """执行一次抓取测速流程"""
    Log(f"=== LiteIPTV 开始: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    cfg = LoadConfig()
    if not cfg:
        return

    # 读取配置
    settings = cfg.get("设置", {})
    maxRetry = settings.get("抓取重试次数", 3)
    retryDelay = settings.get("抓取重试间隔秒", 3)
    timeout = settings.get("测速超时秒", 30)
    maxConcur = settings.get("最大并发数", 500)
    hdLatencyLimit = settings.get("高清延迟阈值毫秒", 2000) / 1000  # 转换为秒

    # 并行抓取所有上游源
    Log("--- 抓取上游源 ---")
    allItems = await FetchAllSources(cfg.get("上游源", []), maxRetry, retryDelay)
    Log(f"共抓取 {len(allItems)} 个频道")

    # 筛选 CCTV 频道（过滤黑名单和 IPv6）
    blacklist = cfg.get("黑名单", [])
    chDict = FilterChannels(allItems, blacklist)

    # 合并散装源
    customSources = cfg.get("散装源", {})
    customCount = 0
    for chId, urls in customSources.items():
        if chId in chDict and urls:
            for url in urls:
                chDict[chId].append((url, "自定义"))
                customCount += 1
    if customCount > 0:
        Log(f"添加散装源: {customCount} 个")

    totalUrls = sum(len(urls) for urls in chDict.values())
    uniqueUrls = len(set(url for urls in chDict.values() for url, _ in urls))
    Log(f"筛选出 CCTV 频道: {totalUrls} 个源 ({uniqueUrls} 个唯一)")

    best = await SelectBestSources(chDict, timeout, maxConcur, hdLatencyLimit)

    # 生成 m3u 文件
    GenerateM3U(best, "iptv.m3u")

    Log(f"\n生成完成: iptv.m3u ({len(best)} 个频道)")

    # 检查变化并提交
    if HasChanges():
        CommitAndPush()
    else:
        Log("无变化，跳过推送")

    Log(f"=== LiteIPTV 结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")


async def Main():
    """主函数 - 单次执行模式（由 launchd 定时调度）"""
    # 初始化日志目录
    LogDir.mkdir(parents=True, exist_ok=True)
    # 清空日志文件
    LogFile.write_text("")

    try:
        await RunOnce()
    except Exception as e:
        Log(f"执行出错: {e}")


if __name__ == "__main__":
    asyncio.run(Main())
