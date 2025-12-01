#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LiteIPTV - 精简稳定的 CCTV 直播源
每小时运行，5轮测速取最优，仅在源变化时更新
"""

import asyncio
import aiohttp
import json
import re
import time
import subprocess
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

# 项目根目录
ROOT_DIR = Path(__file__).parent

# CCTV 频道配置
CHANNELS = {
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
CHANNEL_PATTERNS = [
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


def load_config():
    """加载配置文件"""
    config_path = ROOT_DIR / "config.json"
    if not config_path.exists():
        print("Error: config.json not found")
        return None
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch_source_sync(source):
    """抓取单个上游源（使用 curl）"""
    if not source.get("enabled", True):
        return []

    url = source["url"]
    name = source.get("name", url)
    print(f"Fetching: {name}")

    try:
        result = subprocess.run(
            ["curl", "-s", "-L", "--max-time", "60", url],
            capture_output=True, text=True
        )
        if result.returncode == 0 and result.stdout:
            channels = parse_m3u(result.stdout)
            print(f"  Parsed: {len(channels)} channels")
            return channels
        else:
            print(f"  Error: curl failed with code {result.returncode}")
    except Exception as e:
        print(f"Error fetching {name}: {type(e).__name__}: {e}")
    return []


def parse_m3u(content):
    """解析 m3u 文件，提取频道信息"""
    channels = []
    lines = content.strip().split("\n")

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if line.startswith("#EXTINF:"):
            # 提取频道名
            match = re.search(r',(.+)$', line)
            if match and i + 1 < len(lines):
                channel_name = match.group(1).strip()
                url = lines[i + 1].strip()
                # 清理 URL：移除 # 后面的内容
                if "#" in url:
                    url = url.split("#")[0]
                if url and not url.startswith("#"):
                    channels.append({"name": channel_name, "url": url})
                i += 1
        i += 1

    return channels


def match_channel(name):
    """匹配频道名到标准频道 ID"""
    name_upper = name.upper()
    # 优先匹配 CCTV-5+
    for pattern, channel_id in CHANNEL_PATTERNS:
        if re.search(pattern, name_upper, re.IGNORECASE):
            return channel_id
    return None


def is_ipv6(url):
    """判断 URL 是否为 IPv6"""
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        # IPv6 地址格式：[xxxx:xxxx:...] 或纯 IPv6
        if host.startswith("[") or ":" in host:
            return True
        return False
    except:
        return False


def filter_channels(all_channels):
    """筛选 CCTV 频道，分离 IPv4/IPv6"""
    ipv4_channels = {ch: [] for ch in CHANNELS}
    ipv6_channels = {ch: [] for ch in CHANNELS}

    for item in all_channels:
        channel_id = match_channel(item["name"])
        if channel_id:
            url = item["url"]
            if is_ipv6(url):
                ipv6_channels[channel_id].append(url)
            else:
                ipv4_channels[channel_id].append(url)

    return ipv4_channels, ipv6_channels


async def test_url(session, url, timeout=5):
    """测试单个 URL 的响应时间"""
    try:
        start = time.time()
        # 使用 GET 请求，只读取少量数据
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout), allow_redirects=True) as resp:
            if resp.status == 200:
                # 尝试读取一小部分数据确认可用
                await resp.content.read(1024)
                return time.time() - start
    except:
        pass
    return None


async def test_url_rounds(session, url, rounds=5, interval=60):
    """多轮测速，返回综合得分"""
    results = []

    for i in range(rounds):
        if i > 0:
            await asyncio.sleep(interval)

        response_time = await test_url(session, url)
        if response_time is not None:
            results.append(response_time)

    if not results:
        return None

    # 计算综合得分：成功率 × 平均速度
    success_rate = len(results) / rounds
    avg_time = sum(results) / len(results)
    # 得分越高越好：成功率高、响应时间短
    score = success_rate / (avg_time + 0.1)

    return {
        "success_rate": success_rate,
        "avg_time": avg_time,
        "score": score
    }


async def select_best_sources(channels_dict, rounds=5, interval=60):
    """为每个频道选择最优源"""
    best_sources = {}

    async with aiohttp.ClientSession() as session:
        for channel_id, urls in channels_dict.items():
            if not urls:
                continue

            print(f"Testing {channel_id}: {len(urls)} sources")

            # 去重
            unique_urls = list(set(urls))

            # 并发测速所有源
            tasks = [test_url_rounds(session, url, rounds, interval) for url in unique_urls]
            results = await asyncio.gather(*tasks)

            # 找出最优源
            best_score = -1
            best_url = None

            for url, result in zip(unique_urls, results):
                if result and result["score"] > best_score:
                    best_score = result["score"]
                    best_url = url

            if best_url:
                best_sources[channel_id] = best_url
                print(f"  Best: {best_url[:50]}... (score: {best_score:.2f})")

    return best_sources


def generate_m3u(sources, filename):
    """生成 m3u 文件"""
    lines = ['#EXTM3U x-tvg-url="https://epg.112114.xyz/pp.xml"']

    # 按频道顺序输出
    for channel_id in CHANNELS:
        if channel_id in sources:
            info = CHANNELS[channel_id]
            extinf = f'#EXTINF:-1 tvg-name="{info["tvg_name"]}" tvg-logo="{info["logo"]}" group-title="央视频道",{info["name"]}'
            lines.append(extinf)
            lines.append(sources[channel_id])

    content = "\n".join(lines) + "\n"

    filepath = ROOT_DIR / filename
    filepath.write_text(content, encoding="utf-8")

    return content


def has_changes():
    """检查是否有文件变化"""
    result = subprocess.run(
        ["git", "diff", "--name-only", "ipv4.m3u", "ipv6.m3u"],
        capture_output=True, text=True, cwd=ROOT_DIR
    )
    return bool(result.stdout.strip())


def commit_and_push():
    """提交并推送变更"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    commit_msg = f"update: {now}"

    subprocess.run(["git", "add", "ipv4.m3u", "ipv6.m3u"], cwd=ROOT_DIR)
    subprocess.run(["git", "commit", "-m", commit_msg], cwd=ROOT_DIR)
    subprocess.run(["git", "push"], cwd=ROOT_DIR)

    print(f"Pushed: {commit_msg}")


