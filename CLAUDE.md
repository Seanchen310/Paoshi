# 跑事 Paoshi

台灣路跑賽事查詢網站／App。目標：解決「現在還能報名哪些比賽」與「別錯過報名」。
資料來源：跑者廣場（taipeimarathon.org.tw）＋運動筆記（running.biji.co 賽事列表；irunner.biji.co 是它的報名系統，不是賽事列表）。

## 跟 Sean 合作

- Sean 是設計師，不寫程式；程式由 Claude 負責寫、測試、除錯。
- 用繁體中文溝通，說明要具體、白話、少術語。
- Sean 習慣在 **GitHub 網頁**上操作（上傳、編輯檔案），不用 GitHub Desktop。需要他動手時給逐步的網頁操作。
- 電腦是 Mac。

## 目前狀態（2026-10-09，已加入運動筆記）

只用 Python 內建模組。
- `run.py`：入口。抓兩個來源 → 合併 → `output/races.json`、`output/races.csv`。任一來源失敗就不寫檔（保留上次資料）。
- `scraper.py`：跑者廣場 `contest.aspx` 的 `#GridView1` 表格，也放共用工具（距離分類、縣市、`reg_status`、輸出）。
  - 下載失敗會重試 3 次（跑者廣場常間歇性回 HTTP 500）。
- `biji.py`：運動筆記 `running.biji.co/index.php?q=competition`，一頁就有本月起所有賽事（約 200 場，1 個請求）。
- `merge.py`：比對同一場比賽並合併欄位。
- `.github/workflows/scrape.yml`：GitHub Actions 每天台灣時間 06:07、18:07 執行 `run.py`，結果 commit 回 `output/`。
- 網站：**https://paoshi.pages.dev**（Cloudflare Pages 專案 `paoshi`，帳號 molimora@gmail.com；GitHub App 只授權 Paoshi repo）。
- `site/`：網站（純 HTML/CSS/JS，沒有框架、不用建置工具）。`index.html`、`style.css`、`app.js`。讀同一層的 `races.json`。
  - 部署：Cloudflare Pages 連 GitHub repo，Build command `cp output/races.json site/races.json`、output `site`。排程每次存回資料就會自動重新部署。
  - 本機預覽：`cp output/races.json site/races.json` 後用 `.claude/launch.json` 的 `paoshi-site`（port 8787）。`site/races.json` 在 .gitignore。
  - 路由用網址 hash：`#/` 列表、`#/race/<id>` 詳情。篩選是列表上的底部面板，篩選條件存在 localStorage。
  - 報名狀態、剩幾天在瀏覽器依台灣時間的今天重算；比賽日已過的不顯示。
  - 「截止前提醒我／開報時提醒我」＝下載 .ics 行事曆檔（含提醒），不需要帳號或伺服器。
  - 搜尋只重畫結果、不重畫搜尋框，避免打斷注音選字。
  - 兩種瀏覽方式：列表／日曆（列表正上方有文字的兩段式切換，記在 localStorage；刻意不用右上角圖示按鈕，因為不好被發現）。日曆可切「比賽日／報名截止日」，點日期看當天的賽事；圓點顏色＝報名狀態。
- `tests/`：`python -m unittest discover tests`（36 個），用真實頁面片段當測試資料。改解析邏輯前後都要跑。
- 2026-10-09 合併結果：跑者廣場 193、運動筆記 199（不含海外）→ 237 場（兩邊都有 155、只有運動筆記 44、只有跑者廣場 38）；報名中 70、快截止 13、即將開報 4、未知 30、已截止 120。

## 跑者廣場頁面結構（解析重點）

- 每列 8 格：月份標記（含 new.gif／update.png）、賽名＋外部報名連結、認證圖（aims_logo.gif／iaaf.gif／course_ok.png）、日期「MM/DD 星期 HH:MM」、地點、距離按鈕、承辦單位、報名日期。
- 距離是 `<button>`，**報名費與名額藏在 title**：`費用：1400<br/>限額：1500`。
- 只有月/日沒有年份：列表依日期排序，月份變小就跨年；用星期交叉驗證。
- 報名欄寫法：`已截止`、空白、`~ 10月18日`、`10月12日 ~ 10月18日`、`6月22日 ~`、後綴`(最後一週)`。
- 已知資料錯誤：賽名年份與日期不符、報名起訖顛倒、賽名缺字、缺連結 → 寫進每筆的 `issues`。

## 運動筆記頁面結構（解析重點）

