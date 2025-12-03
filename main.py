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
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, urljoin

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


async def FetchAllSources(sources, cfg, maxRetry, retryDelay, autoDisable=True):
    """并行抓取所有上游源，抓取失败的源自动禁用"""
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, FetchSource, src, maxRetry, retryDelay) for src in sources]
    results = await asyncio.gather(*tasks)

    allItems = []
    disabled = []
    for src, (items, success) in zip(sources, results):
        allItems.extend(items)
        # 抓取失败则禁用
        if autoDisable and not success and src.get("启用", True):
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


def CalcScore(results, rounds):
    """综合评分算法"""
    if not results:
        return None

    successRate = len(results) / rounds
    speeds = [r["speed"] for r in results]
    ttfbs = [r["ttfb"] for r in results]
    segStds = [r.get("speedStd", 0) for r in results]

    avgSpeed = sum(speeds) / len(speeds)
    avgTtfb = sum(ttfbs) / len(ttfbs)
    avgSegStd = sum(segStds) / len(segStds)

    # 轮次间速率标准差
    if len(speeds) > 1:
        variance = sum((s - avgSpeed) ** 2 for s in speeds) / len(speeds)
        roundStd = variance ** 0.5
    else:
        roundStd = 0

    # 分片稳定性评分
    segStabilityScore = 100 - min(100, (avgSegStd / (avgSpeed + 1)) * 100)

    # 轮次稳定性评分
    roundStabilityScore = 100 - min(100, (roundStd / (avgSpeed + 1)) * 100)

    # 带宽评分（2Mbps = 250KB/s 满分）
    bandwidthScore = min(100, (avgSpeed / 250000) * 100)

    # 连接评分（0.5秒内满分）
    connectScore = max(0, 100 - avgTtfb * 200)

    # 综合评分 = 各项加权 × 成功率惩罚
    score = (segStabilityScore * 0.3 + roundStabilityScore * 0.2 +
             bandwidthScore * 0.3 + connectScore * 0.2) * (successRate ** 2)

    return {
        "score": score,
        "avgSpeed": avgSpeed,
        "avgTtfb": avgTtfb,
        "successRate": successRate
    }


async def SelectBestSources(chDict, rounds=3, interval=60, timeout=30, maxConcur=100):
    """为每个频道选择最优源（参考 iptv-api：缓存 + 多轮测速）"""
    # 构建 URL -> [(chId, src), ...] 映射，实现全局去重
    urlMap = {}
    for chId, urlList in chDict.items():
        for url, src in urlList:
            if url not in urlMap:
                urlMap[url] = []
            urlMap[url].append((chId, src))

    if not urlMap:
        return {}, {}

    allUrls = list(urlMap.keys())
    Log(f"待测试: {len(allUrls)} 个唯一 URL")

    # 第一步：快速连通性检查
    Log(f"--- 连通性检查 ---")
    sem = asyncio.Semaphore(maxConcur)

    async def quickCheck(url):
        async with sem:
            content = await AioFetch(url, timeout=5)
            return content is not None and ("#EXTINF" in content or "#EXT-X-STREAM-INF" in content)

    tasks = [quickCheck(url) for url in allUrls]
    connResults = await asyncio.gather(*tasks)

    validUrls = [url for url, ok in zip(allUrls, connResults) if ok]
    Log(f"可连接: {len(validUrls)}/{len(allUrls)}")

    if not validUrls:
        Log("没有可连接的源")
        return {}, {}

    # 第二步：多轮测速
    Log(f"--- 测速 ({rounds}轮, 间隔{interval}秒) ---")
    urlResults = {url: [] for url in validUrls}

    for r in range(rounds):
        if r > 0:
            Log(f"等待 {interval} 秒...")
            await asyncio.sleep(interval)

        Log(f"第 {r + 1}/{rounds} 轮: 测速 {len(validUrls)} 个源...")

        async def testOne(url):
            async with sem:
                return await TestUrl(url, timeout)

        tasks = [testOne(url) for url in validUrls]
        results = await asyncio.gather(*tasks)

        for url, result in zip(validUrls, results):
            if result:
                urlResults[url].append(result)

    # 第三步：计算评分并选择最优
    best = {}
    srcStats = {}
    chScores = {ch: (-1, None) for ch in Channels}

    for url in validUrls:
        scoreData = CalcScore(urlResults[url], rounds)
        if not scoreData:
            continue

        score = scoreData["score"]

        # 将结果分配给所有相关频道
        for chId, src in urlMap[url]:
            # 统计上游源连通情况
            if src not in srcStats:
                srcStats[src] = {"total": 0, "connected": 0}
            srcStats[src]["total"] += 1
            srcStats[src]["connected"] += 1

            # 更新频道最优源
            if score > chScores[chId][0]:
                chScores[chId] = (score, url)

    # 提取最优结果
    for chId in Channels:
        _, bestUrl = chScores[chId]
        if bestUrl:
            best[chId] = bestUrl

    Log(f"选出最优源: {len(best)}/{len(Channels)} 个频道")
    return best, srcStats


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
    """检查是否有文件变化"""
    diff = subprocess.run(
        ["git", "diff", "--name-only", "iptv.m3u", "config.json"],
        capture_output=True, text=True, cwd=RootDir
    )
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "iptv.m3u"],
        capture_output=True, text=True, cwd=RootDir
    )
    return bool(diff.stdout.strip() or untracked.stdout.strip())


def CommitAndPush():
    """提交并推送变更"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    msg = f"update: {now}"
    subprocess.run(["git", "add", "iptv.m3u", "config.json"], cwd=RootDir)
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
    rounds = settings.get("测速轮数", 3)
    interval = settings.get("测速间隔秒", 300)
    timeout = settings.get("测速超时秒", 30)
    maxConcur = settings.get("最大并发数", 500)
    autoDisable = settings.get("自动禁用失效源", True)

    # 快速测试模式
    quickTest = os.environ.get("QUICK_TEST")
    if quickTest:
        rounds, interval = 1, 1
        autoDisable = False
        Log("[快速测试模式]\n")

    # 并行抓取所有上游源
    Log("--- 抓取上游源 ---")
    allItems = await FetchAllSources(cfg.get("上游源", []), cfg, maxRetry, retryDelay, autoDisable)
    Log(f"共抓取 {len(allItems)} 个频道")

    # 筛选 CCTV 频道（排除黑名单和 IPv6）
    blacklist = cfg.get("黑名单", [])
    chDict = FilterChannels(allItems, blacklist)
    totalUrls = sum(len(urls) for urls in chDict.values())
    uniqueUrls = len(set(url for urls in chDict.values() for url, _ in urls))
    Log(f"筛选出 CCTV 频道: {totalUrls} 个源 ({uniqueUrls} 个唯一)")

    if not quickTest:
        Log(f"\n[测速配置: {rounds}轮, 间隔{interval}秒, 超时{timeout}秒, 并发{maxConcur}]")

    best, srcStats = await SelectBestSources(chDict, rounds, interval, timeout, maxConcur)

    # 禁用失效源
    disabled = []
    if autoDisable:
        disabled = DisableDeadSources(srcStats, cfg)

    # 生成 m3u 文件
    GenerateM3U(best, "iptv.m3u")

    # 保存配置
    if disabled:
        SaveConfig(cfg)
        Log(f"配置已更新: 禁用了 {len(disabled)} 个失效源")

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
