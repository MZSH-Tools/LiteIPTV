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
                ["curl", "-s", "-L", "--max-time", "30", url],
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


async def FetchAllSources(sources, maxRetry, retryDelay):
    """并行抓取所有上游源，抓取失败的源自动禁用"""
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(None, FetchSource, src, maxRetry, retryDelay) for src in sources]
    results = await asyncio.gather(*tasks)

    allItems = []
    for src, (items, success) in zip(sources, results):
        allItems.extend(items)
        # 抓取失败则禁用
        if not success and src.get("启用", True):
            src["启用"] = False
            Log(f"已禁用抓取失败源: {src.get('名称', src['地址'])}")

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


async def TestUrlOnce(url, timeout=2):
    """单次双栈测速"""
    loop = asyncio.get_event_loop()
    v4Task = loop.run_in_executor(None, TestUrlCurl, url, 4, timeout)
    v6Task = loop.run_in_executor(None, TestUrlCurl, url, 6, timeout)
    v4Time, v6Time = await asyncio.gather(v4Task, v6Task)
    return {"v4": v4Time, "v6": v6Time}


def CalcScore(results, rounds):
    """计算评分"""
    if not results:
        return None
    rate = len(results) / rounds
    avgMs = sum(results) / len(results) * 1000
    score = rate * 1000 / (avgMs + 10)
    return {"rate": rate, "avgMs": avgMs, "score": score}


async def SelectBestSources(chDict, rounds=5, interval=60, timeout=2, maxConcur=100):
    """为每个频道选择最优源（全局轮次，每轮测完再等待间隔）"""
    # 构建 URL -> [(chId, src), ...] 映射，实现全局去重
    urlMap = {}
    for chId, urlList in chDict.items():
        for url, src in urlList:
            if url not in urlMap:
                urlMap[url] = []
            urlMap[url].append((chId, src))

    if not urlMap:
        return {}, {}, {}

    uniqueUrls = list(urlMap.keys())
    total = len(uniqueUrls)
    Log(f"全局并行测速: {total} 个唯一URL, {rounds} 轮, 间隔 {interval}秒, 超时 {timeout}秒, 并发 {maxConcur}")

    # 存储每个 URL 的测速结果
    urlResults = {url: {"v4": [], "v6": []} for url in uniqueUrls}

    # 全局轮次：每轮测完所有 URL 后再等待间隔
    for r in range(rounds):
        if r > 0:
            Log(f"  等待 {interval} 秒后开始第 {r + 1} 轮...")
            await asyncio.sleep(interval)

        Log(f"  第 {r + 1}/{rounds} 轮:")

        # 分批并发测速
        for i in range(0, total, maxConcur):
            batch = uniqueUrls[i:i + maxConcur]
            end = min(i + maxConcur, total)
            Log(f"    测速中: {i + 1}-{end} / {total}")
            tasks = [TestUrlOnce(url, timeout) for url in batch]
            batchResults = await asyncio.gather(*tasks)

            # 记录结果
            for url, result in zip(batch, batchResults):
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


async def Main():
    """主函数"""
    # 初始化日志目录并清空日志
    LogDir.mkdir(parents=True, exist_ok=True)
    LogFile.write_text("")

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
    allItems = await FetchAllSources(cfg.get("上游源", []), maxRetry, retryDelay)
    Log(f"共抓取 {len(allItems)} 个频道")

    # 筛选 CCTV 频道
    chDict = FilterChannels(allItems)
    totalUrls = sum(len(urls) for urls in chDict.values())
    uniqueUrls = len(set(url for urls in chDict.values() for url, _ in urls))
    Log(f"筛选出 CCTV 频道: {totalUrls} 个源 ({uniqueUrls} 个唯一)")

    # 读取测速配置
    rounds = settings.get("测速轮数", 5)
    interval = settings.get("测速间隔秒", 60)
    timeout = settings.get("测速超时秒", 2)
    maxConcur = settings.get("最大并发数", 100)
    autoDisable = settings.get("自动禁用失效源", True)

    # 快速测试模式
    if os.environ.get("QUICK_TEST"):
        rounds, interval = 1, 1
        Log("\n[快速测试模式]")
    else:
        Log(f"\n[测速配置: {rounds}轮, 间隔{interval}秒, 超时{timeout}秒, 并发{maxConcur}]")

    Log("\n--- 双栈测速 ---")
    bestV4, bestV6, srcStats = await SelectBestSources(chDict, rounds, interval, timeout, maxConcur)

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


if __name__ == "__main__":
    asyncio.run(Main())
