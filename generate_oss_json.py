#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote
import requests

REPO_DIR = Path(__file__).resolve().parent
API_DIR = REPO_DIR / "api"
PORTFOLIO_FILE = API_DIR / "portfolio.json"

ASSET_BASE = os.getenv("ASSET_BASE", "https://JTaoYoung.github.io")

BILIBILI_LINKS = {
    "故宫活宝团圆夜AIGC广告": "https://www.bilibili.com/video/BV1XEoeB4EsD/",
    "蒙牛软牛奶广告": "https://www.bilibili.com/video/BV1GEoeBtE7p/",
    "蒙牛软牛奶AIGC广告": "https://www.bilibili.com/video/BV1giohBEEtR/",
    "蒙牛优骨牛奶AIGC广告": "https://www.bilibili.com/video/BV1hiohBEE28/",
    "仁和牌清火胶囊AIGC广告": "https://www.bilibili.com/video/BV13iohBEEhk/",
    "阿玛尼美妆篇": "https://www.bilibili.com/video/BV1QEoeB4EZM/",
    "古风武侠篇": "https://www.bilibili.com/video/BV1QEoeB4EnR/",
    "科幻动作篇": "https://www.bilibili.com/video/BV1giohBEERB/",
    "香奈儿时尚篇": "https://www.bilibili.com/video/BV1XEoeB4Es6/",
    "战术特工篇": "https://www.bilibili.com/video/BV13iohBEEPL/",
}


@dataclass(frozen=True)
class WorkItem:
    title: str
    category: str
    year: str
    duration: str
    desc: str
    color: str
    object_name: str


WORKS: list[WorkItem] = [
    WorkItem("故宫活宝团圆夜AIGC广告", "商业广告 AIGC", "2026", "—", "宫灯、暖金与东方叙事交织，呈现节庆质感的品牌影像。", "Commercial campaign", "videos/imperial-reunion-night.m4v"),
    WorkItem("蒙牛软牛奶广告", "商业广告 AIGC", "2026", "—", "明亮纯净的乳白基调，强调产品光泽与干净的商业节奏。", "Commercial campaign", "videos/mengniu-softmilk-ad.mp4"),
    WorkItem("蒙牛软牛奶AIGC广告", "商业广告 AIGC", "2026", "—", "柔和高光与轻盈氛围感，突出奶感、口感和流动光影。", "Commercial campaign", "videos/mengniu-softmilk-aigc-ad.mp4"),
    WorkItem("蒙牛优骨牛奶AIGC广告", "商业广告 AIGC", "2026", "—", "健康、活力与通透光效结合，打造高级品牌视觉。", "Commercial campaign", "videos/mengniu-yg-milk-aigc-ad.mp4"),
    WorkItem("仁和牌清火胶囊AIGC广告", "商业广告 AIGC", "2026", "—", "以清爽光线和强对比构图，营造药品广告的专业可信感。", "Commercial campaign", "videos/renhe-clearing-capsule-aigc-ad.mp4"),
    WorkItem("阿玛尼美妆篇", "个人创作 AIGC", "2026", "—", "克制、精致、带有时装大片式的明暗交界与肤感细节。", "Personal creation", "videos/armani-beauty.mp4"),
    WorkItem("古风武侠篇", "个人创作 AIGC", "2026", "—", "水墨、剑气、日照与雾气交织成具有叙事感的画面。", "Personal creation", "videos/ancient-martial-arts.mp4"),
    WorkItem("科幻动作篇", "个人创作 AIGC", "2026", "—", "蓝白色能量感和高速镜头语言，塑造未来动作氛围。", "Personal creation", "videos/sci-fi-action.mp4"),
    WorkItem("香奈儿时尚篇", "个人创作 AIGC", "2026", "—", "优雅、简洁、光影分层清晰，具有时尚广告片的精致质感。", "Personal creation", "videos/chanel-fashion.mp4"),
    WorkItem("战术特工篇", "个人创作 AIGC", "2026", "—", "低饱和冷感与战术化构图，让动作张力更具电影性。", "Personal creation", "videos/tactical-agent.mp4"),
]


def make_public_url(title: str, object_name: str) -> str:
    if title in BILIBILI_LINKS:
        return BILIBILI_LINKS[title]
    if ASSET_BASE:
        return f"{ASSET_BASE.rstrip('/')}/{quote(object_name)}"
    return f"/videos/{quote(Path(object_name).name)}"


def extract_bilibili_bvid(url: str) -> str:
    marker = "/video/"
    if marker in url:
        tail = url.split(marker, 1)[1]
        return tail.split("?")[0].strip("/")
    return ""


def fetch_bilibili_cover(url: str) -> str:
    bvid = extract_bilibili_bvid(url)
    if not bvid:
        return ""
    api_url = f"https://api.bilibili.com/x/web-interface/view?bvid={quote(bvid)}"
    try:
        resp = requests.get(api_url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return data.get("data", {}).get("pic", "") or ""
    except Exception:
        return ""


def main() -> None:
    items = []
    for index, work in enumerate(WORKS, start=1):
        public_url = make_public_url(work.title, work.object_name)
        poster_url = fetch_bilibili_cover(public_url) if work.title in BILIBILI_LINKS else ""
        items.append(
            {
                "title": work.title,
                "category": work.category,
                "year": work.year,
                "duration": work.duration,
                "desc": work.desc,
                "color": work.color,
                "object_name": work.object_name,
                "video": work.object_name,
                "video_url": public_url,
                "poster_url": poster_url,
                "order": index,
            }
        )

    API_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "_refreshed_at": datetime.now(timezone.utc).isoformat(),
        "_count": len(items),
        "items": items,
    }
    PORTFOLIO_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(items)} items to {PORTFOLIO_FILE}")


if __name__ == "__main__":
    main()
