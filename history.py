"""
跑事｜歷史紀錄

每次抓取後，和上一次的資料比對，把「來源真正改了什麼」記下來。
這是跑事要累積、別人抄不走的資產（例如：哪場比賽多快額滿、何時漲價）。

只比對來源寫的事實（賽名、日期、費用、名額、報名起訖、來源標示的已截止…），
不比對依今天日期推算的東西（剩幾天、報名中／快截止），所以不會每天出現假變化。

history/ 資料夾裡：
  latest.json            上一次的精簡快照（下一次比對用）
  snapshots/*.json.gz    有變化時才存的完整快照（壓縮）
  changes.jsonl          每一筆變化一行（給程式分析）
  runs.jsonl             每次執行一行：時間、場數、變化數（算排程成功率）
  CHANGES.md             給人看的變化紀錄（最新的在最上面）
"""

import datetime as dt
import gzip
import json
import os

# 拿來比對的欄位（中文名稱用在 CHANGES.md）
FIELDS = {
    "name": "賽名", "date": "比賽日", "start_time": "起跑時間", "location": "地點", "address": "地址",
    "organizer": "承辦單位", "url": "報名連結", "certifications": "認證", "postponed_from": "原訂日期",
    "reg_raw": "報名欄文字", "reg_start": "開報日", "reg_end": "截止日",
    "reg_start_at": "開報時間", "reg_end_at": "截止時間", "source_closed": "來源標示已截止",
    "distances": "組別",
}
CLOSED_WORDS = ("已截止", "額滿")


def race_key(r):
    """同一場比賽的編號：有運動筆記的就用它的賽事編號（改名、改期也不會變），否則用 id。"""
    for s in r.get("sources", []):
        if s.get("name") == "運動筆記" and "cid=" in (s.get("url") or ""):
            return "biji-" + s["url"].split("cid=")[1].split("&")[0]
    return r["id"]


def compact(r):
    reg = r["registration"]
    return {
        "id": r["id"], "name": r["name"], "date": r["date"], "start_time": r.get("start_time"),
        "location": r.get("location"), "address": r.get("address"), "organizer": r.get("organizer"),
        "url": r.get("url"), "certifications": sorted(r.get("certifications") or []),
        "postponed_from": r.get("postponed_from"),
        "reg_raw": reg.get("raw") or "", "reg_start": reg.get("start"), "reg_end": reg.get("end"),
        "reg_start_at": reg.get("start_at"), "reg_end_at": reg.get("end_at"),
        "source_closed": any(w in (reg.get("raw") or "") for w in CLOSED_WORDS),
        "distances": {d["label"]: [d.get("fee"), d.get("quota")] for d in r["distances"]},
        "sources": sorted(s["name"] for s in r.get("sources", [])),
    }


def snapshot(races):
    return {race_key(r): compact(r) for r in races}


def _dist_changes(old, new):
    """組別的差異，例如 42.195K 報名費 2200 → 2400、新增 5K 組。"""
    out = []
    for label in sorted(set(old) | set(new)):
        if label not in old:
            out.append({"label": label, "change": "added", "new": new[label]})
        elif label not in new:
            out.append({"label": label, "change": "removed", "old": old[label]})
        else:
            (of, oq), (nf, nq) = old[label], new[label]
            # 從「沒有」變成有值＝補上資料（例如從詳情頁補到報名費），不算變化；只記真的改了
            if of != nf and of is not None:
                out.append({"label": label, "change": "fee", "old": of, "new": nf})
            if oq != nq and oq is not None:
                out.append({"label": label, "change": "quota", "old": oq, "new": nq})
    return out


def diff(old, new, today):
    """回傳變化清單；today 是台灣日期（date）。"""
    t = today.isoformat()
    events = []
    for k in sorted(set(new) - set(old)):
        events.append({"type": "added", "key": k, "name": new[k]["name"], "date": new[k]["date"]})
    for k in sorted(set(old) - set(new)):
        o = old[k]
        # 比賽日過了自然消失 vs 比賽日前就消失（很可能是取消或主辦撤下）
        kind = "ended" if (o["date"] or "") < t else "removed_before_race"
        events.append({"type": kind, "key": k, "name": o["name"], "date": o["date"]})
    for k in sorted(set(old) & set(new)):
        o, n = old[k], new[k]
        for f in FIELDS:
            if f == "distances":
                dc = _dist_changes(o["distances"], n["distances"])
                if dc:
                    events.append({"type": "changed", "key": k, "name": n["name"], "date": n["date"],
                                   "field": f, "changes": dc})
            elif o.get(f) != n.get(f):
                events.append({"type": "changed", "key": k, "name": n["name"], "date": n["date"],
                               "field": f, "old": o.get(f), "new": n.get(f)})
        # 截止日還沒到，來源就標成已截止／額滿 → 提前截止
        if n["source_closed"] and not o["source_closed"] and n["reg_end"] and n["reg_end"] > t:
            days = (dt.date.fromisoformat(n["reg_end"]) - today).days
            events.append({"type": "early_close", "key": k, "name": n["name"], "date": n["date"],
                           "reg_end": n["reg_end"], "days_early": days, "raw": n["reg_raw"]})
    return events

