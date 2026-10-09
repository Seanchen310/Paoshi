"""
跑事｜合併多個來源的賽事、去除重複

同一場比賽的判斷方式：
  1. 比賽日期相同（運動筆記有延期資訊時，原本的日期也算）
  2. 賽名相似：去掉年份、「第N屆」、「馬拉松／路跑」這類通用字後，比較兩兩相鄰的字
     （有一半以上相同；或至少三成相同、而且有一段兩個字以上完全一樣，例如「集集」）
  3. 縣市相同（賽名幾乎一模一樣時可以不看縣市）
每場比賽最多只配對一次，從最像的開始配。

合併時每個欄位挑比較可靠的來源：
  - 跑者廣場：報名費、名額、承辦單位、官方報名連結、起跑時間、場地名稱
  - 運動筆記：完整地址、報名起訖（有年份和時間）、延期資訊
"""

import datetime as dt
import re

import scraper as base

GENERIC = ["馬拉松", "半程", "全程", "國際", "全國", "公益", "路跑", "超級", "賽"]


def name_key(name):
    n = (name or "").replace("台", "臺").lower()
    n = re.sub(r"20\d\d|1\d\d\s*年|第\s*[\d一ㄧ二三四五六七八九十]+\s*屆|\d+(th|st|nd|rd)\b", "", n)
    n = re.sub(r"[\W_]+", "", n)
    stripped = n
    for g in GENERIC:
        stripped = stripped.replace(g, "")
    return stripped or n


def common_run(a, b):
    """兩個賽名（去掉通用字後）最長的共同連續字數，例如「集集」→ 2。"""
    ka, kb = name_key(a), name_key(b)
    best = 0
    for i in range(len(ka)):
        for j in range(i + best + 1, len(ka) + 1):
            if ka[i:j] in kb:
                best = j - i
            else:
                break
    return best


def similarity(a, b):
    """0～1，兩個賽名有多像（共同的相鄰兩字 ÷ 較短賽名的組數）。"""
    ka, kb = name_key(a), name_key(b)
    ga = {ka[i:i + 2] for i in range(len(ka) - 1)} or {ka}
    gb = {kb[i:i + 2] for i in range(len(kb) - 1)} or {kb}
    return len(ga & gb) / min(len(ga), len(gb))


def match(primary, secondary):
    """回傳 [(主要來源索引, 次要來源索引)]。"""
    by_date = {}
    for j, b in enumerate(secondary):
        for d in {b["date"], b.get("postponed_from")} - {None}:
            by_date.setdefault(d, []).append(j)
    pairs = []
    for i, a in enumerate(primary):
        for j in by_date.get(a["date"], []):
            b = secondary[j]
            score = similarity(a["name"], b["name"])
            same_county = not a["county"] or not b["county"] or a["county"] == b["county"]
            close = score >= 0.5 or (score >= 0.3 and common_run(a["name"], b["name"]) >= 2)
            if score >= 0.9 or (close and same_county):
                kms = {d["km"] for d in a["distances"]} & {d["km"] for d in b["distances"]}
                pairs.append((score, same_county, len(kms - {None}), i, j))
    pairs.sort(reverse=True)
    used_a, used_b, out = set(), set(), []
    for *_, i, j in pairs:
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            out.append((i, j))
    return out


def combine(a, b, today):
    """a＝跑者廣場、b＝運動筆記，合併成一筆。"""
    r = dict(a)
    issues = list(a["issues"])
    if b["name"] != a["name"]:
        r["alt_names"] = a["alt_names"] + [b["name"]]
    r["address"] = b["address"]
    r["county"] = a["county"] or b["county"]
    r["region"] = base.COUNTY_TO_REGION.get(r["county"])
    if not a["distances"]:
        r["distances"] = b["distances"]
        r["categories"] = b["categories"]
        issues = [i for i in issues if i != "沒有距離資料"]
    r["certifications"] = a["certifications"] + [c for c in b["certifications"] if c not in a["certifications"]]

    if b["postponed_from"]:
        r["postponed_from"] = b["postponed_from"]
        if a["date"] == b["postponed_from"] and b["date"]:
            r["date"] = b["date"]
            issues.append(f"跑者廣場仍寫舊日期 {a['date']}，運動筆記顯示延期到 {b['date']}")

    ra, rb = a["registration"], b["registration"]
    if rb["end"]:
        reg = dict(rb)
        # 運動筆記的報名日期比較完整，跑者廣場報名欄的問題就不用列了
        issues = [i for i in issues if not i.startswith("報名起訖")]
        if ra["end"] and abs((dt.date.fromisoformat(ra["end"]) -
                              dt.date.fromisoformat(rb["end"])).days) > 1:
            issues.append(f"報名截止日兩邊不同：跑者廣場 {ra['end']}、運動筆記 {rb['end']}")
            if ra["end"] > rb["end"]:
                # 寧可多顯示一場還能報名的，也不要漏掉：採用較晚的截止日
                reg["end"], reg["end_at"] = ra["end"], None
                start = dt.date.fromisoformat(reg["start"]) if reg["start"] else None
                reg["status"], reg["days_left"] = base.reg_status(
                    start, dt.date.fromisoformat(ra["end"]), today)
        if ra["start"] and rb["start"] and ra["start"] != rb["start"]:
            issues.append(f"報名開始日兩邊不同：跑者廣場 {ra['start']}、運動筆記 {rb['start']}")
        if ra["raw"] == "已截止" and reg["status"] != "closed":
            reg["status"], reg["days_left"] = "closed", None
            issues.append("跑者廣場標示已截止（可能額滿提前截止）")
        reg["raw"] = ra["raw"] or rb["raw"]
        r["registration"] = reg
    issues += ["運動筆記：" + i for i in b["issues"] if i not in a["issues"]]

    r["issues"] = issues
    r["sources"] = a["sources"] + b["sources"]
    return r


def merge(primary, secondary, today):
    """primary＝跑者廣場、secondary＝運動筆記。回傳合併後依日期排序的清單。"""
    pairs = match(primary, secondary)
    paired_a = {i: j for i, j in pairs}
    paired_b = set(paired_a.values())
    out = []
    for i, a in enumerate(primary):
        out.append(combine(a, secondary[paired_a[i]], today) if i in paired_a else a)
    out += [b for j, b in enumerate(secondary) if j not in paired_b]
    out.sort(key=lambda r: (r["date"] or "9999", r["name"]))
    return out
