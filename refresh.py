#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_DIR = Path(__file__).resolve().parent
API_DIR = REPO_DIR / "api"
PORTFOLIO_FILE = API_DIR / "portfolio.json"
VIDEOS_FILE = API_DIR / "videos.json"
COVERS_FILE = API_DIR / "covers.json"

APP_ID = os.environ.get("LARK_APP_ID", "").strip()
APP_SECRET = os.environ.get("LARK_APP_SECRET", "").strip()
BASE_TOKEN = os.environ.get("LARK_BASE_TOKEN", "").strip()
TABLE_ID = os.environ.get("LARK_TABLE_ID", "").strip()

TITLE_FIELDS = ("标题", "标题名称", "作品名称", "名称")
CATEGORY_FIELDS = ("分类", "类别", "标签", "类型")
VIDEO_FIELDS = ("视频附件", "视频", "样片", "附件")
COVER_FIELDS = ("封面附件", "封面", "海报", "图片")

BATCH_SIZE = 5


def fail(message: str, code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(code)


def require_env() -> None:
    missing = [
        name
        for name, value in (
            ("LARK_APP_ID", APP_ID),
            ("LARK_APP_SECRET", APP_SECRET),
            ("LARK_BASE_TOKEN", BASE_TOKEN),
            ("LARK_TABLE_ID", TABLE_ID),
        )
        if not value
    ]
    if missing:
        fail("Missing required environment variables: " + ", ".join(missing))


def request_json(url: str, *, data: dict[str, Any] | None = None, token: str | None = None) -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    payload = None if data is None else json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")
        fail(f"HTTP {exc.code} calling {url}: {body}")
    except urllib.error.URLError as exc:
        fail(f"Request failed for {url}: {exc}")


def tenant_access_token() -> str:
    res = request_json(
        "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
        data={"app_id": APP_ID, "app_secret": APP_SECRET},
    )
    token = res.get("tenant_access_token")
    if res.get("code") != 0 or not token:
        fail(f"Failed to get tenant access token: {json.dumps(res, ensure_ascii=False)}")
    return str(token)


def get_records(token: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    page_token = ""
    while True:
        params = {"page_size": 500}
        if page_token:
            params["page_token"] = page_token
        url = (
            f"https://open.feishu.cn/open-apis/bitable/v1/apps/{BASE_TOKEN}/tables/{TABLE_ID}/records?"
            + urllib.parse.urlencode(params)
        )
        res = request_json(url, token=token)
        if res.get("code") != 0:
            fail(f"Failed to fetch records: {json.dumps(res, ensure_ascii=False)}")
        data = res.get("data", {})
        items.extend(data.get("items", []))
        if not data.get("has_more"):
            break
        page_token = data.get("page_token", "")
        if not page_token:
            break
    return items


def first_present(fields: dict[str, Any], names: tuple[str, ...]) -> Any:
    for name in names:
        if name in fields and fields[name] not in (None, "", []):
            return fields[name]
    return None


def attachment_token(value: Any) -> str:
    if isinstance(value, list) and value:
        first = value[0]
        if isinstance(first, dict):
            return str(first.get("file_token", ""))
    return ""


def text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, dict):
        for key in ("text", "name", "value"):
            if isinstance(value.get(key), str):
                return value[key].strip()
    if isinstance(value, list):
        return ", ".join(part for part in (text(item) for item in value) if part)
    return str(value).strip()


def resolve_urls(token: str, file_tokens: list[str]) -> dict[str, str]:
    unique = [t for t in dict.fromkeys(file_tokens) if t]
    if not unique:
        return {}
    extra = urllib.parse.quote(json.dumps({"bitablePerm": {"tableId": TABLE_ID}}, ensure_ascii=False))
    base = "https://open.feishu.cn/open-apis/drive/v1/medias/batch_get_tmp_download_url"
    out: dict[str, str] = {}
    for start in range(0, len(unique), BATCH_SIZE):
        batch = unique[start:start + BATCH_SIZE]
        query = [("extra", extra)] + [("file_tokens", t) for t in batch]
        url = base + "?" + "&".join(f"{k}={v}" for k, v in query)
        res = request_json(url, token=token)
        if res.get("code") != 0:
            fail(f"Failed to resolve URLs: {json.dumps(res, ensure_ascii=False)}")
        for item in res.get("data", {}).get("tmp_download_urls", []):
            ft = str(item.get("file_token", ""))
            tmp = str(item.get("tmp_download_url", ""))
            if ft and tmp:
                out[ft] = tmp
    return out


def build_payload(records: list[dict[str, Any]], urls: dict[str, str]) -> tuple[list[dict[str, Any]], dict[str, str], dict[str, str]]:
    portfolio: list[dict[str, Any]] = []
    videos: dict[str, str] = {}
    covers: dict[str, str] = {}
    for index, record in enumerate(records):
        fields = record.get("fields", {})
        title = text(first_present(fields, TITLE_FIELDS)) or f"作品 {index + 1}"
        category = text(first_present(fields, CATEGORY_FIELDS))
        video_token = attachment_token(first_present(fields, VIDEO_FIELDS))
        cover_token = attachment_token(first_present(fields, COVER_FIELDS))
        if not video_token:
            continue
        video_url = urls.get(video_token, "")
        cover_url = urls.get(cover_token, "") if cover_token else ""
        if not video_url:
            continue
        videos[video_token] = video_url
        if cover_token and cover_url:
            covers[cover_token] = cover_url
        portfolio.append(
            {
                "record_id": record.get("record_id", ""),
                "title": title,
                "category": category,
                "video_token": video_token,
                "cover_token": cover_token,
                "video_url": video_url,
                "cover_url": cover_url,
                "order": index,
            }
        )
    return portfolio, videos, covers


def write_files(portfolio: list[dict[str, Any]], videos: dict[str, str], covers: dict[str, str]) -> None:
    API_DIR.mkdir(parents=True, exist_ok=True)
    refreshed_at = datetime.now(timezone.utc).isoformat()
    portfolio_payload = {"_refreshed_at": refreshed_at, "_count": len(portfolio), "items": portfolio}
    videos_payload = {"_refreshed_at": refreshed_at, "_count": len(videos), **videos}
    covers_payload = {"_refreshed_at": refreshed_at, "_count": len(covers), **covers}
    PORTFOLIO_FILE.write_text(json.dumps(portfolio_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    VIDEOS_FILE.write_text(json.dumps(videos_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    COVERS_FILE.write_text(json.dumps(covers_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    require_env()
    token = tenant_access_token()
    records = get_records(token)
    attachment_tokens: list[str] = []
    for record in records:
        fields = record.get("fields", {})
        for candidates in (VIDEO_FIELDS, COVER_FIELDS):
            tk = attachment_token(first_present(fields, candidates))
            if tk:
                attachment_tokens.append(tk)
    urls = resolve_urls(token, attachment_tokens)
    portfolio, videos, covers = build_payload(records, urls)
    write_files(portfolio, videos, covers)
    print(f"Wrote {len(portfolio)} items to {PORTFOLIO_FILE}")


if __name__ == "__main__":
    main()
