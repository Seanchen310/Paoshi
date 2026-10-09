#!/usr/bin/env python3
"""
跑事｜產生網站（Cloudflare Pages 每次部署時執行：python3 build_site.py）

  1. output/races.json → site/races.json（網頁讀這份）
  2. 每場比賽一個靜態網頁 site/race/<key>/index.html
     內容直接寫在 HTML 裡（賽名、日期、地點、報名費…）＋ schema.org 賽事結構化資料，
     讓 Google 收錄「XX 馬拉松 報名」。打開後 app.js 會用最新資料、依當下時間重算狀態。
  3. site/sitemap.xml、site/robots.txt

產生的檔案都不進 git（.gitignore），只在部署時產生。
"""

import argparse
import datetime as dt
import html
import json
import os
import shutil

SITE_URL = "https://paoshi.pages.dev"
WEEKDAYS = "一二三四五六日"
CAT_FULL_HALF = ("full", "half")
STATUS_TEXT = {"open": "報名中", "closing_soon": "快截止", "upcoming": "即將開報", "closed": "已截止",
               "full": "額滿", "unknown": "待確認"}
CERT_LABEL = {"AIMS": "AIMS 認證", "IAAF": "IAAF 認證", "measured": "丈量認證"}

ICON_BACK = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" '
             'stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>')
ICON_OUT = ('<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" '
            'stroke-linecap="round" stroke-linejoin="round"><path d="M7 17L17 7M9 7h8v8"/></svg>')

THEME_SCRIPT = """<script>
  (function () {
    var h = Number(new Date().toLocaleString('en-US', { timeZone: 'Asia/Taipei', hour: 'numeric', hour12: false })) % 24;
    var mode = h >= 6 && h < 18 ? 'day' : 'night';
    try {
      var o = JSON.parse(localStorage.getItem('paoshi-theme') || 'null');
      if (o && o.until > Date.now()) mode = o.mode;
    } catch (e) {}
    document.documentElement.setAttribute('data-theme', mode);
  })();
</script>"""

e = lambda s: html.escape(str(s if s is not None else ""), quote=True)  # noqa: E731


def md(iso):
    return f"{int(iso[5:7])}/{int(iso[8:10])}"


def weekday(iso):
    return WEEKDAYS[dt.date.fromisoformat(iso).weekday()]


def fee_text(f):
    return "免費" if f == 0 else f"NT${f:,}"


def unique_distances(r):
    seen, out = set(), []
    for d in r["distances"]:
        if d["label"] not in seen:
            seen.add(d["label"])
            out.append(d)
    return out


def period_text(reg):
    if not (reg.get("start") or reg.get("end")):
        raw = reg.get("raw") or ""
        return raw if raw and raw not in ("已截止", "已截止報名") else "未公布"
    s = reg["start"].replace("-", "/") + (" " + reg["start_at"][11:16] if reg.get("start_at") else "") if reg.get("start") else "未公布"
    t = md(reg["end"]) + (" " + reg["end_at"][11:16] if reg.get("end_at") else "") if reg.get("end") else "未公布"
    return f"{s} – {t}"


def status_text(reg):
    st = reg.get("status")
    if st == "open":
        if reg.get("days_left") is not None:
            return f"報名中 · 剩 {reg['days_left']} 天"
        return "報名中 · " + (f"截止日 {md(reg['end'])}" if reg.get("end") else "截止日未公布")
    if st == "closing_soon" and reg.get("end_at"):
        return f"快截止 · {md(reg['end_at'][:10])} {reg['end_at'][11:16]} 截止"
    if st == "upcoming" and reg.get("start"):
        return f"即將開報 · {md(reg['start'])}" + (f" {reg['start_at'][11:16]}" if reg.get("start_at") else "") + " 開報"
    return STATUS_TEXT.get(st, "報名資訊未公布")


