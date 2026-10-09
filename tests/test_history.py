import copy
import datetime as dt
import gzip
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, ".."))
import history  # noqa: E402

TZ = dt.timezone(dt.timedelta(hours=8))


def race(name, date, cid=None, raw="", end=None, dists=(("42.195K", 2200, 9000),)):
    sources = [{"name": "跑者廣場", "url": "http://www.taipeimarathon.org.tw/contest.aspx"}]
    if cid:
        sources.append({"name": "運動筆記", "url": f"https://running.biji.co/index.php?q=competition&act=info&cid={cid}"})
    return {
        "id": f"{date}-{abs(hash(name)) % 10**8:08d}", "name": name, "date": date, "start_time": "06:30",
        "location": "臺北市政府", "address": None, "organizer": "臺北市政府", "url": "https://x",
        "certifications": ["AIMS"], "postponed_from": None,
        "registration": {"raw": raw, "start": "2026-06-22", "end": end, "start_at": None, "end_at": None,
                         "status": "open", "days_left": 3},
        "distances": [{"label": l, "fee": f, "quota": q} for l, f, q in dists],
        "sources": sources,
    }


class TestDiff(unittest.TestCase):
    TODAY = dt.date(2026, 10, 10)

    def run_diff(self, old, new):
        return history.diff(history.snapshot(old), history.snapshot(new), self.TODAY)

    def test_no_change_no_events(self):
        a = [race("2026 臺北馬拉松", "2026-12-20", cid="13020")]
        b = copy.deepcopy(a)
        b[0]["registration"].update(status="closing_soon", days_left=1)   # 推算出來的欄位不算變化
        self.assertEqual(self.run_diff(a, b), [])

    def test_fee_and_quota_change(self):
        a = [race("2026 臺北馬拉松", "2026-12-20")]
        b = [race("2026 臺北馬拉松", "2026-12-20", dists=(("42.195K", 2400, 9000), ("5K", 600, None)))]
        ev = self.run_diff(a, b)
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["field"], "distances")
        kinds = {(c["label"], c["change"]) for c in ev[0]["changes"]}
        self.assertEqual(kinds, {("42.195K", "fee"), ("5K", "added")})
        self.assertIn("42.195K 報名費 2,200 → 2,400", history.describe(ev[0]))

    def test_filled_in_blanks_are_not_changes(self):
        a = [race("2026 臺北馬拉松", "2026-12-20", cid="13020", dists=(("42.195K", None, None),))]
        a[0]["organizer"] = None
        a[0]["url"] = None
        b = [race("2026 臺北馬拉松", "2026-12-20", cid="13020", dists=(("42.195K", 2200, 9000),))]
        self.assertEqual(self.run_diff(a, b), [])                 # 補上承辦單位、連結、費用、名額
        c = [race("2026 臺北馬拉松", "2026-12-20", cid="13020", dists=(("42.195K", 2400, 9000),))]
        c[0]["organizer"] = "別的單位"
        ev = self.run_diff(b, c)
        self.assertEqual(sorted(e.get("field") for e in ev), ["distances", "organizer"])   # 真的改了才記

    def test_rename_same_biji_cid_is_change_not_add_remove(self):
        a = [race("2026 臺北馬拉松", "2026-12-20", cid="13020")]
        b = [race("2026 臺北馬拉松 TAIPEI MARATHON", "2026-12-20", cid="13020")]
        ev = self.run_diff(a, b)
        self.assertEqual([(e["type"], e.get("field")) for e in ev], [("changed", "name")])

    def test_early_close(self):
        a = [race("2026 臺北馬拉松", "2026-12-20", raw="~ 10月30日", end="2026-10-30")]
        b = [race("2026 臺北馬拉松", "2026-12-20", raw="已截止", end="2026-10-30")]
        ev = [e for e in self.run_diff(a, b) if e["type"] == "early_close"]
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["days_early"], 20)
        self.assertIn("提前 20 天", history.describe(ev[0]))

    def test_removed_before_race_vs_ended(self):
        a = [race("已比完", "2026-10-09"), race("消失的", "2026-11-15")]
        ev = {e["name"]: e["type"] for e in self.run_diff(a, [])}
        self.assertEqual(ev, {"已比完": "ended", "消失的": "removed_before_race"})

    def test_added(self):
        ev = self.run_diff([], [race("新比賽", "2027-01-10")])
        self.assertEqual(ev[0]["type"], "added")


class TestUpdate(unittest.TestCase):
    def test_baseline_then_changes(self):
        with tempfile.TemporaryDirectory() as d:
            t1 = dt.datetime(2026, 10, 10, 6, 7, tzinfo=TZ)
            a = [race("2026 臺北馬拉松", "2026-12-20", cid="13020")]
            self.assertEqual(history.update(d, a, t1), [])          # 第一次只建立基準
            self.assertEqual(len(os.listdir(os.path.join(d, "snapshots"))), 1)

            t2 = dt.datetime(2026, 10, 10, 18, 7, tzinfo=TZ)
            self.assertEqual(history.update(d, a, t2), [])          # 沒變化：不存快照
            self.assertEqual(len(os.listdir(os.path.join(d, "snapshots"))), 1)

            t3 = dt.datetime(2026, 10, 11, 6, 7, tzinfo=TZ)
            b = [race("2026 臺北馬拉松", "2026-12-20", cid="13020", dists=(("42.195K", 2400, 9000),))]
            ev = history.update(d, b, t3)
            self.assertEqual(len(ev), 1)
            snaps = sorted(os.listdir(os.path.join(d, "snapshots")))
            self.assertEqual(len(snaps), 2)
            with gzip.open(os.path.join(d, "snapshots", snaps[-1]), "rt", encoding="utf-8") as f:
                self.assertEqual(json.load(f)["biji-13020"]["distances"]["42.195K"], [2400, 9000])

            with open(os.path.join(d, "runs.jsonl"), encoding="utf-8") as f:
                runs = [json.loads(x) for x in f]
            self.assertEqual([r["changes"] for r in runs], [0, 0, 1])
            self.assertTrue(runs[0]["baseline"])
            with open(os.path.join(d, "CHANGES.md"), encoding="utf-8") as f:
                md = f.read()
            self.assertIn("## 2026-10-11 06:07", md)
            self.assertIn("報名費 2,200 → 2,400", md)


if __name__ == "__main__":
    unittest.main()
