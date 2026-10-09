import datetime as dt
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import scraper as s  # noqa: E402

TODAY = dt.date(2026, 10, 9)

# 從跑者廣場 2026/10/09 頁面實際取得的原始列（挑邊界案例）
RAW = [
    ["10月", "", "2026 Maokong 貓空 Night Trail", "https://venturetreks.asia/maokong/", "", "10/09 五", "臺北市文山區煎茶院", "65K§|40K§", "Venture Treks", "已截止", ""],
    ["", "", "最強市民飆5K－新北市5000公尺挑戰賽 十月場", "http://esg.soonest.com/Home/Index", "", "10/21 三 18:30", "新北市板橋區第一運動場", "5K§0", "捷迅股份有限公司", "10月12日 ~ 10月18日", ""],
    ["", "", "2026 南投馬11th-草鞋墩馬拉松", "https://x", "", "10/25 日 06:10", "南投縣草屯鎮九九峰氦氣球園區停車場", "42.195K§|22k§|10k§|5k§", "南投縣馬拉松協會", "已截止", ""],
    ["11月", "", "2026 冬山河馬拉松", "https://sportaiwan.com/a", "", "11/14 六 06:30", "宜蘭縣冬山鄉冬山火車站", "42.195K§|21K§|10K§|5K§", "影流文創 SporTaiwan", "~ 10月10日(最後二天)", ""],
    ["", "", "2026 宜蘭冬山河超級馬拉松", "https://ctau", "course_ok.png", "11/20 五 21:00", "宜蘭縣五結鄉親水公園", "100miles§|100K§|50miles§|50K§|44K§|22K§|11K§", "社團法人中華民國超級馬拉松運動協會", "~ 10月19日", ""],
    ["", "", "2026 國聚慵懶跑者聚樂部", "", "", "11/15 日", "臺中市西屯區中央球場", "10K§|5K§", "", "", ""],
    ["12月", "", "2026 第二屆核泰皮拉提斯馬拉松", "https://f", "", "12/05 六 06:00", "臺中市清水區頂湳玉聖寺", "51K§<br/>限額：20|42.2K§<br/>限額： 200|5.4Kx4§<br/>限額： 25隊", "核立子身心技法創研社", "6月01日 ~ 11月07日", ""],
    ["", "", "2026 臺北馬拉松", "https://www.taipeicitymarathon.com/", "aims_logo.gif", "12/20 日 06:30", "臺北市信義區臺北市政府", "42.195K§2200<br/>限額：9000|21.0975K§ 1600<br/>限額： 19000", "臺北市政府", "6月22日 ~", ""],
    ["", "new.gif", "2026 高雄捷運蜜柑站長耶誕公益主題路跑", "https://j", "", "12/26 六 07:00", "高雄市鼓山區棧貳庫廣場", "10K§1299<br/>限額：1500|4K§ 988<br/>限額： 1000", "高雄捷運股份有限公司", "~ 10月31日", ""],
    ["1月", "", "2027 渣打臺北公益馬拉松", "https://scbmarathon.com/index.php", "aims_logo.gif", "01/10 日 05:00", "臺北市中正區總統府前廣場", "42.195K§<br/>限額：4700|21.0975K§<br/>限額： 9800|12K§<br/>限額： 9000|3K§<br/>限額： 3000", "中華民國路跑協會", "8月26日 ~ 10月30日", ""],
    ["", "", "2026 陽明山超級馬拉松", "https://ctau2", "", "01/23 六 06:00", "臺北市士林區至善國中", "63K§|50K§|42.195K§|21K§|10K§|5K§", "社團法人中華民國超級馬拉松運動協會", "~ 12月22日", ""],
    ["3月", "", "2027 LAVA 玩賽樂園", "https://b", "", "03/13 六 07:00", "臺東縣臺東市森林公園活水湖", "1.9K+90K+21.1K§|1.5K+40K+10K§", "LAVA 鐵人公司", "4月01日 ~ 1月10日", ""],
    ["", "", "2027 柚花追香半程馬拉松-瑞穗星光夜跑", "https://b2", "", "03/27 六 15:30", "花蓮縣瑞穗鄉瑞穗國小", "21K§1190<br/>限額：1000", "瑞穗鄉農會", "8月20日 ~ 8月12日", ""],
    ["", "", "2027 七股生態馬拉松", "", "", "04/11 日 06:00", "七股正王府雷安宮  台南市七股區十份里53之2號", "42.195K§|21.0975K§|10K§|5K§", "府城國際超級馬拉松協會", "", ""],
    ["4月", "update.png", "2027 中山香香生活節", "", "", "04/03 六", "", "", "", "", ""],
]