def description(r):
    reg = r["registration"]
    county, loc = r.get("county") or "", (r.get("location") or r.get("address") or "").replace("台", "臺")
    where = loc if county and loc.startswith(county) else (county + (" " if county and loc else "") + loc)
    parts = [f"{r['date'].replace('-', '/')}（週{weekday(r['date'])}）在{where or '地點未公布'}舉行"]
    labels = [d["label"] for d in unique_distances(r)]
    if labels:
        parts.append("組別 " + "、".join(labels[:6]))
    parts.append("報名期間 " + period_text(reg))
    fees = [d["fee"] for d in r["distances"] if d.get("fee") is not None]
    if fees:
        parts.append("報名費 " + fee_text(min(fees)) + (" 起" if min(fees) else ""))
    return "。".join(parts) + "。"


def json_ld(r, url):
    """schema.org SportsEvent：Google 搜尋結果可能顯示日期、地點。"""
    reg = r["registration"]
    start = r["date"] + (f"T{r['start_time']}:00+08:00" if r.get("start_time") else "")
    avail = {"open": "InStock", "closing_soon": "LimitedAvailability", "upcoming": "PreOrder",
             "full": "SoldOut", "closed": "SoldOut"}.get(reg.get("status"))
    offers = []
    for d in unique_distances(r):
        if d.get("fee") is None:
            continue
        o = {"@type": "Offer", "name": d["label"], "price": d["fee"], "priceCurrency": "TWD",
             "url": r.get("url") or url}
        if reg.get("start"):
            o["validFrom"] = (reg.get("start_at") or reg["start"] + "T00:00") + ":00+08:00"
        if avail:
            o["availability"] = "https://schema.org/" + avail
        offers.append(o)
    data = {
        "@context": "https://schema.org", "@type": "SportsEvent", "name": r["name"],
        "startDate": start, "url": url, "description": description(r),
        "eventStatus": "https://schema.org/" + ("EventRescheduled" if r.get("postponed_from") else "EventScheduled"),
        "eventAttendanceMode": "https://schema.org/OfflineEventAttendanceMode",
        "sport": "Running",
        "location": {"@type": "Place", "name": r.get("location") or r.get("county") or "臺灣",
                     "address": {"@type": "PostalAddress", "streetAddress": r.get("address") or r.get("location") or "",
                                 "addressRegion": r.get("county") or "", "addressCountry": "TW"}},
    }
    if r.get("postponed_from"):
        data["previousStartDate"] = r["postponed_from"]
    if r.get("organizer"):
        data["organizer"] = {"@type": "Organization", "name": r["organizer"]}
    if offers:
        data["offers"] = offers
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def race_page(r, scraped):
    reg = r["registration"]
    url = f"{SITE_URL}/race/{r['key']}/"
    title = f"{r['name']} 報名資訊｜跑事"
    desc = description(r)
    badges = []
    if r.get("postponed_from"):
        badges.append(f'<span class="tag alert">已延期（原訂 {md(r["postponed_from"])}）</span>')
    if "trail" in r["categories"]:
        badges.append('<span class="tag">越野</span>')
    badges += [f'<span class="cert">{CERT_LABEL[c]}</span>' for c in r["certifications"] if c in CERT_LABEL]
    badges.append(f'<span class="status {e(reg.get("status"))}">{e(status_text(reg))}</span>')
    info = [("地點", e(r.get("location") or r.get("address") or "未公布")
             + (f"<small>{e(r['address'])}</small>" if r.get("location") and r.get("address") else "")),
            ("報名期間", e(period_text(reg)))]
    if r.get("organizer"):
        info.append(("承辦單位", e(r["organizer"])))
    groups = unique_distances(r)
    has_fee = any(d.get("fee") is not None or d.get("quota") is not None for d in groups)
    rows = "".join(
        f'<div class="grp"><span class="d {d["category"] if d["category"] in CAT_FULL_HALF else ""}">{e(d["label"])}</span>'
        f'<span class="q">{("名額 " + format(d["quota"], ",") + ("（共用）" if d.get("quota_shared") else "")) if d.get("quota") is not None else ("名額未公布" if has_fee else "")}</span>'
        f'<span class="f">{fee_text(d["fee"]) if d.get("fee") is not None else ""}</span></div>'
        for d in groups)
    srcs = "、".join(f'<a href="{e(s["url"])}" target="_blank" rel="noopener">{e(s["name"])}</a>' for s in r["sources"])
    can_signup = reg.get("status") in ("open", "closing_soon") and r.get("url")
    if can_signup:
        cta = f'<a class="cta" href="{e(r["url"])}" target="_blank" rel="noopener">前往報名 {ICON_OUT}</a>'
    elif r.get("url"):
        cta = f'<a class="cta" href="{e(r["url"])}" target="_blank" rel="noopener">查看官方網站 {ICON_OUT}</a>'
    else:
        cta = f'<a class="cta" href="{e(r["sources"][-1]["url"])}" target="_blank" rel="noopener">看賽事資訊 {ICON_OUT}</a>'
    when = f'{r["date"][:4]} · 週{weekday(r["date"])}' + (f' {e(r["start_time"])} 起跑' if r.get("start_time") else "")
    aka = (f'<div class="aka">也稱：{"、".join(e(n) for n in r["alt_names"])}</div>' if r.get("alt_names") else "")
    return f"""<!doctype html>
<html lang="zh-Hant" data-theme="day">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{e(title)}</title>
<meta name="description" content="{e(desc)}">
<link rel="canonical" href="{url}">
<meta property="og:type" content="website">
<meta property="og:site_name" content="跑事">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(desc)}">
<meta property="og:url" content="{url}">
<meta name="theme-color" content="#E8F1F8">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="/style.css">
<script type="application/ld+json">{json_ld(r, url)}</script>
{THEME_SCRIPT}
</head>
<body>
<div class="app is-detail" id="app" data-prerendered="1">
  <div class="bar"><a class="icon-btn" href="/" data-act="back" aria-label="返回列表">{ICON_BACK}</a></div>
  <main class="detail">
    <section class="hero">
      <div class="badges">{"".join(badges)}</div>
      <h1>{e(r["name"])}</h1>
      {aka}
      <div class="when"><span class="big">{r["date"][5:7]}.{r["date"][8:10]}</span><span>{when}</span></div>
    </section>
    <dl class="box info">{"".join(f"<div><dt>{k}</dt><dd>{v}</dd></div>" for k, v in info)}</dl>
    {f'<section class="sec"><h2>組別</h2><div class="box groups">{rows}</div></section>' if groups else ""}
    <p class="fine">賽事資訊整理自{srcs}（{scraped[:10].replace("-", "/")} 更新），報名與最新內容以主辦單位官網為準。<a href="/">看更多可報名的比賽</a></p>
  </main>
  <div class="actions">{cta}</div>
</div>
<div id="sheet"></div>
<div id="toast" class="toast hidden" role="status" aria-live="polite"></div>
<script src="/app.js"></script>
</body>
</html>
"""


