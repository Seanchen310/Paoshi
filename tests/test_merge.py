import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, HERE)
import biji  # noqa: E402
import merge  # noqa: E402
import run  # noqa: E402
import scraper  # noqa: E402
from test_biji import load as load_biji  # noqa: E402
from test_scraper import RAW, TODAY  # noqa: E402


class TestSimilarity(unittest.TestCase):
    def test_same_race_different_names(self):
        # 2026/10/09 兩個網站實際的寫法
        same = [
            ("2027 渣打臺北公益馬拉松", "2027 渣打公益臺北馬拉松"),
            ("2026 第14屆開廣飛跑盃超級馬拉松", "2026 CTAU超馬系列賽 - 第二站 開廣飛跑盃超級馬拉松"),
            ("2026 國聚慵懶跑者聚樂部", "慵懶跑者聚樂部-COZY RUNNER CLUB"),
            ("2026 第十ㄧ屆馬祖馬拉松", "2026馬祖馬拉松"),
        ]
        for a, b in same:
            self.assertGreaterEqual(merge.similarity(a, b), 0.5, (a, b))

    def test_different_races(self):
        # 同一天、名字都有「全國馬拉松」，但是不同比賽
        self.assertLess(merge.similarity("2026 北港媽祖盃全國馬拉松", "2026年東石全國馬拉松"), 0.3)
        self.assertLess(merge.similarity("2027 柚花追香半程馬拉松-麻豆場", "2027府城英雄馬拉松"), 0.3)

    def test_common_run(self):
        self.assertEqual(merge.common_run("2027 臺灣集集半程國際馬拉松", "2027集集濁水溪半程國際馬拉松"), 2)


def race(name, date, county, km=(), reg_end=None, raw=""):
    return {"name": name, "alt_names": [], "date": date, "county": county,
            "distances": [{"km": k} for k in km], "categories": [], "address": None,
            "certifications": [], "postponed_from": None, "issues": [],
            "registration": {"raw": raw, "start": None, "end": reg_end, "start_at": None,
                             "end_at": None, "status": "unknown", "days_left": None},
            "sources": [{"name": "x"}]}


class TestMatch(unittest.TestCase):
    def test_county_must_agree_unless_name_identical(self):
        a = [race("2026 北港媽祖盃全國馬拉松", "2026-11-21", "雲林縣"),
             race("2026 八百壯士系列--制霸極西超馬賽", "2026-11-01", "臺南市")]
        b = [race("2026年東石全國馬拉松", "2026-11-21", "嘉義縣"),
             race("2026八百壯士系列--制霸極西超馬賽", "2026-11-01", "嘉義縣")]
        self.assertEqual(merge.match(a, b), [(1, 1)])

    def test_one_to_one_best_first(self):
        # 同一天同縣市兩場名字很像的，各自配到最像的那場
        a = [race("2026 臺灣極限超級鐵人賽", "2026-11-08", "臺南市"),
             race("2026 臺灣極限超級鐵人推廣路跑", "2026-11-08", "臺南市", km=(10,))]
        b = [race("2026台灣極限超級鐵人推廣路跑", "2026-11-08", "臺南市", km=(10,))]
        self.assertEqual(merge.match(a, b), [(1, 0)])

    def test_postponed_date_matches(self):
        a = [race("2026 POCARI SWEAT RUN 寶礦力路跑", "2026-10-17", "臺北市")]
        b = [race("2026 POCARI SWEAT RUN寶礦力路跑", "2026-10-18", "臺北市")]
        b[0]["postponed_from"] = "2026-10-17"
        self.assertEqual(merge.match(a, b), [(0, 0)])