class TestParseHtml(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(HERE, "fixture.html"), encoding="utf-8") as f:
            self.rows = s.parse_html(f.read())

    def test_rows_and_header_skipped(self):
        self.assertEqual(len(self.rows), 4)

    def test_fields(self):
        r = self.rows[1]
        self.assertEqual(r[2], "2026 第14屆開廣飛跑盃超級馬拉松")
        self.assertEqual(r[4], "course_ok.png")
        self.assertEqual(r[5], "10/10 六 06:00")
        self.assertEqual(r[7], "50K§|42.195K§|6H§|5H接力§")
        self.assertEqual(r[8], "社團法人中華民國超級馬拉松運動協會")

    def test_fee_title_and_flag(self):
        r = self.rows[2]
        self.assertEqual(r[1], "update.png")
        self.assertTrue(r[7].startswith("42.195K§1400<br/>限額：1500"))
        self.assertEqual(r[9], "6月10日 ~ 10月15日(最後一週)")

    def test_unescaped_br_in_title(self):
        html = ('<table id="GridView1"><tr><td></td><td>X</td><td></td><td>10/18 日</td><td>臺北市</td>'
                '<td><button title="費用：900<br/>限額：50">10K</button></td><td>O</td><td></td></tr></table>')
        rows = s.parse_html(html)
        self.assertEqual(rows[0][7], "10K§900<br/>限額：50")

    def test_no_link_row(self):
        r = self.rows[3]
        self.assertEqual(r[2], "臺南保生盃全國馬拉松")
        self.assertEqual(r[3], "")
        self.assertEqual(r[7], "")


