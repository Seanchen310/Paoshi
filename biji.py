#!/usr/bin/env python3
"""
跑事｜運動筆記賽事爬蟲

抓取運動筆記「國內賽事」列表（https://running.biji.co/index.php?q=competition），
一頁就有今年本月起所有賽事，只需要 1 個請求。

列表每一列的「加入行事曆」連結裡藏著最完整的資料：
  dates=20261009/20261010、location=完整地址、報名日期:2026-03-01 00:00:00~2026-09-01 12:00:00
報名費、主辦單位、關門時間只在各賽事詳情頁，這裡先不抓（一場一個請求太多）。

用法：
  python3 biji.py --html 檔案.html   # 解析存下來的網頁，印出摘要（測試用）
"""

import argparse
import datetime as dt
import re
import sys
import urllib.parse
from html.parser import HTMLParser

import scraper as base

SOURCE_NAME = "運動筆記"
SOURCE_URL = "https://running.biji.co/index.php?q=competition"
SITE = "https://running.biji.co"


def fetch_html():
    return base.fetch_html(SOURCE_URL, label=SOURCE_NAME)


class ListParser(HTMLParser):
    """把每個 <div class="competition-list-row"> 轉成原始欄位 dict。"""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.row = None       # 目前這一列
        self.depth = 0        # 在這一列裡的 div 深度
        self.field = None     # 目前在收集哪個欄位的文字
        self.field_depth = 0
        self.rows = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        cls = (a.get("class") or "").split()
        if self.row is None:
            if tag == "div" and "competition-list-row" in cls:
                self.row = {"cid": (a.get("id") or "").replace("cp_part_", ""),
                            "ad": "ad-row" in cls, "date_title": "", "calendar": "",
                            "place": "", "name": "", "href": "", "events": [],
                            "status": "", "hot": False, "certs": []}
                self.depth = 1
            return
        if tag == "div":
            self.depth += 1
            for c, f in (("competition-date-title", "date_title"), ("competition-place", "place"),
                         ("event_item", "events"), ("competition-status", "status")):
                if c in cls:
                    self.field, self.field_depth = f, self.depth
                    if f == "events":
                        self.row["events"].append("")
            if "competition-name" in cls:
                self.field, self.field_depth = "name", self.depth
        elif tag == "a":
            href = a.get("href") or ""
            if "competition-date-calendar" in cls:
                self.row["calendar"] = href
            elif self.field == "name" and not self.row["href"]:
                self.row["href"] = href
        elif tag == "img":
            if "hot-icon" in cls:
                self.row["hot"] = True
            src = a.get("src") or ""
            if "/default/comp/" in src:
                self.row["certs"].append(src.rsplit("/", 1)[-1])

    def handle_endtag(self, tag):
        if self.row is None or tag != "div":
            return
        if self.field and self.depth == self.field_depth:
            self.field = None
        self.depth -= 1
        if self.depth == 0:
            self.rows.append(self.row)
            self.row = None

    def handle_data(self, data):
        if self.row is None or not self.field:
            return
        if self.field == "events":
            self.row["events"][-1] += data
        else:
            self.row[self.field] += data


def parse_html(html):
    """回傳原始列（廣告列是重複的賽事，同一個 cid 只留一筆）。"""
    p = ListParser()
    p.feed(html)
    out, seen = [], set()
    for r in p.rows:
        if not r["cid"] or r["cid"] in seen:
            continue
        seen.add(r["cid"])
        for k in ("date_title", "place", "name", "status"):
            r[k] = base.squash(r[k])
        r["events"] = [base.squash(e) for e in r["events"] if base.squash(e)]
        out.append(r)
    return out

# ---------------------------------------------------------------
# 整理成跟跑者廣場一樣的格式
# ---------------------------------------------------------------

CERTS = {"aims.png": "AIMS", "iaaf_gold.png": "IAAF", "ctaa.png": "measured", "jaaf.png": "JAAF"}


def parse_calendar(href):
    """從 Google 行事曆連結取出 (比賽日期, 地址, 報名開始, 報名截止)；後兩者是 datetime 或 None。"""
    href = urllib.parse.unquote(href or "")
    race_date = address = start = end = None
    m = re.search(r"[?&]dates=(\d{8})/", href)
    if m:
        race_date = dt.datetime.strptime(m.group(1), "%Y%m%d").date()
    m = re.search(r"&location=(.*?)&details=", href)
    if m:
        address = base.squash(m.group(1)) or None
    m = re.search(r"報名日期:(\d{4}-\d\d-\d\d \d\d:\d\d)(?::\d\d)?~(\d{4}-\d\d-\d\d \d\d:\d\d)", href)
    if m:
        start = dt.datetime.strptime(m.group(1), "%Y-%m-%d %H:%M")
        end = dt.datetime.strptime(m.group(2), "%Y-%m-%d %H:%M")
    return race_date, address, start, end


