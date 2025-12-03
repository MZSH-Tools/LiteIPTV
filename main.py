#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LiteIPTV - 精简稳定的 CCTV 直播源
每小时运行，多轮测速取最优，仅在源变化时更新
"""

import asyncio
import json
import os
import re
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path

import aiohttp

# 项目根目录
RootDir = Path(__file__).parent


# 日志目录
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


def FetchSource(src, maxRetry, retryDelay):
    """抓取单个上游源，失败时重试，返回 (items, success)"""
    if not src.get("启用", True):
        return [], True  # 未启用不算失败

    url = src["地址"]
    name = src.get("名称", url)

    for attempt in range(maxRetry):
        try:
            result = subprocess.run(
                ["curl", "-s", "-L", "--noproxy", "*", "--max-time", "30", url],
                capture_output=True, text=True
            )
            if result.returncode == 0 and result.stdout:
                items = ParseM3U(result.stdout)
                for item in items:
                    item["source"] = name
                Log(f"已抓取 {name}: {len(items)} 个频道")
                return items, True
            if attempt < maxRetry - 1:
                time.sleep(retryDelay)
        except:
            if attempt < maxRetry - 1:
                time.sleep(retryDelay)

    Log(f"抓取失败 {name}: {maxRetry} 次尝试均失败")
    return [], False


async def FetchAllSources(sources, cfg, maxRetry, retryDelay):
    """并行抓取所有上游源，抓取失败的源自动禁用"""
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, FetchSource, src, maxRetry, retryDelay) for src in sources]
    results = await asyncio.gather(*tasks)

    allItems = []
    disabled = []
    for src, (items, success) in zip(sources, results):
        allItems.extend(items)
        # 抓取失败则禁用
        if not success and src.get("启用", True):
            src["启用"] = False
            disabled.append(src.get("名称", src["地址"]))
            Log(f"已禁用抓取失败源: {src.get('名称', src['地址'])}")

    # 保存配置
    if disabled:
        SaveConfig(cfg)

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


def FilterChannels(allItems):
    """筛选 CCTV 频道，返回 {chId: [(url, source), ...]}"""
    result = {ch: [] for ch in Channels}
    for item in allItems:
        chId = MatchChannel(item["name"])
        if chId:
            result[chId].append((item["url"], item.get("source", "unknown")))
    return result


async def AioFetch(url, ipVer, timeout=10):
    """使用 aiohttp 获取内容（真异步，强制 IPv4/IPv6，跳过 SSL 验证）"""
    family = socket.AF_INET if ipVer == 4 else socket.AF_INET6
    connector = aiohttp.TCPConnector(family=family)
    try:
        async with aiohttp.ClientSession(connector=connector, trust_env=False) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), ssl=False) as resp:
                if resp.status == 200:
                    return await resp.text()
    except:
        pass
    return None


async def AioDownload(url, ipVer, timeout=5):
    """使用 aiohttp 下载并返回指标（真异步，跳过 SSL 验证）"""
    family = socket.AF_INET if ipVer == 4 else socket.AF_INET6
    connector = aiohttp.TCPConnector(family=family)
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
                    return {
                        "bytes": size,
                        "speed": speed,
                        "ttfb": ttfb,
                        "total": totalTime
                    }
    except:
        pass
    return None


def CurlFetch(url, ipVer, timeout=10):
    """使用 curl 获取内容（同步，用于 ffprobe 等场景）"""
    flag = "-4" if ipVer == 4 else "-6"
    try:
        result = subprocess.run(
            ["curl", flag, "-s", "-L", "--noproxy", "*", "--max-time", str(timeout), url],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            return result.stdout
    except:
        pass
    return None


def ParseM3u8Segments(content, baseUrl):
    """解析 m3u8 获取 ts 分片地址"""
    from urllib.parse import urlparse, urljoin
    segments = []
    for line in content.strip().split("\n"):
        line = line.strip()
        if line and not line.startswith("#"):
            if line.startswith("http"):
                segments.append(line)
            elif line.startswith("/"):
                # 绝对路径，需要用 host
                parsed = urlparse(baseUrl)
                segments.append(f"{parsed.scheme}://{parsed.netloc}{line}")
            else:
                # 相对路径，用 urljoin 处理
                segments.append(urljoin(baseUrl, line))
    return segments


def ParseM3u8Resolution(content):
    """从 m3u8 内容解析分辨率"""
    # 匹配 RESOLUTION=1920x1080 格式
    match = re.search(r'RESOLUTION=(\d+)x(\d+)', content)
    if match:
        return int(match.group(1)), int(match.group(2))
    return None, None


def DetectResolutionFfprobe(tsUrl, ipVer):
    """使用 ffprobe 检测 ts 分片分辨率（强制裸连，不使用代理）"""
    flag = "-4" if ipVer == 4 else "-6"
    try:
        # 使用 curl 下载分片到临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".ts", delete=False) as tmp:
            tmpPath = tmp.name

        result = subprocess.run(
            ["curl", flag, "-s", "-L", "--noproxy", "*", "--max-time", "10", "-o", tmpPath, tsUrl],
            capture_output=True
        )
        if result.returncode != 0:
            return None, None

        # 使用 ffprobe 检测分辨率
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height", "-of", "csv=p=0", tmpPath],
            capture_output=True, text=True
        )

        # 清理临时文件
        import os
        os.unlink(tmpPath)

        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            if len(parts) == 2:
                return int(parts[0]), int(parts[1])
    except:
        pass
    return None, None


def Is1080p(width, height):
    """判断是否为 1080p（高度 >= 1080）"""
    if width and height:
        return height >= 1080
    return False


async def CheckResolution(url, ipVer, cachedContent=None, debug=False):
    """检查 URL 分辨率，返回 (is1080p, width, height, reason)"""
    # 直播流分片会过期，必须重新获取最新 m3u8
    content = await AioFetch(url, ipVer, timeout=10)
    if not content:
        if debug:
            Log(f"  [DEBUG] {url[:50]}... fetch_failed")
        return False, None, None, "fetch_failed"

    # 检查是否是 Master Playlist（包含 EXT-X-STREAM-INF）
    if "#EXT-X-STREAM-INF" in content:
        # 解析最高分辨率的子播放列表
        bestRes, bestUrl = 0, None
        lines = content.strip().split("\n")
        for i, line in enumerate(lines):
            if "#EXT-X-STREAM-INF" in line:
                match = re.search(r'RESOLUTION=(\d+)x(\d+)', line)
                if match and i + 1 < len(lines):
                    w, h = int(match.group(1)), int(match.group(2))
                    res = w * h
                    if res > bestRes:
                        bestRes = res
                        subUrl = lines[i + 1].strip()
                        if subUrl.startswith("http"):
                            bestUrl = subUrl
                        elif subUrl.startswith("/"):
                            from urllib.parse import urlparse
                            parsed = urlparse(url)
                            bestUrl = f"{parsed.scheme}://{parsed.netloc}{subUrl}"
                        else:
                            from urllib.parse import urljoin
                            bestUrl = urljoin(url, subUrl)
        if bestUrl:
            content = await AioFetch(bestUrl, ipVer, timeout=10)
            if not content:
                return False, None, None, "sub_fetch_failed"
            url = bestUrl

    # 尝试从 m3u8 解析分辨率
    width, height = ParseM3u8Resolution(content)

    # 解析分片
    segments = ParseM3u8Segments(content, url)
    if not segments:
        return False, None, None, "no_segments"

    # 如果 m3u8 没有分辨率信息，用 ffprobe 检测第一个分片
    if not width or not height:
        if debug:
            Log(f"  [DEBUG] {url[:50]}... no m3u8 res, trying ffprobe on {segments[0][:50]}...")
        loop = asyncio.get_event_loop()
        width, height = await loop.run_in_executor(None, DetectResolutionFfprobe, segments[0], ipVer)

    if not width or not height:
        if debug:
            Log(f"  [DEBUG] {url[:50]}... detect_failed (w={width}, h={height})")
        return False, None, None, "detect_failed"

    if debug:
        Log(f"  [DEBUG] {url[:50]}... {width}x{height}")
    return Is1080p(width, height), width, height, "ok"


async def QuickConnectCheck(url, ipVer):
    """快速连通性检查（真异步，只获取 m3u8 内容）"""
    content = await AioFetch(url, ipVer, timeout=5)
    if not content:
        return False, None
    # 简单验证是否是有效的 m3u8
    if "#EXTINF" in content or "#EXT-X-STREAM-INF" in content:
        return True, content
    return False, None


async def FilterByResolution(urls, maxConcur=500):
    """两阶段筛选：先连通性检查，再检测分辨率（真异步）"""
    Log(f"--- 分辨率预检 ---")
    Log(f"第一阶段: 连通性检查 ({len(urls)} 个 URL)...")

    results = {}
    connectable = {}  # url -> {v4: content, v6: content}
    urlList = list(urls)

    # 第一阶段：真异步连通性检查
    sem = asyncio.Semaphore(maxConcur)

    async def checkOne(url, ipVer):
        async with sem:
            return await QuickConnectCheck(url, ipVer)

    # 构建所有任务
    tasks = []
    for url in urlList:
        tasks.append(checkOne(url, 4))
        tasks.append(checkOne(url, 6))

    Log(f"  并发检查 {len(urlList)} 个 URL (IPv4+IPv6)...")
    allResults = await asyncio.gather(*tasks)

    # 解析结果
    for i, url in enumerate(urlList):
        v4Ok, v4Content = allResults[i * 2]
        v6Ok, v6Content = allResults[i * 2 + 1]
        if v4Ok or v6Ok:
            connectable[url] = {"v4": v4Content, "v6": v6Content}
        results[url] = {"v4": False, "v6": False}

    Log(f"  可连接源: {len(connectable)} 个")

    if not connectable:
        Log(f"1080p 源: IPv4 0 个, IPv6 0 个, 共 0 个通过 (总 {len(urls)} 个)")
        return results

    # 第二阶段：检测分辨率（真异步，传入缓存内容）
    Log(f"第二阶段: 分辨率检测 ({len(connectable)} 个连通源)...")
    failReasons = {"no_segments": 0, "detect_failed": 0, "low_res": 0}
    resSem = asyncio.Semaphore(50)  # ffprobe 并发限制

    async def checkRes(url, ipVer, content):
        async with resSem:
            return await CheckResolution(url, ipVer, content, debug=False)

    tasks = []
    taskInfo = []
    for url in connectable:
        content = connectable[url]
        if content["v4"]:
            tasks.append(checkRes(url, 4, content["v4"]))
            taskInfo.append((url, 4))
        if content["v6"]:
            tasks.append(checkRes(url, 6, content["v6"]))
            taskInfo.append((url, 6))

    Log(f"  并发检测 {len(tasks)} 个...")
    batchResults = await asyncio.gather(*tasks)

    for (url, ipVer), result in zip(taskInfo, batchResults):
        is1080p, width, height, reason = result
        key = "v4" if ipVer == 4 else "v6"
        results[url][key] = is1080p
        if not is1080p:
            if reason == "ok":
                failReasons["low_res"] += 1
            elif reason in failReasons:
                failReasons[reason] += 1

    # 统计
    v4Count = sum(1 for r in results.values() if r["v4"])
    v6Count = sum(1 for r in results.values() if r["v6"])
    totalPass = sum(1 for r in results.values() if r["v4"] or r["v6"])

    Log(f"1080p 源: IPv4 {v4Count} 个, IPv6 {v6Count} 个, 共 {totalPass} 个通过 (总 {len(urls)} 个)")
    Log(f"失败原因: 无分片 {failReasons['no_segments']}, 检测失败 {failReasons['detect_failed']}, 低分辨率 {failReasons['low_res']}")

    return results


async def TestUrl(url, ipVer, timeout=30):
    """测试 URL，模拟真实播放：连续下载多个 ts 分片（真异步）"""
    # 获取 m3u8 内容
    content = await AioFetch(url, ipVer, timeout=10)
    if not content:
        return None

    # 解析分片
    segments = ParseM3u8Segments(content, url)
    if not segments:
        return None

    # 并发下载前 5 个分片
    testSegs = segments[:5]
    tasks = [AioDownload(seg, ipVer, timeout=10) for seg in testSegs]
    segResults = await asyncio.gather(*tasks)
    results = [r for r in segResults if r]

    if not results:
        return None

    # 汇总：取平均值，计算稳定性
    avgSpeed = sum(r["speed"] for r in results) / len(results)
    avgTtfb = sum(r["ttfb"] for r in results) / len(results)
    totalBytes = sum(r["bytes"] for r in results)
    totalTime = sum(r["total"] for r in results)

    # 计算速率标准差（稳定性指标）
    speeds = [r["speed"] for r in results]
    if len(speeds) > 1:
        avgSpd = sum(speeds) / len(speeds)
        variance = sum((s - avgSpd) ** 2 for s in speeds) / len(speeds)
        speedStd = variance ** 0.5
    else:
        speedStd = 0

    return {
        "bytes": totalBytes,
        "speed": avgSpeed,
        "ttfb": avgTtfb,
        "total": totalTime,
        "segments": len(results),
        "speedStd": speedStd
    }


async def TestUrlOnce(url, timeout=30, testV4=True, testV6=True):
    """单次双栈测速（真异步）"""
    v4Result, v6Result = None, None

    tasks = []
    if testV4:
        tasks.append(("v4", TestUrl(url, 4, timeout)))
    if testV6:
        tasks.append(("v6", TestUrl(url, 6, timeout)))

    if tasks:
        results = await asyncio.gather(*[t[1] for t in tasks])
        for i, (proto, _) in enumerate(tasks):
            if proto == "v4":
                v4Result = results[i]
            else:
                v6Result = results[i]

    return {"v4": v4Result, "v6": v6Result}


def CalcScore(results, rounds):
    """综合评分算法：分片稳定性(30%) + 轮次稳定性(20%) + 带宽(30%) + 连接速度(20%)"""
    if not results:
        return None

    # 成功率
    successRate = len(results) / rounds

    # 提取各项指标
    speeds = [r["speed"] for r in results]
    ttfbs = [r["ttfb"] for r in results]
    # 分片级稳定性（每次测试内部的波动）
    segStds = [r.get("speedStd", 0) for r in results]

    # 平均值
    avgSpeed = sum(speeds) / len(speeds)
    avgTtfb = sum(ttfbs) / len(ttfbs)
    avgSegStd = sum(segStds) / len(segStds)

    # 标准差计算
    def stdDev(values, avg):
        if len(values) < 2:
            return 0
        variance = sum((v - avg) ** 2 for v in values) / len(values)
        return variance ** 0.5

    # 轮次间速率标准差
    roundStd = stdDev(speeds, avgSpeed)

    # 各项评分（0-100分）
    # 分片稳定性：单次测试内分片速率波动越小越好
    segStabilityScore = 100 - min(100, (avgSegStd / (avgSpeed + 1)) * 100)

    # 轮次稳定性：不同时间点测速结果波动越小越好
    roundStabilityScore = 100 - min(100, (roundStd / (avgSpeed + 1)) * 100)

    # 带宽分：以 2Mbps (250KB/s) 为满分标准
    targetSpeed = 250000  # bytes/s
    bandwidthScore = min(100, (avgSpeed / targetSpeed) * 100)

    # 连接分：TTFB 越小越好，0.5秒以内满分
    connectScore = max(0, 100 - avgTtfb * 200)

    # 成功率惩罚：成功率低于100%时大幅降低总分
    ratePenalty = successRate ** 2

    # 综合评分 = 各项加权 × 成功率惩罚
    # 分片稳定性 30% + 轮次稳定性 20% + 带宽 30% + 连接 20%
    score = (segStabilityScore * 0.3 + roundStabilityScore * 0.2 +
             bandwidthScore * 0.3 + connectScore * 0.2) * ratePenalty

    return {
        "rate": successRate,
        "avgSpeed": avgSpeed,
        "avgTtfb": avgTtfb,
        "segStability": segStabilityScore,
        "roundStability": roundStabilityScore,
        "bandwidth": bandwidthScore,
        "connect": connectScore,
        "score": score
    }


async def SelectBestSources(chDict, rounds=5, interval=60, timeout=30, maxConcur=100, checkResolution=True):
    """为每个频道选择最优源（真异步，semaphore 控制并发）"""
    # 构建 URL -> [(chId, src), ...] 映射，实现全局去重
    urlMap = {}
    for chId, urlList in chDict.items():
        for url, src in urlList:
            if url not in urlMap:
                urlMap[url] = []
            urlMap[url].append((chId, src))

    if not urlMap:
        return {}, {}, {}

    allUrls = list(urlMap.keys())

    if checkResolution:
        # 分辨率预检：只保留 1080p
        resResults = await FilterByResolution(allUrls, maxConcur)
        # 按协议筛选出 1080p 源
        v4Urls = [url for url in allUrls if resResults[url]["v4"]]
        v6Urls = [url for url in allUrls if resResults[url]["v6"]]
        uniqueUrls = list(set(v4Urls + v6Urls))
        if not uniqueUrls:
            Log("没有找到 1080p 源")
            return {}, {}, {}
    else:
        # 跳过分辨率检测，直接用连通性检查
        Log(f"--- 连通性检查 ---")
        resResults = {}
        sem = asyncio.Semaphore(maxConcur)

        async def checkOne(url, ipVer):
            async with sem:
                ok, _ = await QuickConnectCheck(url, ipVer)
                return ok

        Log(f"检查 {len(allUrls)} 个 URL...")
        tasks = []
        for url in allUrls:
            tasks.append(checkOne(url, 4))
            tasks.append(checkOne(url, 6))
        results = await asyncio.gather(*tasks)

        for i, url in enumerate(allUrls):
            resResults[url] = {"v4": results[i * 2], "v6": results[i * 2 + 1]}

        v4Urls = [url for url in allUrls if resResults[url]["v4"]]
        v6Urls = [url for url in allUrls if resResults[url]["v6"]]
        uniqueUrls = list(set(v4Urls + v6Urls))
        Log(f"可连接源: IPv4 {len(v4Urls)} 个, IPv6 {len(v6Urls)} 个, 共 {len(uniqueUrls)} 个")

        if not uniqueUrls:
            Log("没有找到可连接的源")
            return {}, {}, {}

    total = len(uniqueUrls)
    Log(f"--- 双栈测速 ---")
    Log(f"测速 {total} 个源, {rounds} 轮, 间隔 {interval}秒, 并发 {maxConcur}")

    # 存储每个 URL 的测速结果
    urlResults = {url: {"v4": [], "v6": []} for url in uniqueUrls}
    sem = asyncio.Semaphore(maxConcur)

    async def testOne(url, testV4, testV6):
        async with sem:
            return await TestUrlOnce(url, timeout, testV4, testV6)

    # 全局轮次：每轮测完所有 URL 后再等待间隔
    for r in range(rounds):
        if r > 0:
            Log(f"  等待 {interval} 秒后开始第 {r + 1} 轮...")
            await asyncio.sleep(interval)

        Log(f"  第 {r + 1}/{rounds} 轮: 测速 {total} 个源...")

        # 用 semaphore 控制并发，所有任务一起启动
        tasks = []
        for url in uniqueUrls:
            tasks.append(testOne(url, resResults[url]["v4"], resResults[url]["v6"]))

        batchResults = await asyncio.gather(*tasks)

        # 记录结果
        for url, result in zip(uniqueUrls, batchResults):
            if result["v4"] is not None:
                urlResults[url]["v4"].append(result["v4"])
            if result["v6"] is not None:
                urlResults[url]["v6"].append(result["v6"])

    # 汇总结果
    bestV4, bestV6 = {}, {}
    srcStats = {}
    chScores = {ch: {"v4": (-1, None), "v6": (-1, None)} for ch in Channels}

    for url in uniqueUrls:
        v4 = CalcScore(urlResults[url]["v4"], rounds)
        v6 = CalcScore(urlResults[url]["v6"], rounds)

        # 将结果分配给所有相关频道
        for chId, src in urlMap[url]:
            # 统计上游源连通情况
            if src not in srcStats:
                srcStats[src] = {"total": 0, "connected": 0}
            srcStats[src]["total"] += 1
            if v4 or v6:
                srcStats[src]["connected"] += 1

            # 更新频道最优源
            if v4 and v4["score"] > chScores[chId]["v4"][0]:
                chScores[chId]["v4"] = (v4["score"], url)
            if v6 and v6["score"] > chScores[chId]["v6"][0]:
                chScores[chId]["v6"] = (v6["score"], url)

    # 提取最优结果
    for chId in Channels:
        _, v4Url = chScores[chId]["v4"]
        _, v6Url = chScores[chId]["v6"]
        if v4Url:
            bestV4[chId] = v4Url
        if v6Url:
            bestV6[chId] = v6Url

    Log(f"测速完成: 找到 {len(bestV4)} 个IPv4频道, {len(bestV6)} 个IPv6频道")

    return bestV4, bestV6, srcStats


def DisableDeadSources(srcStats, cfg):
    """禁用完全无法连接的上游源"""
    disabled = []
    for src in cfg.get("上游源", []):
        name = src.get("名称", src["地址"])
        stats = srcStats.get(name)
        if stats and stats["total"] > 0 and stats["connected"] == 0:
            if src.get("启用", True):
                src["启用"] = False
                disabled.append(name)
                Log(f"已禁用失效源: {name} (0/{stats['total']} 连通)")
    return disabled


def GenerateM3U(sources, filename):
    """生成 m3u 文件，内容相同或无源则跳过"""
    if not sources:
        Log(f"跳过 {filename}: 无可用源")
        return False

    lines = ['#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"']
    for chId in Channels:
        if chId in sources:
            info = Channels[chId]
            lines.append(f'#EXTINF:-1 tvg-name="{info["tvg_name"]}" tvg-logo="{info["logo"]}" group-title="央视频道",{info["name"]}')
            lines.append(sources[chId])

    content = "\n".join(lines) + "\n"
    path = RootDir / filename

    if path.exists() and path.read_text(encoding="utf-8") == content:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def HasChanges():
    """检查是否有文件变化（包括未跟踪的新文件）"""
    # 检查已跟踪文件的修改
    diff = subprocess.run(
        ["git", "diff", "--name-only", "ipv4.m3u", "ipv6.m3u", "config.json"],
        capture_output=True, text=True, cwd=RootDir
    )
    # 检查未跟踪的新文件
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "ipv4.m3u", "ipv6.m3u"],
        capture_output=True, text=True, cwd=RootDir
    )
    return bool(diff.stdout.strip() or untracked.stdout.strip())


def CommitAndPush():
    """提交并推送变更"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"update: {now}"
    subprocess.run(["git", "add", "ipv4.m3u", "ipv6.m3u", "config.json"], cwd=RootDir)
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

    # 并行抓取所有上游源
    Log("--- 抓取上游源 ---")
    allItems = await FetchAllSources(cfg.get("上游源", []), cfg, maxRetry, retryDelay)
    Log(f"共抓取 {len(allItems)} 个频道")

    # 筛选 CCTV 频道
    chDict = FilterChannels(allItems)
    totalUrls = sum(len(urls) for urls in chDict.values())
    uniqueUrls = len(set(url for urls in chDict.values() for url, _ in urls))
    Log(f"筛选出 CCTV 频道: {totalUrls} 个源 ({uniqueUrls} 个唯一)")

    # 读取测速配置
    rounds = settings.get("测速轮数", 5)
    interval = settings.get("测速间隔秒", 60)
    timeout = settings.get("测速超时秒", 30)
    maxConcur = settings.get("最大并发数", 100)
    autoDisable = settings.get("自动禁用失效源", True)
    checkRes = settings.get("分辨率检测", True)

    # 快速测试模式
    if os.environ.get("QUICK_TEST"):
        rounds, interval = 1, 1
        Log("\n[快速测试模式]")
    else:
        Log(f"\n[测速配置: {rounds}轮, 间隔{interval}秒, 超时{timeout}秒, 并发{maxConcur}]")

    bestV4, bestV6, srcStats = await SelectBestSources(chDict, rounds, interval, timeout, maxConcur, checkRes)

    # 禁用失效源
    disabled = []
    if autoDisable:
        disabled = DisableDeadSources(srcStats, cfg)

    # 生成 m3u 文件
    GenerateM3U(bestV4, "ipv4.m3u")
    GenerateM3U(bestV6, "ipv6.m3u")

    # 保存配置
    if disabled:
        SaveConfig(cfg)
        Log(f"配置已更新: 禁用了 {len(disabled)} 个失效源")

    Log(f"\n生成完成: ipv4.m3u ({len(bestV4)} 个频道), ipv6.m3u ({len(bestV6)} 个频道)")

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