async def main():
    """主函数"""
    print(f"=== LiteIPTV Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")

    # 加载配置
    config = load_config()
    if not config:
        return

    # 抓取所有上游源
    all_channels = []
    for source in config.get("sources", []):
        channels = fetch_source_sync(source)
        all_channels.extend(channels)

    print(f"Total channels fetched: {len(all_channels)}")

    # 筛选 CCTV 频道
    ipv4_channels, ipv6_channels = filter_channels(all_channels)

    ipv4_count = sum(len(urls) for urls in ipv4_channels.values())
    ipv6_count = sum(len(urls) for urls in ipv6_channels.values())
    print(f"CCTV channels: IPv4={ipv4_count}, IPv6={ipv6_count}")

    # 测速选优（5轮，每轮间隔1分钟）
    # 可通过环境变量 QUICK_TEST=1 进行快速测试
    import os
    if os.environ.get("QUICK_TEST"):
        rounds, interval = 1, 1
        print("\n[Quick test mode]")
    else:
        rounds, interval = 5, 60

    print("\n--- Testing IPv4 sources ---")
    best_ipv4 = await select_best_sources(ipv4_channels, rounds=rounds, interval=interval)

    print("\n--- Testing IPv6 sources ---")
    best_ipv6 = await select_best_sources(ipv6_channels, rounds=rounds, interval=interval)

    # 生成 m3u 文件
    generate_m3u(best_ipv4, "ipv4.m3u")
    generate_m3u(best_ipv6, "ipv6.m3u")

    print(f"\nGenerated: ipv4.m3u ({len(best_ipv4)} channels), ipv6.m3u ({len(best_ipv6)} channels)")

    # 检查变化并提交
    if has_changes():
        commit_and_push()
    else:
        print("No changes detected, skip push")

    print(f"=== LiteIPTV End: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")


if __name__ == "__main__":
    asyncio.run(main())