- 每場是 `div.competition-list-row#cp_part_{cid}`；`ad-row` 是置頂廣告，跟一般列重複 → 依 cid 去重。
- 「加入行事曆」連結（`a.competition-date-calendar`）最完整：`dates=YYYYMMDD/`、`location=完整地址`、`報名日期:YYYY-MM-DD HH:MM:SS~YYYY-MM-DD HH:MM:SS`。
- 截止時間 00:00 → 實際截止日是前一天。
- 狀態欄：`已截止報名`、`MM-DD截止`、`報名時間未定`、`原YYYY/MM/DD因故延期至YYYY/MM/DD`。
- 距離 `div.event_item`（旁邊有被註解掉的重複 div，HTMLParser 會略過）。認證圖：aims／ctaa（→ measured）／iaaf_gold／jaaf。
- 「國內」列表混有日本、香港、中國賽事 → 地點和地址都對不到臺灣縣市就略過。
- 報名費、主辦單位、關門時間只在詳情頁（`act=info&cid=`），目前沒抓。

## 合併規則（merge.py）

- 配對：日期相同（或運動筆記的延期前日期）＋賽名相似（去掉年份、第N屆、馬拉松／路跑等通用字後比相鄰兩字；≥0.5，或 ≥0.3 且有 2 字以上完全相同）＋縣市相同（相似度 ≥0.9 可不看縣市）。一對一、最像的先配。
- 跑者廣場優先：name、報名費、名額、承辦單位、url、起跑時間、location。運動筆記補：address、報名起訖（有年份時間）、postponed_from、alt_names。
- 截止日兩邊差 >1 天 → 用較晚的並記 issue；跑者廣場寫「已截止」但運動筆記仍在期間 → closed（可能額滿）。
- 已知對不上的：同一場兩邊日期不同（如清水馬拉松嘉年華）、中英文不同名（臺灣極限超級鐵人賽／Taiwan Extreme Super Triathlon）。

## 資料格式（races.json 每筆）

`id, name, alt_names, date, start_time, location, address, county, region, distances[{label, km, category, fee, quota, quota_shared}], categories, organizer, registration{raw, start, end, start_at, end_at, status, days_left}, url, certifications, flag, postponed_from, issues, sources[{name, url, scraped_at}]`

- id = 日期＋賽名的 hash（合併時用跑者廣場的賽名）。

- category：full / half(20–25K) / 10k(9–20K) / short(<9K) / long(25–42K) / ultra / triathlon / relay / timed / virtual / other
- `categories` 另外可能有 `trail`（越野）：兩個網站都沒這欄，`scraper.tag_trail` 用賽名判斷（越野、trail、山徑、天空跑、skyrun），合併後才加。
- status：open / closing_soon(≤7 天) / upcoming / closed / unknown
- region：北部 / 中部 / 南部 / 東部 / 離島

## 設計（手機版 MVP，在 Claude 的設計畫布上）

三個畫面：賽事列表（預設只顯示可報名、距離多選篩選、卡片顯示最低報名費）、篩選、賽事詳情。
品牌字「跑事」用 Noto Serif TC 300、字距 0.1em；數字用 Barlow Condensed；內文 Noto Sans TC。

主題沿用 Sean 另一個專案「修仙小幫狗」，06:00–18:00 白天、18:00–06:00 夜晚自動切換，可手動切換：

| | 白天（靈氣仙境） | 夜晚（玄門夜色） |
|---|---|---|
| 背景 | #E8F1F8 | #1A1C23 |
| 卡片 | #FAFDFF／框 #C2D8E8 | #202229／框 #2C2F37 |
| 文字／次要 | #1E3D52／#4A7090 | #E2E8F0／#94A3B8 |
| 主色（全馬、主要按鈕） | #0C447C | #F59E0B（按鈕上字 #1A1C23） |
| 報名中 | 底 #DDF1E8 字 #1B6B4F | 底 rgba(52,211,153,.13) 字 #34D399 |
| 快截止 | 底 #FEF5D6 字 #7D6608 | 底 rgba(245,158,11,.16) 字 #FBBF24 |
| 即將開報 | 底 #DCEBF5 字 #0C447C | 底 rgba(91,163,201,.18) 字 #8CC8E8 |

## 原則

- 頁面依 `sources` 標明「資料來源：跑者廣場／運動筆記」，保留到主辦單位的報名連結。
- 抓取頻率低（一天兩次、每個網站每次 1 個請求）。運動筆記 robots.txt 沒有限制。之後考慮寫信給兩個網站徵求同意。

## 下一步（依優先序）

1. 設計稿上還沒做的：收藏／我的賽季、底部導覽列、路線海拔。
2. 賽事詳情補關門時間、報名費（只有運動筆記才有的 44 場）、路線、海拔：運動筆記詳情頁有，但一場一個請求，要限量（例如只抓報名中、且每天只抓新出現的）。
