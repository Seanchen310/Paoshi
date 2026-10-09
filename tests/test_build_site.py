import json
import os
import re
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import build_site  # noqa: E402

RACE = {
    "id": "2027-01-10-cb9d8216", "key": "biji-13155", "name": "2027 渣打臺北公益馬拉松",
    "alt_names": ["2027 渣打公益臺北馬拉松"], "date": "2027-01-10", "start_time": "05:00",
    "location": "臺北市中正區總統府前廣場", "address": "台北市中正區重慶南路一段122號", "county": "臺北市",
    "region": "北部", "categories": ["full", "half", "10k", "short"], "organizer": "中華民國路跑協會",
    "distances": [{"label": "42.195K", "km": 42.195, "category": "full", "fee": 1800, "quota": 4700, "quota_shared": False},
                  {"label": "3K", "km": 3.0, "category": "short", "fee": None, "quota": 3000, "quota_shared": False}],
    "registration": {"raw": "8月26日 ~ 10月30日", "start": "2026-09-02", "end": "2026-10-30",
                     "start_at": "2026-09-02T16:00", "end_at": "2026-10-30T16:00", "status": "open", "days_left": 20},
    "url": "https://scbmarathon.com/", "certifications": ["AIMS", "measured"], "flag": None,
    "postponed_from": None, "issues": [],
    "sources": [{"name": "跑者廣場", "url": "http://www.taipeimarathon.org.tw/contest.aspx", "scraped_at": "2026-10-10T06:07:00+08:00"},
                {"name": "運動筆記", "url": "https://running.biji.co/index.php?q=competition&act=info&cid=13155", "scraped_at": "2026-10-10T06:07:00+08:00"}],
}


class TestBuildSite(unittest.TestCase):
    def build(self, races):
        d = tempfile.mkdtemp()
        data = os.path.join(d, "races.json")
        with open(data, "w", encoding="utf-8") as f:
            json.dump({"count": len(races), "races": races}, f, ensure_ascii=False)
        site = os.path.join(d, "site")
        os.makedirs(os.path.join(site, "race", "old-race"))      # 舊網頁應該被清掉
        n = build_site.build(data, site)
        return site, n

    def test_race_page_seo(self):
        site, n = self.build([RACE])
        self.assertEqual(n, 1)
        self.assertFalse(os.path.exists(os.path.join(site, "race", "old-race")))
        with open(os.path.join(site, "race", "biji-13155", "index.html"), encoding="utf-8") as f:
            h = f.read()
        self.assertIn("<title>2027 渣打臺北公益馬拉松 報名資訊｜跑事</title>", h)
        self.assertIn('<link rel="canonical" href="https://paoshi.pages.dev/race/biji-13155/">', h)
        self.assertIn("在臺北市中正區總統府前廣場舉行", h)          # 縣市不重複
        self.assertIn("報名費 NT$1,800 起", h)
        self.assertIn("報名中 · 剩 20 天", h)
        self.assertIn('href="https://scbmarathon.com/"', h)
        ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', h).group(1).replace("<\\/", "</"))
        self.assertEqual(ld["@type"], "SportsEvent")
        self.assertEqual(ld["startDate"], "2027-01-10T05:00:00+08:00")
        self.assertEqual(ld["location"]["address"]["addressRegion"], "臺北市")
        self.assertEqual([o["price"] for o in ld["offers"]], [1800])          # 沒有費用的組別不列
        self.assertEqual(ld["offers"][0]["availability"], "https://schema.org/InStock")

    def test_calendar_files(self):
        site, _ = self.build([RACE])
        d = os.path.join(site, "race", "biji-13155")
        self.assertEqual(sorted(f for f in os.listdir(d) if f.endswith(".ics")), ["deadline.ics", "open.ics", "race.ics"])
        with open(os.path.join(d, "deadline.ics"), encoding="utf-8", newline="") as f:
            ics = f.read()
        self.assertIn("\r\nDTSTART:20261030T080000Z\r\n", ics)              # 10/30 16:00 台灣時間
        self.assertIn("SUMMARY:報名截止：2027 渣打臺北公益馬拉松", ics)
        self.assertEqual(ics.count("BEGIN:VALARM"), 3)                       # 前 3 天、前 1 天、前 3 小時
        with open(os.path.join(site, "_headers"), encoding="utf-8") as f:
            self.assertIn("Content-Type: text/calendar", f.read())

    def test_date_only_deadline_reminds_at_9am(self):
        r = json.loads(json.dumps(RACE))
        r["registration"].update(end_at=None)
        files = build_site.race_ics_files(r, "https://paoshi.pages.dev/race/biji-13155/")
        self.assertIn("DTSTART;VALUE=DATE:20261030", files["deadline.ics"])
        self.assertIn("TRIGGER:-P2DT15H", files["deadline.ics"])               # 3 天前早上 9 點

    def test_sitemap_and_robots(self):
        site, _ = self.build([RACE])
        with open(os.path.join(site, "sitemap.xml"), encoding="utf-8") as f:
            sm = f.read()
        self.assertIn("<loc>https://paoshi.pages.dev/</loc>", sm)
        self.assertIn("<loc>https://paoshi.pages.dev/race/biji-13155/</loc><lastmod>2026-10-10</lastmod>", sm)
        with open(os.path.join(site, "robots.txt"), encoding="utf-8") as f:
            self.assertIn("Sitemap: https://paoshi.pages.dev/sitemap.xml", f.read())

    def test_closed_race_has_no_signup_and_escapes_html(self):
        r = json.loads(json.dumps(RACE))
        r["name"] = "<b>奇怪</b> & 賽名"
        r["registration"].update(status="closed", days_left=None)
        r["postponed_from"] = "2026-12-20"
        site, _ = self.build([r])
        with open(os.path.join(site, "race", "biji-13155", "index.html"), encoding="utf-8") as f:
            h = f.read()
        self.assertNotIn("前往報名", h)
        self.assertIn("查看官方網站", h)
        self.assertIn("已延期（原訂 12/20）", h)
        self.assertIn("&lt;b&gt;奇怪&lt;/b&gt; &amp; 賽名", h)
        self.assertNotIn("<b>奇怪</b>", h)


if __name__ == "__main__":
    unittest.main()