# ---------------------------------------------------------------
# 給人看的文字
# ---------------------------------------------------------------

def _fmt(v):
    if v is None or v == "":
        return "（無）"
    if isinstance(v, bool):
        return "是" if v else "否"
    if isinstance(v, list):
        return "、".join(map(str, v)) or "（無）"
    if isinstance(v, int):
        return f"{v:,}"
    return str(v)


def describe(e):
    head = f"**{e['name']}**（{e.get('date') or '日期未定'}）"
    t = e["type"]
    if t == "added":
        return f"新增 {head}"
    if t == "ended":
        return f"比賽日已過，移出列表：{head}"
    if t == "removed_before_race":
        return f"⚠️ 比賽日前就從來源消失（可能取消）：{head}"
    if t == "early_close":
        return f"🔔 提前截止：{head}，原訂 {e['reg_end']} 截止，提前 {e['days_early']} 天（來源寫「{e['raw']}」）"
    if e["field"] == "distances":
        parts = []
        for c in e["changes"]:
            if c["change"] == "added":
                parts.append(f"新增 {c['label']} 組")
            elif c["change"] == "removed":
                parts.append(f"取消 {c['label']} 組")
            elif c["change"] == "fee":
                parts.append(f"{c['label']} 報名費 {_fmt(c['old'])} → {_fmt(c['new'])}")
            else:
                parts.append(f"{c['label']} 名額 {_fmt(c['old'])} → {_fmt(c['new'])}")
        return f"{head}：" + "；".join(parts)
    return f"{head}：{FIELDS[e['field']]} {_fmt(e['old'])} → {_fmt(e['new'])}"


def write_changes_md(path, changes_path, keep_days=180):
    """從 changes.jsonl 產生最近半年的 CHANGES.md（最新在上，依執行時間分段）。"""
    rows = []
    if os.path.exists(changes_path):
        with open(changes_path, encoding="utf-8") as f:
            rows = [json.loads(line) for line in f if line.strip()]
    if rows:
        cutoff = (dt.datetime.fromisoformat(rows[-1]["at"]) - dt.timedelta(days=keep_days)).isoformat()
        rows = [r for r in rows if r["at"] >= cutoff]
    groups = {}
    for r in rows:
        groups.setdefault(r["at"], []).append(r)
    lines = ["# 跑事 賽事變化紀錄", "",
             "每次抓取（每天 06:07、18:07）和上一次比對，記下來源真正改了什麼。最新的在最上面，保留最近半年。",
             "完整紀錄在 `changes.jsonl`。", ""]
    order = {"early_close": 0, "removed_before_race": 1, "changed": 2, "added": 3, "ended": 4}
    for at in sorted(groups, reverse=True):
        lines.append(f"## {at[:10]} {at[11:16]}")
        lines.append("")
        for e in sorted(groups[at], key=lambda e: (order[e["type"]], e.get("date") or "", e["name"])):
            lines.append("- " + describe(e))
        lines.append("")
    if not groups:
        lines.append("（還沒有變化紀錄）")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def update(history_dir, races, now):
    """比對、記錄；回傳這次的變化清單。第一次執行只建立基準，不算變化。"""
    os.makedirs(os.path.join(history_dir, "snapshots"), exist_ok=True)
    latest_path = os.path.join(history_dir, "latest.json")
    changes_path = os.path.join(history_dir, "changes.jsonl")
    at = now.isoformat(timespec="minutes")
    new = snapshot(races)

    first = not os.path.exists(latest_path)
    if first:
        events = []
    else:
        with open(latest_path, encoding="utf-8") as f:
            old = json.load(f)
        events = diff(old, new, now.date())

    if first or events:
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False, indent=0, sort_keys=True)
        snap = os.path.join(history_dir, "snapshots", now.strftime("%Y-%m-%d_%H%M") + ".json.gz")
        with gzip.open(snap, "wt", encoding="utf-8") as f:
            json.dump(new, f, ensure_ascii=False, sort_keys=True)
    if events:
        with open(changes_path, "a", encoding="utf-8") as f:
            for e in events:
                f.write(json.dumps(dict(at=at, **e), ensure_ascii=False) + "\n")
    with open(os.path.join(history_dir, "runs.jsonl"), "a", encoding="utf-8") as f:
        f.write(json.dumps({"at": at, "races": len(races), "changes": len(events), "baseline": first},
                           ensure_ascii=False) + "\n")
    write_changes_md(os.path.join(history_dir, "CHANGES.md"), changes_path)
    return events
