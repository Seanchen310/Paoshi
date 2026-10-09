import datetime as dt
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import biji  # noqa: E402

TODAY = dt.date(2026, 10, 9)


def load():
    with open(os.path.join(HERE, "fixture_biji.html"), encoding="utf-8") as f:
        return biji.parse_html(f.read())


class TestParseHtml(unittest.TestCase):
    def setUp(self):
        self.rows = load()
        self.by = {r["cid"]: r for r in self.rows}

    def test_ad_duplicates_removed(self):
        # 10 列裡有 2 列是廣告重複
        self.assertEqual(len(self.rows), 8)
        self.assertEqual(len({r["cid"] for r in self.rows}), 8)

    def test_fields(self):
        r = self.by["12966"]
        self.assertEqual(r["name"], "2026 Maokong 貓空 Night Trail")
        self.assertEqual(r["place"], "臺北市")
        self.assertEqual(r["events"], ["65K", "42K", "40K", "15K", "9K", "6K"])  # 註解掉的 div 不算
        self.assertEqual(r["status"], "已截止報名")
        self.assertIn("act=info&cid=12966", r["href"])

    def test_certs(self):
        self.assertEqual(self.by["13155"]["certs"], ["aims.png", "ctaa.png"])


class TestNormalize(unittest.TestCase):
    def setUp(self):
        self.races = biji.normalize(load(), TODAY, "2026-10-09T11:30:00+08:00")
        self.by = {r["name"]: r for r in self.races}

    def test_overseas_skipped(self):
        self.assertNotIn("2026 成都馬拉松", self.by)
        self.assertEqual(len(self.races), 7)

    def test_calendar_link(self):
        r = self.by["2027 國家地理路跑-RUN FOR EARTH"]  # 廣告列，日期寫法不同
        self.assertEqual(r["date"], "2027-03-14")
        self.assertEqual(r["address"], "台北市中正區重慶南路一段122號")
        self.assertEqual((r["county"], r["region"]), ("臺北市", "北部"))
        reg = r["registration"]
        self.assertEqual((reg["start"], reg["end"]), ("2026-10-01", "2027-01-07"))
        self.assertEqual((reg["start_at"], reg["end_at"]), ("2026-10-01T12:00", "2027-01-07T23:59"))
        self.assertEqual(reg["status"], "open")
        self.assertEqual(reg["days_left"], 90)

    def test_registration_status(self):
        st = lambda n: self.by[n]["registration"]["status"]  # noqa: E731
        self.assertEqual(st("2026 Maokong 貓空 Night Trail"), "closed")
        self.assertEqual(st("最強市民飆5K－新北市5000公尺挑戰賽 十月場"), "upcoming")
        self.assertEqual(st("2027 富邦人壽高雄馬拉松 DAY 1"), "unknown")
        self.assertEqual(st("2027 渣打公益臺北馬拉松"), "open")

    def test_postponed(self):
        r = self.by["2026 華山論劍湖超級馬拉松"]
        self.assertEqual((r["date"], r["postponed_from"]), ("2026-10-04", "2026-09-19"))
        self.assertEqual(r["issues"], [])
        bad = self.by["2027新竹縣尖石鄉鎮西堡王者之路~光明(火)超級馬拉松"]
        self.assertTrue(any("延期說明" in i for i in bad["issues"]))

    def test_certs_and_source(self):
        r = self.by["2027 渣打公益臺北馬拉松"]
        self.assertEqual(r["certifications"], ["AIMS", "measured"])
        self.assertEqual(r["sources"][0]["url"],
                         "https://running.biji.co/index.php?q=competition&act=info&cid=13155")

    def test_midnight_deadline(self):
        # 截止時間 00:00 → 實際上前一天晚上就截止
        self.assertEqual(biji.last_day(dt.datetime(2026, 10, 1, 0, 0)), dt.date(2026, 9, 30))
        self.assertEqual(biji.last_day(dt.datetime(2026, 10, 1, 23, 59)), dt.date(2026, 10, 1))


if __name__ == "__main__":
    unittest.main()
