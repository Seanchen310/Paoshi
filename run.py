#!/usr/bin/env python3
"""
跑事｜抓取所有來源、合併、輸出

  1. 跑者廣場 contest.aspx（1 個請求）
  2. 運動筆記 賽事列表（1 個請求）
  3. 合併同一場比賽 → output/races.json、output/races.csv
  4. 和上一次比對，記下變化 → history/（加上 --history history 才會記）

只用 Python 內建模組，不需要另外安裝套件。

用法：
  python3 run.py                                    # 抓網站，輸出到 output/
  python3 run.py --html 跑者廣場.html --biji-html 運動筆記.html   # 改用存下來的網頁檔（測試用）

任何一個來源下載或解析失敗，就不更新資料（保留上一次的結果），避免一半的賽事突然消失。
"""

import argparse
import datetime as dt
import os
import sys

import biji
import history
import merge
import scraper


def load(label, path, fetch, out_dir, saved_name):
    """讀本機檔或下載；下載的話留一份原始網頁，出問題時可以重跑解析。"""
    if path:
        with open(path, encoding="utf-8") as f:
            return f.read()
    print(f"下載{label}賽事頁…")
    html = fetch()
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, saved_name), "w", encoding="utf-8") as f:
        f.write(html)
    return html


def main(argv=None):
    ap = argparse.ArgumentParser(description="抓取跑者廣場、運動筆記賽事，合併成 JSON / CSV")
    ap.add_argument("--html", help="跑者廣場：改用本機的 HTML 檔，不連網")
    ap.add_argument("--biji-html", help="運動筆記：改用本機的 HTML 檔，不連網")
    ap.add_argument("--out", default="output", help="輸出資料夾（預設 output）")
    ap.add_argument("--today", help="指定今天日期 YYYY-MM-DD（測試用）")
    ap.add_argument("--history", help="歷史紀錄資料夾（排程用 history；不給就不記錄）")
    args = ap.parse_args(argv)

    now = dt.datetime.now(scraper.TZ)
    today = dt.date.fromisoformat(args.today) if args.today else now.date()
    scraped_at = now.isoformat(timespec="seconds")

    try:
        pz_html = load("跑者廣場", args.html, scraper.fetch_html, args.out, "source.html")
        bj_html = load("運動筆記", args.biji_html, biji.fetch_html, args.out, "source_biji.html")
    except RuntimeError as e:
        print(e, file=sys.stderr)
        return 2

    pz_raw = scraper.parse_html(pz_html)
    bj_raw = biji.parse_html(bj_html)
    if not pz_raw or not bj_raw:
        which = "跑者廣場" if not pz_raw else "運動筆記"
        print(f"找不到{which}的賽事列表，網站可能改版了。原始網頁已存在 {args.out}/。", file=sys.stderr)
        return 1

    pz = scraper.normalize(pz_raw, today, scraped_at)
    bj = biji.normalize(bj_raw, today, scraped_at)
    races = scraper.tag_trail(merge.merge(pz, bj, today))
    jpath, cpath = scraper.write_outputs(races, args.out)
    print(f"跑者廣場 {len(pz)} 場、運動筆記 {len(bj)} 場（不含海外）→ 合併後 {len(races)} 場")
    print(scraper.summarize(races))
    print(f"已輸出：{jpath}\n        {cpath}")
    if args.history:
        when = now if not args.today else dt.datetime.combine(today, now.time(), now.tzinfo)
        events = history.update(args.history, races, when)
        print(f"歷史紀錄：這次有 {len(events)} 筆變化（{args.history}/CHANGES.md）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
