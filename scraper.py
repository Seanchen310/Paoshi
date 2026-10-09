"""
跑事｜跑者廣場賽事爬蟲

抓取跑者廣場「全國賽會」頁（http://www.taipeimarathon.org.tw/contest.aspx），
整理成結構化資料：
  - races.json：給網站／App 使用
  - races.csv ：用 Excel 打開檢查

只用 Python 內建模組，不需要另外安裝套件。

這個檔案也放兩個來源共用的工具（距離分類、縣市、報名狀態、輸出）。
執行請用 run.py（會同時抓跑者廣場和運動筆記並合併）。
"""

import csv
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.request
from html.parser import HTMLParser

SOURCE_NAME = "跑者廣場"
SOURCE_URL = "http://www.taipeimarathon.org.tw/contest.aspx"
USER_AGENT = "PaoshiBot/0.1 (race calendar; low-frequency, 1 request per run)"
TZ = dt.timezone(dt.timedelta(hours=8))  # 台灣時間

# ---------------------------------------------------------------
# 1. 下載與解析 HTML
# ---------------------------------------------------------------

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.6",
}


def fetch_html(url=SOURCE_URL, timeout=30, attempts=3, wait=20, label=SOURCE_NAME):
    """下載網頁；遇到伺服器錯誤或連線問題會等一下再試，最多試 attempts 次。"""
    import time
    import urllib.error
    last = None
    for i in range(1, attempts + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            last = e
            print(f"第 {i} 次下載失敗：網站回應 HTTP {e.code}", file=sys.stderr)
            if e.code < 500 and e.code != 429:
                break  # 4xx（例如被拒絕）重試也沒用
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = e
            print(f"第 {i} 次下載失敗：{e}", file=sys.stderr)
        if i < attempts:
            time.sleep(wait * i)
    raise RuntimeError(f"無法下載{label}賽事頁（{last}）")


class GridParser(HTMLParser):
    """把 <table id="GridView1"> 的每一列轉成原始欄位。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_grid = False
        self.depth = 0          # 在 GridView1 裡的 table 巢狀深度
        self.row = None         # 目前這一列：list of cells
        self.cell = None        # 目前這一格
        self.button = None      # 目前的距離按鈕
        self.rows = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            if a.get("id") == "GridView1":
                self.in_grid, self.depth = True, 1
                return
            if self.in_grid:
                self.depth += 1
        if not self.in_grid:
            return
        if tag == "tr":
            self.row = {"class": a.get("class", "") or "", "cells": []}
        elif tag in ("td", "th") and self.row is not None:
            self.cell = {"tag": tag, "text": "", "href": "", "imgs": [], "buttons": []}
        elif self.cell is not None:
            if tag == "a" and not self.cell["href"]:
                self.cell["href"] = a.get("href", "") or ""
            elif tag == "img":
                src = a.get("src", "") or ""
                self.cell["imgs"].append(src.rsplit("/", 1)[-1])
            elif tag == "button":
                self.button = {"text": "", "title": a.get("title", "") or ""}
            elif tag == "br":
                self.cell["text"] += " "

    def handle_endtag(self, tag):
        if not self.in_grid:
            return
        if tag == "table":
            self.depth -= 1
            if self.depth == 0:
                self.in_grid = False
            return
        if tag == "button" and self.button is not None and self.cell is not None:
            self.cell["buttons"].append(self.button)
            self.button = None
        elif tag in ("td", "th") and self.cell is not None and self.row is not None:
            self.row["cells"].append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.button is not None:
            self.button["text"] += data
        if self.cell is not None:
            self.cell["text"] += data


def squash(s):
    return re.sub(r"\s+", " ", s or "").strip()


def parse_html(html):
    """回傳原始列：每列 11 個欄位，跟瀏覽器裡抓到的格式一致。"""
    p = GridParser()
    p.feed(html)
    out = []
    for r in p.rows:
        c = r["cells"]
        if len(c) < 8 or c[0]["tag"] == "th":
            continue  # 標題列或格式不符
        dists = "|".join(
            squash(b["text"]) + "§" + re.sub(r"^費用：", "", b["title"])
            for b in c[5]["buttons"]
        )
        out.append([
            squash(c[0]["text"]), ",".join(c[0]["imgs"]),
            squash(c[1]["text"]), c[1]["href"],
            ",".join(c[2]["imgs"]),
            squash(c[3]["text"]), squash(c[4]["text"]),
            dists, squash(c[6]["text"]), squash(c[7]["text"]),
            r["class"],
        ])
    return out

# ---------------------------------------------------------------
# 2. 整理成結構化資料
# ---------------------------------------------------------------

REGIONS = {
    "北部": ["臺北市", "新北市", "基隆市", "桃園市", "新竹市", "新竹縣", "宜蘭縣"],
    "中部": ["苗栗縣", "臺中市", "彰化縣", "南投縣", "雲林縣"],
    "南部": ["嘉義市", "嘉義縣", "臺南市", "高雄市", "屏東縣"],
    "東部": ["花蓮縣", "臺東縣"],
    "離島": ["澎湖縣", "金門縣", "連江縣"],
}
COUNTY_TO_REGION = {c: r for r, cs in REGIONS.items() for c in cs}
WEEKDAYS = "一二三四五六日"


def find_county(location):
    loc = (location or "").replace("台", "臺")
    for county in COUNTY_TO_REGION:
        if county in loc:
            return county
    # 「七股…台南市…」這類地址寫在後面的情況已在上面處理；
    # 有些只寫鄉鎮（如「七股」），對照不到就留空
    return None


def parse_km(label):
    """把距離標籤轉成公里數；不是單純距離的回傳 None。"""
    s = label.strip()
    m = re.fullmatch(r"([\d.]+)\s*miles?", s, re.I) or re.fullmatch(r"([\d.]+)\s*mi", s, re.I)
    if m:
        return round(float(m.group(1)) * 1.609344, 1)
    m = re.fullmatch(r"([\d.]+)\s*[Kk]", s)
    if m:
        return float(m.group(1))
    return None


def classify(label, km):
    s = label
    if "+" in s:
        return "triathlon"      # 鐵人三項／二鐵
    if "接力" in s or re.search(r"[xX×]\s*\d", s):
        return "relay"
    if re.fullmatch(r"\d+\s*[Hh]", s.strip()):
        return "timed"          # 計時賽（6H、24H）
    if "線上" in s:
        return "virtual"
    if km is None:
        return "other"
    if km > 42.3:
        return "ultra"
    if km >= 42:
        return "full"
    if 20 <= km <= 25:
        return "half"
    if 9 <= km < 20:
        return "10k"
    if km < 9:
        return "short"
    return "long"               # 25–42K 之間


def parse_fee_quota(title):
    """按鈕 title 格式範例：'1400<br/>限額：1500'、' 100<br/>限額： 共500人'、'0'。"""
    t = (title or "").replace("<br/>", "\n").replace("<br>", "\n")
    fee = quota = None
    shared = False
    head, _, tail = t.partition("限額")
    m = re.search(r"\d+", head)
    if m:
        fee = int(m.group(0))
    if tail:
        shared = "共" in tail
        m = re.search(r"\d+", tail)
        if m:
            quota = int(m.group(0))  # 單位可能是人、隊或組，只記數字
    return fee, quota, shared


def parse_distances(raw):
    out = []
    if not raw:
        return out
    for part in raw.split("|"):
        label, _, title = part.partition("§")
        label = label.strip()
        if not label:
            continue
        # 統一大小寫：22k → 22K（miles 保留）
        label = re.sub(r"(?<=\d)k\b", "K", label)
        km = parse_km(label)
        fee, quota, shared = parse_fee_quota(title)
        out.append({
            "label": label,
            "km": km,
            "category": classify(label, km),
            "fee": fee,
            "quota": quota,
            "quota_shared": shared,
        })
    return out


def assign_years(raw_rows, today):
    """跑者廣場只寫月/日。列表依日期排序，月份變小代表跨年。"""
    year = today.year
    prev_month = None
    years = []
    for r in raw_rows:
        m = re.match(r"(\d{1,2})/(\d{1,2})", r[5])
        if not m:
            years.append(None)
            continue
        month = int(m.group(1))
        if prev_month is not None and month < prev_month:
            year += 1
        prev_month = month
        years.append(year)
    return years


def md_to_date(text, year):
    m = re.search(r"(\d{1,2})月\s*(\d{1,2})日", text)
    if not m:
        return None
    try:
        return dt.date(year, int(m.group(1)), int(m.group(2)))
    except ValueError:
        return None


def parse_registration(text, race_date, today):
    """
    報名欄的各種寫法：
      已截止 / （空白）/ ~ 10月18日 / 10月12日 ~ 10月18日 / 6月22日 ~ / ... (最後一週)
    回傳 (dict, issues)
    """
    issues = []
    raw = (text or "").strip()
    reg = {"raw": raw, "start": None, "end": None, "start_at": None, "end_at": None,
           "status": "unknown", "days_left": None}
    if raw == "已截止":
        reg["status"] = "closed"
        return reg, issues
    if not raw or race_date is None:
        return reg, issues

    left, sep, right = raw.partition("~")
    start_txt, end_txt = (left, right) if sep else ("", left)
    ry = race_date.year

    end = md_to_date(end_txt, ry)
    if end and end > race_date:
        end = md_to_date(end_txt, ry - 1)
    start = md_to_date(start_txt, ry)
    if start:
        limit = end or race_date
        if start > limit:
            start = md_to_date(start_txt, ry - 1)
    if start and end and (start > end or (end - start).days > 330):
        issues.append("報名起訖日期疑似顛倒：" + raw)
        start = None  # 開始日不可信，只保留截止日

    reg["start"] = start.isoformat() if start else None
    reg["end"] = end.isoformat() if end else None
    reg["status"], reg["days_left"] = reg_status(start, end, today)
    return reg, issues


def reg_status(start, end, today):
    """依報名起訖日（date 或 None）算出 (status, days_left)。"""
    if end and today > end:
        return "closed", None
    if start and today < start:
        return "upcoming", None
    if end:
        left_days = (end - today).days
        return ("closing_soon" if left_days <= 7 else "open"), left_days
    return "open", None


def make_id(date_iso, name):
    h = hashlib.sha1((date_iso + "|" + name).encode("utf-8")).hexdigest()[:8]
    return f"{date_iso}-{h}"


def normalize(raw_rows, today, scraped_at):
    years = assign_years(raw_rows, today)
    races = []
    for r, year in zip(raw_rows, years):
        (_month_tag, flag_imgs, name, url, cert_imgs, date_txt,
         location, dist_raw, organizer, reg_txt, _cls) = r
        issues = []

        m = re.match(r"(\d{1,2})/(\d{1,2})\s*(\S)?\s*(\d{1,2}:\d{2})?", date_txt)
        race_date = None
        start_time = None
        if m and year:
            try:
                race_date = dt.date(year, int(m.group(1)), int(m.group(2)))
            except ValueError:
                issues.append("日期無法解析：" + date_txt)
            start_time = m.group(4)
            wd = m.group(3)
            if race_date and wd in WEEKDAYS and WEEKDAYS[race_date.weekday()] != wd:
                issues.append(f"星期不符：{date_txt}（推算年份 {year}）")
        else:
            issues.append("日期無法解析：" + date_txt)

        name_year = re.match(r"\s*(20\d{2})", name)
        if name_year and race_date and int(name_year.group(1)) != race_date.year:
            issues.append(f"賽名年份 {name_year.group(1)} 與比賽日期 {race_date.year} 不符")

        distances = parse_distances(dist_raw)
        if not distances:
            issues.append("沒有距離資料")
        if not url:
            issues.append("沒有報名連結")
        if not location:
            issues.append("沒有地點")

        reg, reg_issues = parse_registration(reg_txt, race_date, today)
        issues += reg_issues

        cats = sorted({d["category"] for d in distances})
        county = find_county(location)
        certs = []
        if "aims_logo.gif" in cert_imgs:
            certs.append("AIMS")
        if "iaaf.gif" in cert_imgs:
            certs.append("IAAF")
        if "course_ok.png" in cert_imgs:
            certs.append("measured")

        date_iso = race_date.isoformat() if race_date else ""
        races.append({
            "id": make_id(date_iso, name),
            "name": name,
            "alt_names": [],
            "date": date_iso or None,
            "start_time": start_time,
            "location": location or None,
            "address": None,
            "county": county,
            "region": COUNTY_TO_REGION.get(county),
            "distances": distances,
            "categories": cats,
            "organizer": organizer or None,
            "registration": reg,
            "url": url or None,
            "certifications": certs,
            "flag": "new" if "new.gif" in flag_imgs else ("updated" if "update.png" in flag_imgs else None),
            "postponed_from": None,
            "issues": issues,
            "sources": [{"name": SOURCE_NAME, "url": SOURCE_URL, "scraped_at": scraped_at}],
        })
    return races

# ---------------------------------------------------------------
# 3. 輸出
# ---------------------------------------------------------------

CAT_ZH = {"full": "全馬", "half": "半馬", "10k": "10K", "short": "10K以下", "long": "25-42K",
          "ultra": "超馬", "triathlon": "鐵人", "relay": "接力", "timed": "計時賽",
          "virtual": "線上", "other": "其他"}
STATUS_ZH = {"open": "報名中", "closing_soon": "快截止", "upcoming": "即將開報",
             "closed": "已截止", "unknown": "未知"}


def write_outputs(races, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    jpath = os.path.join(out_dir, "races.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump({"count": len(races), "races": races}, f, ensure_ascii=False, indent=2)

    cpath = os.path.join(out_dir, "races.csv")
    with open(cpath, "w", encoding="utf-8-sig", newline="") as f:  # utf-8-sig：Excel 才不會亂碼
        w = csv.writer(f)
        w.writerow(["日期", "時間", "賽事名稱", "縣市", "地區", "地點", "地址", "距離", "分類",
                    "報名狀態", "報名開始", "報名截止", "剩幾天", "最低報名費", "認證",
                    "承辦單位", "報名連結", "來源", "資料問題"])
        for r in races:
            fees = [d["fee"] for d in r["distances"] if d["fee"]]
            w.writerow([
                r["date"], r["start_time"], r["name"], r["county"], r["region"], r["location"],
                r["address"],
                " / ".join(d["label"] for d in r["distances"]),
                "、".join(CAT_ZH.get(c, c) for c in r["categories"]),
                STATUS_ZH[r["registration"]["status"]],
                r["registration"]["start"], r["registration"]["end"], r["registration"]["days_left"],
                min(fees) if fees else "", "、".join(r["certifications"]),
                r["organizer"], r["url"], "、".join(x["name"] for x in r["sources"]),
                "；".join(r["issues"]),
            ])
    return jpath, cpath


def summarize(races):
    from collections import Counter
    st = Counter(r["registration"]["status"] for r in races)
    lines = [f"共 {len(races)} 場賽事"]
    lines.append("  " + "、".join(f"{STATUS_ZH[k]} {v}" for k, v in st.most_common()))
    src = Counter("＋".join(x["name"] for x in r["sources"]) for r in races)
    if len(src) > 1:
        lines.append("  來源：" + "、".join(f"{k} {v}" for k, v in src.most_common()))
    flagged = [r for r in races if r["issues"]]
    lines.append(f"  有資料問題的賽事：{len(flagged)} 場（寫在 races.csv 最後一欄）")
    return "\n".join(lines)
