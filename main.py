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

# 项目根目录
RootDir = Path(__file__).parent

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
        print("Error: config.json not found")
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


def FetchSource(src):
    """抓取单个上游源，返回带 source 标记的频道列表"""
    if not src.get("启用", True):
        return []

    url = src["地址"]
    name = src.get("名称", url)

    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", "30", url],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout:
            items = ParseM3U(result.stdout)
            for item in items:
                item["source"] = name
            print(f"Fetched {name}: {len(items)} channels")
            return items
        print(f"Fetch failed {name}: curl code {result.returncode}")
    except Exception as e:
        print(f"Fetch error {name}: {type(e).__name__}")
    return []


async def FetchAllSources(sources):
    """并行抓取所有上游源"""
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, FetchSource, src) for src in sources]
    results = await asyncio.gather(*tasks)
    allItems = []
    for items in results:
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


def FilterChannels(allItems):
    """筛选 CCTV 频道，返回 {chId: [(url, source), ...]}"""
    result = {ch: [] for ch in Channels}
    for item in allItems:
        chId = MatchChannel(item["name"])
        if chId:
            result[chId].append((item["url"], item.get("source", "unknown")))
    return result


def TestUrlCurl(url, ipVer, timeout=5):
    """使用 curl 测试 URL（指定 IPv4 或 IPv6）"""
    flag = "-4" if ipVer == 4 else "-6"
    try:
        start = time.time()
        result = subprocess.run(
            ["curl", flag, "-s", "-L", "-o", "/dev/null", "-w", "%{http_code}",
             "--max-time", str(timeout), url],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout.strip() == "200":
            return time.time() - start
    except:
        pass
    return None


async def TestUrlDualStack(url, rounds=5, interval=60):
    """双栈测速，分别测试 IPv4 和 IPv6"""
    loop = asyncio.get_event_loop()
    v4Results, v6Results = [], []

    for i in range(rounds):
        if i > 0:
            await asyncio.sleep(interval)
        v4Task = loop.run_in_executor(None, TestUrlCurl, url, 4, 5)
        v6Task = loop.run_in_executor(None, TestUrlCurl, url, 6, 5)
        v4Time, v6Time = await asyncio.gather(v4Task, v6Task)
        if v4Time is not None:
            v4Results.append(v4Time)
        if v6Time is not None:
            v6Results.append(v6Time)

    def CalcScore(results):
        if not results:
            return None
        rate = len(results) / rounds
        avg = sum(results) / len(results)
        return {"rate": rate, "avg": avg, "score": rate / (avg + 0.1)}

    return {"v4": CalcScore(v4Results), "v6": CalcScore(v6Results)}


async def SelectBestSources(chDict, rounds=5, interval=60, maxConcur=50):
    """为每个频道选择最优源（全局并行双栈测速，限制并发数）"""
    # 收集所有待测 URL
    allTests = []
    for chId, urlList in chDict.items():
        seen = set()
        for url, src in urlList:
            if url not in seen:
                seen.add(url)
                allTests.append((chId, url, src))

    if not allTests:
        return {}, {}, {}

    print(f"Global parallel testing: {len(allTests)} URLs, {rounds} rounds, max concurrency: {maxConcur}")

    # 使用信号量限制并发数
    sem = asyncio.Semaphore(maxConcur)

    async def TestWithLimit(url, r, i):
        async with sem:
            return await TestUrlDualStack(url, r, i)

    tasks = [TestWithLimit(url, rounds, interval) for _, url, _ in allTests]
    results = await asyncio.gather(*tasks)

    # 汇总结果
    bestV4, bestV6 = {}, {}
    srcStats = {}
    chScores = {ch: {"v4": (-1, None), "v6": (-1, None)} for ch in Channels}

    for (chId, url, src), result in zip(allTests, results):
        if src not in srcStats:
            srcStats[src] = {"total": 0, "connected": 0}
        srcStats[src]["total"] += 1

        v4 = result.get("v4")
        v6 = result.get("v6")

        if v4 or v6:
            srcStats[src]["connected"] += 1

        if v4 and v4["score"] > chScores[chId]["v4"][0]:
            chScores[chId]["v4"] = (v4["score"], url)
        if v6 and v6["score"] > chScores[chId]["v6"][0]:
            chScores[chId]["v6"] = (v6["score"], url)

    # 提取最优结果
    for chId in Channels:
        v4Score, v4Url = chScores[chId]["v4"]
        v6Score, v6Url = chScores[chId]["v6"]
        if v4Url:
            bestV4[chId] = v4Url
        if v6Url:
            bestV6[chId] = v6Url

    print(f"Testing complete: {len(bestV4)} IPv4, {len(bestV6)} IPv6 channels found")

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
                print(f"Disabled source: {name} (0/{stats['total']} connected)")
    return disabled


def GenerateM3U(sources, filename):
    """生成 m3u 文件，内容相同则跳过"""
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
    print(f"Pushed: {msg}")


async def Main():
    """主函数"""
    print(f"=== LiteIPTV Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    cfg = LoadConfig()
    if not cfg:
        return

    # 并行抓取所有上游源
    print("--- Fetching sources ---")
    allItems = await FetchAllSources(cfg.get("上游源", []))
    print(f"Total channels fetched: {len(allItems)}")

    # 筛选 CCTV 频道
    chDict = FilterChannels(allItems)
    totalUrls = sum(len(urls) for urls in chDict.values())
    print(f"CCTV channels: {totalUrls} sources")

    # 读取测速配置
    settings = cfg.get("设置", {})
    rounds = settings.get("测速轮数", 5)
    interval = settings.get("测速间隔秒", 60)
    autoDisable = settings.get("自动禁用失效源", True)

    # 快速测试模式
    if os.environ.get("QUICK_TEST"):
        rounds, interval = 1, 1
        print("\n[Quick test mode]")
    else:
        print(f"\n[Test config: {rounds} rounds, {interval}s interval]")

    print("\n--- Dual-stack testing ---")
    bestV4, bestV6, srcStats = await SelectBestSources(chDict, rounds, interval)

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
        print(f"Config updated: {len(disabled)} sources disabled")

    print(f"\nGenerated: ipv4.m3u ({len(bestV4)} channels), ipv6.m3u ({len(bestV6)} channels)")

    # 检查变化并提交
    if HasChanges():
        CommitAndPush()
    else:
        print("No changes detected, skip push")

    print(f"=== LiteIPTV End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    asyncio.run(Main())
