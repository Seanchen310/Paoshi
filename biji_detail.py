"""
跑事｜運動筆記賽事詳情頁

列表頁沒有報名費、關門時間、主辦單位；這些在每場的詳情頁
（https://running.biji.co/index.php?q=competition&act=info&cid=<cid>）的「項目」區塊，格式固定：
  <li class="groups"><h3 class="groups-title">全程馬拉松組 ( 42.195K )</h3>
    起跑 05:00 ／ 費用 1500元 ／ 限時 6小時 ／ 限額 4700人 ／ 參賽贈品 …

一場一個請求，所以要有禮貌：
  - 每次排程最多抓 MAX_PER_RUN 頁，每頁間隔 DELAY 秒
  - 抓到的存在 data/biji_details.json（進 git），REFRESH_DAYS 天內不重抓
  - 可報名／即將開報、比賽日較近的優先

合併規則：跑者廣場有的報名費、名額照用；運動筆記只補空白。關門時間（限時）是新資訊。
"""

import datetime as dt
import html
import json
import os
import re
import sys
import time

import scraper as base

DETAIL_URL = "https://running.biji.co/index.php?q=competition&act=info&cid={cid}"
MAX_PER_RUN = 20
DELAY = 3
REFRESH_DAYS = 14
TRACKER_HOSTS = ("doubleclick.net", "googleadservices", "facebook.com/tr", "utm_")


def _text(s):
    return base.squash(html.unescape(re.sub(r"<[^>]+>", " ", s or "")))


def parse_number(s):
    """'1,500元' → 1500；'免費' → 0；沒有數字 → None。"""
    if not s:
        return None
    if "免費" in s:
        return 0
    m = re.search(r"\d[\d,]*", s)
    return int(m.group(0).replace(",", "")) if m else None


def parse_minutes(s):
    """'6小時' → 360、'3.5小時' → 210、'120分鐘' → 120、'5H30M' → 330。看不懂 → None。"""
    if not s:
        return None
    t = s.replace(" ", "")
    h = re.search(r"([\d.]+)\s*(小時|hr|h|H)", t)
    m = re.search(r"([\d.]+)\s*(分鐘|分|min|m|M)(?![a-z])", t)
    if not h and not m:
        return None
    total = (float(h.group(1)) * 60 if h else 0) + (float(m.group(1)) if m else 0)
    return int(round(total)) or None


def parse_detail(page):
    """回傳 {"organizer", "signup_url", "brochure_url", "groups": [...]}。"""
    out = {"organizer": None, "signup_url": None, "brochure_url": None, "groups": []}
    m = re.search(r'data-title">\s*主辦單位\s*</div>\s*<div[^>]*>(.*?)</div>', page, re.S)
    if m:
        out["organizer"] = _text(m.group(1)) or None

    i = page.find("相關連結")
    if i >= 0:
        for href, label in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page[i:i + 3000], re.S):
            href = html.unescape(href)
            if not href.startswith("http") or any(t in href for t in TRACKER_HOSTS):
                continue
            label = _text(label)
            if "報名" in label and not out["signup_url"]:
                out["signup_url"] = href
            elif "簡章" in label and not out["brochure_url"]:
                out["brochure_url"] = href

    i = page.find('id="comp_groups"')
    if i >= 0:
        seg = page[i:]
        seg = seg[:seg.find("</section>")]
        for block in re.findall(r'<li class="groups">(.*?)</ul>\s*</div>\s*</li>', seg, re.S):
            t = re.search(r"groups-title[^>]*>(.*?)</h3>", block, re.S)
            title = _text(t.group(1)) if t else ""
            pm = re.search(r"\(\s*([^()]+?)\s*\)\s*$", title)
            label = pm.group(1) if pm else title
            items = {_text(a): _text(b) for a, b in
                     re.findall(r'data-title">(.*?)</div>\s*<div class="data-content">(.*?)</div>', block, re.S)}
            start = re.match(r"\d{1,2}:\d{2}", items.get("起跑", ""))
            limit = items.get("限時") or None
            out["groups"].append({
                "name": re.sub(r"\s*\([^()]*\)\s*$", "", title) or label,
                "label": label,
                "km": base.parse_km(re.sub(r"(?<=\d)k\b", "K", label)),
                "start": start.group(0) if start else None,
                "fee": parse_number(items.get("費用")),
                "time_limit": parse_minutes(limit),
                "time_limit_text": limit,
                "quota": parse_number(items.get("限額")),
                "gifts": items.get("參賽贈品") or None,
            })
    return out