class TestNormalize(unittest.TestCase):
    def setUp(self):
        races = s.normalize(RAW, TODAY, "2026-10-09T11:30:00+08:00")
        self.by = {r["name"]: r for r in races}
        self.races = races

    def test_year_rollover(self):
        self.assertEqual(self.by["2026 Maokong 貓空 Night Trail"]["date"], "2026-10-09")
        self.assertEqual(self.by["2027 渣打臺北公益馬拉松"]["date"], "2027-01-10")
        self.assertEqual(self.by["2027 LAVA 玩賽樂園"]["date"], "2027-03-13")

    def test_weekday_consistent(self):
        for r in self.races:
            self.assertFalse(any("星期不符" in i for i in r["issues"]), r["name"])

    def test_distance_categories(self):
        d = {x["label"]: x for x in self.by["2026 宜蘭冬山河超級馬拉松"]["distances"]}
        self.assertEqual(d["100miles"]["category"], "ultra")
        self.assertAlmostEqual(d["100miles"]["km"], 160.9)
        self.assertEqual(d["22K"]["category"], "half")
        self.assertEqual(d["11K"]["category"], "10k")
        labels = [x["label"] for x in self.by["2026 南投馬11th-草鞋墩馬拉松"]["distances"]]
        self.assertEqual(labels, ["42.195K", "22K", "10K", "5K"])
        cats = self.by["2027 LAVA 玩賽樂園"]["categories"]
        self.assertEqual(cats, ["triathlon"])
        pil = {x["label"]: x for x in self.by["2026 第二屆核泰皮拉提斯馬拉松"]["distances"]}
        self.assertEqual(pil["42.2K"]["category"], "full")
        self.assertEqual(pil["5.4Kx4"]["category"], "relay")

    def test_fee_quota(self):
        d = self.by["2026 臺北馬拉松"]["distances"]
        self.assertEqual((d[0]["fee"], d[0]["quota"]), (2200, 9000))
        self.assertEqual((d[1]["fee"], d[1]["quota"]), (1600, 19000))
        d = self.by["2027 渣打臺北公益馬拉松"]["distances"]
        self.assertEqual((d[0]["fee"], d[0]["quota"]), (None, 4700))
        free = self.by["最強市民飆5K－新北市5000公尺挑戰賽 十月場"]["distances"][0]
        self.assertEqual(free["fee"], 0)

    def test_registration_status(self):
        st = lambda n: self.by[n]["registration"]["status"]  # noqa: E731
        self.assertEqual(st("2026 Maokong 貓空 Night Trail"), "closed")
        self.assertEqual(st("最強市民飆5K－新北市5000公尺挑戰賽 十月場"), "upcoming")
        self.assertEqual(st("2026 冬山河馬拉松"), "closing_soon")
        self.assertEqual(self.by["2026 冬山河馬拉松"]["registration"]["days_left"], 1)
        self.assertEqual(st("2026 宜蘭冬山河超級馬拉松"), "open")
        self.assertEqual(st("2026 臺北馬拉松"), "open")
        self.assertIsNone(self.by["2026 臺北馬拉松"]["registration"]["days_left"])
        self.assertEqual(st("2026 國聚慵懶跑者聚樂部"), "unknown")
        self.assertEqual(self.by["2027 渣打臺北公益馬拉松"]["registration"]["end"], "2026-10-30")
        self.assertEqual(self.by["2026 陽明山超級馬拉松"]["registration"]["end"], "2026-12-22")

    def test_cross_year_registration(self):
        reg = self.by["2027 LAVA 玩賽樂園"]["registration"]
        self.assertEqual((reg["start"], reg["end"]), ("2026-04-01", "2027-01-10"))
        self.assertEqual(reg["status"], "open")

    def test_issues(self):
        self.assertTrue(any("賽名年份" in i for i in self.by["2026 陽明山超級馬拉松"]["issues"]))
        self.assertTrue(any("顛倒" in i for i in self.by["2027 柚花追香半程馬拉松-瑞穗星光夜跑"]["issues"]))
        self.assertIn("沒有報名連結", self.by["2026 國聚慵懶跑者聚樂部"]["issues"])
        empty = self.by["2027 中山香香生活節"]["issues"]
        self.assertIn("沒有距離資料", empty)
        self.assertIn("沒有地點", empty)
        self.assertEqual(self.by["2026 臺北馬拉松"]["issues"], [])

    def test_county_region_cert_flag(self):
        r = self.by["2027 七股生態馬拉松"]
        self.assertEqual((r["county"], r["region"]), ("臺南市", "南部"))
        self.assertEqual(self.by["2026 臺北馬拉松"]["certifications"], ["AIMS"])
        self.assertEqual(self.by["2026 宜蘭冬山河超級馬拉松"]["certifications"], ["measured"])
        self.assertEqual(self.by["2026 高雄捷運蜜柑站長耶誕公益主題路跑"]["flag"], "new")

    def test_ids_unique(self):
        ids = [r["id"] for r in self.races]
        self.assertEqual(len(ids), len(set(ids)))


class TestCli(unittest.TestCase):
    def test_end_to_end(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            rc = s.main(["--html", os.path.join(HERE, "fixture.html"), "--out", d, "--today", "2026-10-09"])
            self.assertEqual(rc, 0)
            self.assertTrue(os.path.exists(os.path.join(d, "races.json")))
            with open(os.path.join(d, "races.csv"), encoding="utf-8-sig") as f:
                lines = f.read().splitlines()
            self.assertEqual(len(lines), 5)


if __name__ == "__main__":
    unittest.main()
