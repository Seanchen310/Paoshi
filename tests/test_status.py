"""報名狀態規則（2026-10-10 決定）。網站 site/app.js 的 liveStatus() 是同一套規則。"""
import datetime as dt
import os
import sys
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import scraper as s  # noqa: E402

TZ = s.TZ
NOW = dt.datetime(2026, 10, 10, 9, 0, tzinfo=TZ)          # 10/10 早上 9 點
FRESH = dt.datetime(2026, 10, 10, 6, 7, tzinfo=TZ)        # 今天 06:07 抓的資料


def reg(raw="x", start=None, end=None, start_at=None, end_at=None):
    return {"raw": raw, "start": start, "end": end, "start_at": start_at, "end_at": end_at}


def st(r, now=NOW, scraped=FRESH):
    return s.live_status(r, now, scraped)


class TestLiveStatus(unittest.TestCase):
    def test_source_says_full_or_closed(self):
        self.assertEqual(st(reg("額滿", end="2026-10-30"))[0], "full")
        self.assertEqual(st(reg("已截止", end="2026-10-30"))[0], "closed")
        self.assertEqual(st(reg("已截止報名"))[0], "closed")

    def test_no_info_is_unknown(self):
        self.assertEqual(st(reg(""))[:3], ("unknown", None, "no_info"))

    def test_exact_deadline_passed(self):
        r = reg(start="2026-09-01", end="2026-10-10", end_at="2026-10-10T08:00")
        self.assertEqual(st(r)[0], "closed")

    def test_date_only_deadline(self):
        self.assertEqual(st(reg(start="2026-09-01", end="2026-10-09"))[0], "closed")
        # 只知道日期、今天就是截止日 → 待確認，不假設當晚還報得到
        self.assertEqual(st(reg(start="2026-09-01", end="2026-10-10"))[:3], ("unknown", None, "deadline_today"))
        # 只知道日期 → 報名中但不倒數
        self.assertEqual(st(reg(start="2026-09-01", end="2026-10-30"))[:2], ("open", None))

    def test_exact_deadline_countdown_and_72h(self):
        far = reg(start="2026-09-01", end="2026-10-30", end_at="2026-10-30T16:00")
        self.assertEqual(st(far)[:2], ("open", 20))
        soon = reg(start="2026-09-01", end="2026-10-13", end_at="2026-10-13T09:00")   # 剛好 72 小時
        self.assertEqual(st(soon)[:2], ("closing_soon", 3))
        later = reg(start="2026-09-01", end="2026-10-13", end_at="2026-10-13T09:01")  # 72 小時又 1 分
        self.assertEqual(st(later)[0], "open")
        today_late = reg(start="2026-09-01", end="2026-10-10", end_at="2026-10-10T23:59")
        self.assertEqual(st(today_late)[:2], ("closing_soon", 0))   # 有確切時間，當天還能報

    def test_upcoming_and_should_have_opened(self):
        self.assertEqual(st(reg(start="2026-10-12", end="2026-10-18"))[0], "upcoming")
        self.assertEqual(st(reg(start_at="2026-10-10T12:00", start="2026-10-10", end="2026-10-30"))[0], "upcoming")
        # 開報時間已到，但資料是開報前抓的 → 待確認，等下次抓取
        r = reg(start_at="2026-10-10T08:00", start="2026-10-10", end="2026-10-30")
        self.assertEqual(st(r)[:3], ("unknown", None, "should_have_opened"))
        later_scrape = dt.datetime(2026, 10, 10, 8, 30, tzinfo=TZ)
        self.assertEqual(st(r, scraped=later_scrape)[0], "open")

    def test_stale_data(self):
        r = reg(start="2026-09-01", end="2026-12-30")
        seven = NOW - dt.timedelta(days=7)
        self.assertEqual(st(r, scraped=seven)[0], "open")             # 剛好 7 天不降級
        eight = NOW - dt.timedelta(days=7, minutes=1)
        self.assertEqual(st(r, scraped=eight)[:3], ("unknown", None, "stale"))

    def test_half_marathon_range(self):
        self.assertEqual(s.classify("21.0975K", 21.0975), "half")
        self.assertEqual(s.classify("22K", 22.0), "half")
        self.assertEqual(s.classify("23K", 23.0), "long")
        self.assertEqual(s.classify("25K", 25.0), "long")


if __name__ == "__main__":
    unittest.main()