# ---------------------------------------------------------------
# 快取：要抓哪幾場、抓下來存好
# ---------------------------------------------------------------

def biji_cid(r):
    k = r.get("key") or ""
    return k[5:] if k.startswith("biji-") else None


def load_cache(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_cache(path, cache):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=1, sort_keys=True)


def pick(races, cache, now, limit):
    """挑這次要抓的：沒抓過 > 太久沒更新；可報名／即將開報優先，比賽日近的優先。"""
    today = now.date().isoformat()
    order = {"closing_soon": 0, "open": 0, "upcoming": 0, "unknown": 1, "full": 2, "closed": 3}
    todo = []
    for r in races:
        cid = biji_cid(r)
        if not cid or not r.get("date") or r["date"] < today:
            continue
        c = cache.get(cid)
        if c:
            age = now - dt.datetime.fromisoformat(c["fetched_at"])
            if age < dt.timedelta(days=REFRESH_DAYS):
                continue
        todo.append((0 if not c else 1, order.get(r["registration"]["status"], 2), r["date"], cid))
    todo.sort()
    return [cid for *_, cid in todo[:limit]]


def update_cache(cache, races, now, limit=MAX_PER_RUN, delay=DELAY, fetch=None):
    """抓幾頁、更新快取；回傳 (成功數, 失敗數)。單頁失敗不影響整次排程。"""
    fetch = fetch or (lambda url: base.fetch_html(url, attempts=1, label="運動筆記詳情"))
    ok = bad = 0
    for n, cid in enumerate(pick(races, cache, now, limit)):
        if n:
            time.sleep(delay)
        try:
            d = parse_detail(fetch(DETAIL_URL.format(cid=cid)))
        except Exception as e:          # noqa: BLE001 — 單頁錯誤只記下，不中斷
            print(f"詳情頁 cid={cid} 失敗：{e}", file=sys.stderr)
            bad += 1
            continue
        d["fetched_at"] = now.isoformat(timespec="seconds")
        cache[cid] = d
        ok += 1
    return ok, bad

# ---------------------------------------------------------------
# 把詳情頁的資料補進賽事
# ---------------------------------------------------------------

def match_groups(dist, groups):
    """同一個距離的組別：標籤一樣，或距離差 0.3 公里以內（列表寫 42K、詳情頁寫 42.195K）。"""
    same = [g for g in groups if g["label"].upper() == dist["label"].upper()]
    if same or dist.get("km") is None:
        return same
    near = [g for g in groups if g["km"] is not None and abs(g["km"] - dist["km"]) <= 0.3]
    if not near:
        return []
    best = min(abs(g["km"] - dist["km"]) for g in near)
    return [g for g in near if abs(g["km"] - dist["km"]) == best]


def apply_details(races, cache):
    """補報名費、名額（只補空白）、關門時間、各組起跑時間、主辦單位、報名連結。"""
    for r in races:
        d = cache.get(biji_cid(r) or "")
        if not d:
            continue
        for dist in r["distances"]:
            gs = match_groups(dist, d["groups"])
            if not gs:
                continue
            fees = [g["fee"] for g in gs if g["fee"] is not None]
            quotas = [g["quota"] for g in gs if g["quota"] is not None]
            if dist.get("fee") is None and fees:
                dist["fee"] = min(fees)
            if dist.get("quota") is None and quotas:
                dist["quota"] = quotas[0]
            g = next((g for g in gs if g["time_limit"]), gs[0])
            dist["time_limit"] = g["time_limit"]
            dist["time_limit_text"] = g["time_limit_text"]
            dist["start"] = g["start"]
        if not r.get("organizer") and d.get("organizer"):
            r["organizer"] = d["organizer"]
        if not r.get("url") and (d.get("signup_url") or d.get("brochure_url")):
            r["url"] = d.get("signup_url") or d.get("brochure_url")
            r["issues"] = [i for i in r["issues"] if i != "沒有報名連結"]
    return races