def last_day(end):
    """報名截止 00:00 代表前一天晚上就截止了。"""
    if end is None:
        return None
    d = end.date()
    return d - dt.timedelta(days=1) if end.time() == dt.time(0, 0) else d


def parse_registration(status_txt, start, end, race_date, today):
    issues = []
    reg = {"raw": status_txt, "start": None, "end": None, "start_at": None, "end_at": None,
           "status": "unknown", "days_left": None}
    if start and end:
        if start > end:
            issues.append("報名起訖日期疑似顛倒")
            start = None
        s_day, e_day = (start.date() if start else None), last_day(end)
        reg.update(start=s_day.isoformat() if s_day else None, end=e_day.isoformat(),
                   start_at=start.isoformat(timespec="minutes") if start else None,
                   end_at=end.isoformat(timespec="minutes"))
        reg["status"], reg["days_left"] = base.reg_status(s_day, e_day, today)
        if race_date and e_day > race_date:
            issues.append("報名截止日在比賽日之後")
    elif status_txt == "已截止報名":
        reg["status"] = "closed"
    else:
        m = re.fullmatch(r"(\d\d)-(\d\d)截止", status_txt)
        if m and race_date:  # 行事曆連結沒有報名日期時的備案：只有月-日
            e = dt.date(race_date.year, int(m.group(1)), int(m.group(2)))
            if e > race_date:
                e = e.replace(year=e.year - 1)
            reg["end"] = e.isoformat()
            reg["status"], reg["days_left"] = base.reg_status(None, e, today)
    return reg, issues


def is_overseas(r):
    """國內列表裡偶爾混入日本、香港等海外賽事：地點和地址都對不到臺灣縣市就算海外。"""
    address = parse_calendar(r["calendar"])[1]
    return not (base.find_county(r["place"]) or base.find_county(address))


def normalize(raw_rows, today, scraped_at):
    races = []
    for r in raw_rows:
        if is_overseas(r):
            continue
        issues = []
        race_date, address, reg_start, reg_end = parse_calendar(r["calendar"])
        if race_date is None:
            m = re.match(r"(\d{4})\.(\d\d)\.(\d\d)", r["date_title"])  # 廣告列的寫法
            if m:
                race_date = dt.date(*map(int, m.groups()))
            else:
                issues.append("日期無法解析：" + r["date_title"])

        m = re.search(r"\(週\s*(\S)\)", r["date_title"])
        if race_date and m and base.WEEKDAYS[race_date.weekday()] != m.group(1):
            issues.append(f"星期不符：{r['date_title']}")

        postponed_from = None
        m = re.search(r"原(\d{4})/(\d{1,2})/(\d{1,2})\s*因故.*?至(\d{4})/(\d{1,2})/(\d{1,2})", r["status"])
        if m:
            g = list(map(int, m.groups()))
            postponed_from = dt.date(*g[:3]).isoformat()
            if race_date and dt.date(*g[3:]) != race_date:
                issues.append("延期說明的日期與比賽日期不一致：" + r["status"])

        name = r["name"]
        name_year = re.match(r"\s*(20\d{2})", name)
        if name_year and race_date and int(name_year.group(1)) != race_date.year:
            issues.append(f"賽名年份 {name_year.group(1)} 與比賽日期 {race_date.year} 不符")

        distances = base.parse_distances("|".join(r["events"]))
        if not distances:
            issues.append("沒有距離資料")

        reg, reg_issues = parse_registration(r["status"], reg_start, reg_end, race_date, today)
        issues += reg_issues

        county = base.find_county(r["place"]) or base.find_county(address)
        date_iso = race_date.isoformat() if race_date else ""
        page = urllib.parse.urljoin(SITE, r["href"]) if r["href"] else SOURCE_URL
        page = re.sub(r"&subtitle=.*", "", page)  # 網址裡的中文賽名拿掉，比較短
        races.append({
            "id": base.make_id(date_iso, name),
            "name": name,
            "alt_names": [],
            "date": date_iso or None,
            "start_time": None,
            "location": None,
            "address": address,
            "county": county,
            "region": base.COUNTY_TO_REGION.get(county),
            "distances": distances,
            "categories": sorted({d["category"] for d in distances}),
            "organizer": None,
            "registration": reg,
            "url": None,
            "certifications": [CERTS[c] for c in r["certs"] if c in CERTS],
            "flag": None,
            "postponed_from": postponed_from,
            "issues": issues,
            "sources": [{"name": SOURCE_NAME, "url": page, "scraped_at": scraped_at}],
        })
    return races


def main(argv=None):
    ap = argparse.ArgumentParser(description="解析運動筆記賽事列表（測試用）")
    ap.add_argument("--html", required=True)
    ap.add_argument("--today")
    args = ap.parse_args(argv)
    today = dt.date.fromisoformat(args.today) if args.today else dt.datetime.now(base.TZ).date()
    with open(args.html, encoding="utf-8") as f:
        races = normalize(parse_html(f.read()), today, "")
    print(base.summarize(races))
    return 0


if __name__ == "__main__":
    sys.exit(main())