def build(races_json, site_dir):
    with open(races_json, encoding="utf-8") as f:
        data = json.load(f)
    races = data["races"]
    shutil.copyfile(races_json, os.path.join(site_dir, "races.json"))

    race_dir = os.path.join(site_dir, "race")
    if os.path.isdir(race_dir):
        shutil.rmtree(race_dir)              # 已經不在資料裡的比賽，網頁也拿掉
    stamps = sorted(s["scraped_at"] for r in races for s in r["sources"] if s.get("scraped_at"))
    scraped = stamps[-1] if stamps else dt.datetime.now().isoformat()
    urls = [(f"{SITE_URL}/", scraped[:10])]
    for r in races:
        if not r.get("date") or not r.get("key"):
            continue
        d = os.path.join(race_dir, r["key"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(race_page(r, scraped))
        urls.append((f"{SITE_URL}/race/{r['key']}/", scraped[:10]))

    with open(os.path.join(site_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for u, last in urls:
            f.write(f"  <url><loc>{u}</loc><lastmod>{last}</lastmod></url>\n")
        f.write("</urlset>\n")
    with open(os.path.join(site_dir, "robots.txt"), "w", encoding="utf-8") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE_URL}/sitemap.xml\n")
    return len(urls) - 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="產生跑事網站的靜態檔案")
    ap.add_argument("--data", default="output/races.json")
    ap.add_argument("--site", default="site")
    args = ap.parse_args(argv)
    n = build(args.data, args.site)
    print(f"已產生 {n} 場比賽的網頁、sitemap.xml、robots.txt")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
