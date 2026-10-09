import datetime as dt
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import biji_detail as bd  # noqa: E402

TZ = dt.timezone(dt.timedelta(hours=8))
NOW = dt.datetime(2026, 10, 10, 6, 7, tzinfo=TZ)


def pages():
    with open(os.path.join(HERE, "fixture_biji_detail.html"), encoding="utf-8") as f:
        parts = f.read().split("<!-- cid=")[1:]
    return {p.split(" ")[0]: p for p in parts}


class TestParse(unittest.TestCase):
    def setUp(self):
        self.p = pages()

    def test_groups(self):
        d = bd.parse_detail(self.p["12943"])
        self.assertEqual(d["organizer"], "嘉義市諸羅山長跑協會")
        g = {x["label"]: x for x in d["groups"]}
        self.assertEqual((g["100K"]["fee"], g["100K"]["time_limit"], g["100K"]["quota"], g["100K"]["start"]),
                         (3700, 900, 350, "04:00"))
        self.assertEqual(g["42.195K"]["fee"], None)               # 這組沒寫費用
        self.assertEqual(g["42.195K"]["time_limit"], 510)          # 8.5 小時
        self.assertEqual(d["signup_url"], "https://www.focusline.com.tw/270228JK/personal")

    def test_skips_ad_tracker_links(self):
        d = bd.parse_detail(self.p["13155"])
        self.assertIsNone(d["signup_url"])                         # 「立即報名」是 doubleclick 廣告連結
        self.assertEqual(d["brochure_url"], "https://scbmarathon.com/")
        self.assertEqual([x["time_limit"] for x in d["groups"]], [360, 210, 120, 30])

    def test_parse_helpers(self):
        self.assertEqual(bd.parse_minutes("3.5小時"), 210)
        self.assertEqual(bd.parse_minutes("120分鐘"), 120)
        self.assertEqual(bd.parse_minutes("5H30M"), 330)
        self.assertIsNone(bd.parse_minutes("依大會規定"))
        self.assertEqual(bd.parse_number("1,500元"), 1500)
        self.assertEqual(bd.parse_number("免費"), 0)
        self.assertIsNone(bd.parse_number("洽主辦單位"))


def race(key, date="2027-01-10", status="open", dists=(), url=None, organizer=None):
    return {"key": key, "date": date, "url": url, "organizer": organizer, "issues": ["沒有報名連結"] if not url else [],
            "registration": {"status": status},
            "distances": [{"label": l, "km": k, "fee": f, "quota": q} for l, k, f, q in dists]}


class TestApply(unittest.TestCase):
    def test_fill_blanks_keep_existing(self):
        cache = {"13155": bd.parse_detail(pages()["13155"])}
        r = race("biji-13155", dists=[("42K", 42.0, None, None), ("21.0975K", 21.0975, 1300, 9800), ("3K", 3.0, None, None)])
        bd.apply_details([r], cache)
        d = {x["label"]: x for x in r["distances"]}
        self.assertEqual((d["42K"]["fee"], d["42K"]["quota"], d["42K"]["time_limit"]), (1500, 4700, 360))  # 42K ≈ 42.195K
        self.assertEqual(d["21.0975K"]["fee"], 1300)          # 跑者廣場已經有 → 不覆蓋（運動筆記寫 1500 是錯的）
        self.assertEqual(d["21.0975K"]["time_limit_text"], "3.5小時")
        self.assertEqual(d["3K"]["start"], "09:30")
        self.assertEqual(r["organizer"], "中華民國路跑協會")
        self.assertEqual(r["url"], "https://scbmarathon.com/")
        self.assertEqual(r["issues"], [])

    def test_pick_order_and_refresh(self):
        races = [race("biji-1", date="2027-03-01"), race("biji-2", date="2026-11-01"),
                 race("biji-3", date="2026-10-20", status="closed"), race("biji-4", date="2026-10-01"),
                 race("2026-12-01-abc", date="2026-12-01")]
        cache = {"1": {"fetched_at": (NOW - dt.timedelta(days=3)).isoformat()}}
        # 比賽日已過、沒有運動筆記編號的不抓；3 天前抓過的不重抓；可報名的排在已截止前面
        self.assertEqual(bd.pick(races, cache, NOW, 10), ["2", "3"])
        cache["1"]["fetched_at"] = (NOW - dt.timedelta(days=15)).isoformat()
        self.assertEqual(bd.pick(races, cache, NOW, 10), ["2", "3", "1"])     # 沒抓過的優先，太久的排後面
        self.assertEqual(bd.pick(races, cache, NOW, 1), ["2"])

    def test_update_cache_survives_errors(self):
        races = [race("biji-13155"), race("biji-999", date="2026-12-01")]
        def fetch(url):
            if "cid=999" in url:
                raise RuntimeError("HTTP 500")
            return pages()["13155"]
        cache = {}
        ok, bad = bd.update_cache(cache, races, NOW, limit=5, delay=0, fetch=fetch)
        self.assertEqual((ok, bad), (1, 1))
        self.assertIn("13155", cache)
        self.assertEqual(cache["13155"]["fetched_at"], "2026-10-10T06:07:00+08:00")


if __name__ == "__main__":
    unittest.main()