class TestMerge(unittest.TestCase):
    def setUp(self):
        pz = scraper.normalize(RAW, TODAY, "t")
        bj = biji.normalize(load_biji(), TODAY, "t")
        self.races = merge.merge(pz, bj, TODAY)
        self.by = {r["name"]: r for r in self.races}

    def test_matched_fields(self):
        r = self.by["2027 渣打臺北公益馬拉松"]
        self.assertEqual(r["alt_names"], ["2027 渣打公益臺北馬拉松"])
        self.assertEqual([s["name"] for s in r["sources"]], ["跑者廣場", "運動筆記"])
        self.assertEqual(r["url"], "https://scbmarathon.com/index.php")      # 跑者廣場的報名連結
        self.assertEqual(r["distances"][1]["quota"], 9800)                     # 跑者廣場的名額
        self.assertEqual(r["address"], "台北市中正區重慶南路一段122號")         # 運動筆記的地址
        self.assertEqual(r["registration"]["end_at"], "2026-10-30T16:00")     # 運動筆記的報名時間（下午 4 點截止）
        self.assertEqual(r["certifications"], ["AIMS", "measured"])
        self.assertTrue(any("報名開始日兩邊不同" in i for i in r["issues"]))

    def test_counts_and_order(self):
        both = [r for r in self.races if len(r["sources"]) == 2]
        self.assertEqual(len(both), 3)  # 貓空、最強市民十月場、渣打
        self.assertEqual(len(self.races), 15 + 7 - 3)
        dates = [r["date"] or "9999" for r in self.races]
        self.assertEqual(dates, sorted(dates))
        ids = [r["id"] for r in self.races]
        self.assertEqual(len(ids), len(set(ids)))

    def test_conflicting_deadline_uses_later(self):
        a = scraper.normalize(RAW, TODAY, "t")
        a = [r for r in a if r["name"] == "2026 宜蘭冬山河超級馬拉松"]   # 跑者廣場：~ 10月19日
        b = [dict(race("2026 宜蘭冬山河超級馬拉松", "2026-11-20", "宜蘭縣"), address="x", id="b")]
        b[0]["registration"].update(start="2026-04-23", end="2026-09-19", end_at="2026-09-19T23:59",
                                    status="closed")
        r = merge.merge(a, b, TODAY)[0]
        self.assertEqual(r["registration"]["end"], "2026-10-19")
        self.assertEqual(r["registration"]["status"], "open")
        self.assertTrue(any("截止日兩邊不同" in i for i in r["issues"]))

    def test_marked_closed_on_one_site(self):
        a = [r for r in scraper.normalize(RAW, TODAY, "t") if r["name"] == "2026 Maokong 貓空 Night Trail"]
        b = [dict(race("2026 Maokong 貓空 Night Trail", "2026-10-09", "臺北市"), address="x", id="b")]
        b[0]["registration"].update(start="2026-03-01", end="2026-10-31", status="open")
        r = merge.merge(a[:1], b, TODAY)[0]
        self.assertEqual(r["registration"]["status"], "closed")
        self.assertTrue(any("額滿" in i for i in r["issues"]))


class TestTrail(unittest.TestCase):
    def test_tag_trail(self):
        names = ["2026 Maokong 貓空 Night Trail", "2027 SUPERACE 野馬越野系列賽冬嶺野馬",
                 "南庄山水悠遊行 2026-山水路跑賽", "2026 陽明山超級馬拉松"]
        rs = [dict(race(n, "2026-10-09", "臺北市"), categories=["10k"]) for n in names]
        rs[2]["alt_names"] = ["2026 南庄山水悠遊行 — 山水路跑賽 × 慢城爬坡(觀賞)賽"]
        scraper.tag_trail(rs)
        self.assertEqual([("trail" in r["categories"]) for r in rs], [True, True, False, False])
        self.assertEqual(rs[0]["categories"], ["10k", "trail"])


class TestCli(unittest.TestCase):
    def test_end_to_end(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rc = run.main(["--html", os.path.join(HERE, "fixture.html"),
                           "--biji-html", os.path.join(HERE, "fixture_biji.html"),
                           "--out", d, "--today", "2026-10-09"])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(os.path.join(d, "races.json")))
            with open(os.path.join(d, "races.csv"), encoding="utf-8-sig") as f:
                lines = f.read().splitlines()
            self.assertEqual(lines[0].split(",")[-2:], ["來源", "資料問題"])
            self.assertGreater(len(lines), 8)

    def test_missing_list_fails(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            empty = os.path.join(d, "empty.html")
            with open(empty, "w", encoding="utf-8") as f:
                f.write("<html></html>")
            rc = run.main(["--html", os.path.join(HERE, "fixture.html"), "--biji-html", empty,
                           "--out", d, "--today", "2026-10-09"])
            self.assertEqual(rc, 1)
            self.assertFalse(os.path.exists(os.path.join(d, "races.json")))


if __name__ == "__main__":
    unittest.main()
