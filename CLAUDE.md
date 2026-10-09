# 跑事 Paoshi

台灣路跑賽事查詢網站／App。目標：解決「現在還能報名哪些比賽」與「別錯過報名」。
資料來源：跑者廣場（taipeimarathon.org.tw）＋運動筆記（running.biji.co 賽事列表；irunner.biji.co 是它的報名系統，不是賽事列表）。

## 跟 Sean 合作

- **所有工作都在 Claude Code 做**（產品策略、設計討論、程式）。Sean 是設計師，Claude 兼 PM 與工程師。
- **給人看的文件放 Claude Docs，不放 GitHub**：主文件是〈跑事 產品設計與策略書〉https://claude.ai/code/artifact/425c195c-12d2-4724-81a7-71488a2c0379 。
  每個產品／設計決定都要同時寫進策略書（給人看）和這份 CLAUDE.md（給程式用）；沒寫進去的就當作還沒決定。

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
- `biji_detail.py`：運動筆記賽事詳情頁的「項目」區（每組起跑、費用、限時、限額、參賽贈品）＋主辦單位＋相關連結（線上報名／活動簡章，略過 doubleclick 等廣告追蹤連結）。
  - 有禮貌地抓：排程每次最多 20 頁（`--details 20`）、每頁間隔 3 秒；快取在 `data/biji_details.json`（進 git），14 天內不重抓；沒抓過的、可報名／即將開報的、比賽日近的優先。單頁失敗不影響排程。
  - 只補空白：跑者廣場有的報名費、名額照用（運動筆記詳情頁的費用偶爾有錯，例如渣打半馬）；新增每組 `time_limit`（分鐘）、`time_limit_text`、`start`；補 organizer、url。
  - 組別比對：標籤相同，或距離差 0.3 公里內最接近的（列表 42K ↔ 詳情 42.195K）。
  - 歷史紀錄：費用、名額從「沒有」變成有值不算變化（是補資料），只記真的改了。
- `history.py`：歷史紀錄（策略書排第 1 的優勢）。每次排程和上一次比對 → `history/`：`latest.json`（比對基準）、`snapshots/*.json.gz`（有變化才存）、`changes.jsonl`、`runs.jsonl`（每次執行一行，算排程成功率）、`CHANGES.md`（給人看，最近半年）。
  - 只比對來源寫的事實，不比對推算的狀態／剩幾天，避免假變化。
  - 同一場比賽的編號：有運動筆記就用 `biji-<cid>`（改名改期不變），否則用 id。
  - 事件：added／ended（比賽日過了）／removed_before_race（比賽前消失，可能取消）／changed（逐欄位，組別看費用與名額）／early_close（截止日前來源就標已截止或額滿，記提前幾天）。
  - 2026-10-10 開始累積（第一次執行只建立基準）。
- `.github/workflows/scrape.yml`：GitHub Actions 每天台灣時間 06:07、18:07 執行 `run.py`，結果 commit 回 `output/`。
- 網站：**https://paoshi.pages.dev**（Cloudflare Pages 專案 `paoshi`，帳號 molimora@gmail.com；GitHub App 只授權 Paoshi repo）。
- `site/`：網站（純 HTML/CSS/JS，沒有框架、不用建置工具）。`index.html`、`style.css`、`app.js`。讀同一層的 `races.json`。
  - 部署：Cloudflare Pages 連 GitHub repo，Build command `python3 build_site.py`、output `site`。排程每次存回資料就會自動重新部署。
  - `build_site.py`：複製 races.json，並為每場比賽產生靜態網頁 `site/race/<key>/index.html`（title、description、canonical、og、schema.org SportsEvent JSON-LD、預先寫好的詳情內容），加上 sitemap.xml、robots.txt。這些產生的檔案都在 .gitignore。
  - Google Search Console：2026-10-10 以「網址前置字元」https://paoshi.pages.dev/ 驗證（帳號 molimora@gmail.com），已送出 sitemap.xml 並要求首頁建立索引。
    驗證靠 `site/googlec7ef7df34be6e497.html`，**不能刪**（刪了會失去驗證）。Cloudflare 會把 .html 轉址到無副檔名版本，Google 接受。
  - 本機預覽：`python3 build_site.py` 後用 `.claude/launch.json` 的 `paoshi-site`（port 8787）。
  - 網址：`/` 列表、`/race/<key>/` 詳情（真正的網址，站內用 pushState 換頁不重新載入；舊的 `#/race/<id>` 會自動轉成新網址）。資產路徑一律用絕對路徑（/app.js）。
  - 靜態網頁的 #app 有 `data-prerendered`：資料載入前先顯示預先寫好的內容，載入後換成即時狀態。
  - 篩選是列表上的底部面板，篩選條件存在 localStorage。
  - 報名狀態、剩幾天在瀏覽器依台灣時間的今天重算；比賽日已過的不顯示。
  - 「截止前提醒我／開報時提醒我」／行事曆鈕 → 跳出選單：Apple 行事曆（連到部署時產生的 `/race/<key>/{deadline,open,race}.ics`，`_headers` 設成 text/calendar，iPhone 直接跳出加入畫面）或 Google 日曆（calendar.google.com 新增活動連結；不能自訂提醒，所以截止提醒＝截止前一天 09:00 的行程）。依裝置把建議的排第一（iPhone/Mac→Apple、Android→Google）。另有「下載 .ics」給其他行事曆。
  - 「請跑事喝杯咖啡」懸浮按鈕（Buy Me a Coffee 黃），往下捲自動藏起、往上捲出現。
    - 手機（<1024）：右下角 64px 圓鈕，大咖啡杯（45.75px）＋下緣弧形文字「支持跑事」（字級 10.5、字距 5.5）。弧形文字**四個字各自用 textPath 放在對稱位置**，不用 letter-spacing（不同瀏覽器處理字距不同，會歪）。尺寸位置以設計畫布「支持跑事圓鈕（放大 4 倍）」畫板為準（Sean 在畫布直接拖曳縮放，數值除以 4 套用）。手機沒有滑鼠移過去，一定要有文字。詳情頁抬高讓開報名列。
    - 電腦（≥1024）：浮動，距底部 48px；捲到底時按鈕下緣停在最後一張卡片的下緣（不掉進頁尾），接近頁尾時自動出現；平常只有咖啡圖示，滑鼠移過去向左展開「請跑事喝杯咖啡」。右邊緣對齊日夜切換鈕的右緣（詳情頁對齊內容欄右緣），由 app.js `placeFab()` 計算。Sean 2026-10-10 確認：不要放在頁尾資料來源那裡。
  - 詳情頁組別小字：名額、限時（關門時間）、起跑時間。
  - 列表月份分段：少於兩場的相鄰月份併成一段（「2027 年 11 月、12 月 · 2 場」）。
  - 搜尋只重畫結果、不重畫搜尋框，避免打斷注音選字。
  - 版面：手機（<768）單欄、底部篩選面板；iPad（≥768）卡片兩欄、搜尋與分頁同列、日曆與當天清單並排、篩選改置中視窗；桌機（≥1024）頁首併成一排（品牌｜搜尋＋分頁｜主題）、篩選常駐左側欄；≥1360 卡片三欄。
  - 列表依月份分段，月份小標題（「2027 年 1 月 · 18 場」，今年不寫年份）捲動時固定在頂端；所有尺寸都有。詳情頁最寬 720–760px。
  - Buy Me a Coffee：`app.js` 最上面的 `BMC_SLUG` = `sean310`（buymeacoffee.com/sean310；空白就不顯示）。用一般連結按鈕，不用官方 script（它用 document.write，在動態畫面會壞）。出現在列表頁尾、詳情頁說明下方。
  - 兩種瀏覽方式：列表／日曆（列表正上方有文字的兩段式切換，記在 localStorage；刻意不用右上角圖示按鈕，因為不好被發現）。日曆可切「比賽日／報名截止日」，點日期看當天的賽事；圓點顏色＝報名狀態。電腦版（≥1024）一次並排兩個月、當天清單排在下方多欄；手機與 iPad 一個月。箭頭一次移一個月。
- `tests/`：`python -m unittest discover tests`（62 個），用真實頁面片段當測試資料。改解析邏輯前後都要跑。
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

## 報名狀態規則（2026-10-10 決定並實作）

原則：寧可說待確認，也不說錯。Python `scraper.live_status()`（合併後由 `apply_status_rules` 套用，CSV 用）與網站 `app.js liveStatus()`（依打開網頁的當下重算）是同一套規則，改一邊就要改另一邊；測試在 `tests/test_status.py`。
- 狀態：open 報名中／closing_soon 快截止／upcoming 即將開報（分頁名稱維持「即將開報」）／closed 已截止／full 額滿／unknown 待確認。
- 只知道截止「日期」→ 不倒數，顯示「截止日 10/30」；知道確切截止時間（運動筆記的 end_at）才倒數。
- 快截止＝有確切截止時間且剩不到 72 小時。
- 只知道日期、今天就是截止日 → 待確認。
- 超過 7 天沒抓到新資料 → 報名中降級為待確認（剛好 7 天不降級）。
- 即將開報的比賽已到開報時間 → 待確認，等下次抓取。
- 來源寫額滿 → full。已取消、已延期等異動要當主訊息，不用綠色報名中蓋過。
- 「前往報名」只在：報名中或快截止、比賽日未過、有報名連結 時顯示；否則有連結→「查看官方網站」，沒有→「看賽事資訊」（來源頁）。
- 有 postponed_from 的比賽在卡片與詳情顯示黃色「已延期」標籤。
- 待確認的畫面文字依原因：今天截止／應已開放報名／資料超過 7 天未更新；完全沒資訊顯示「報名資訊未公布」。
- 半馬 20–22K（含 22K）；22–42K 為長距離（long）。

## 合併規則（merge.py）

- 配對：日期相同（或運動筆記的延期前日期）＋賽名相似（去掉年份、第N屆、馬拉松／路跑等通用字後比相鄰兩字；≥0.5，或 ≥0.3 且有 2 字以上完全相同）＋縣市相同（相似度 ≥0.9 可不看縣市）。一對一、最像的先配。
- 跑者廣場優先：name、報名費、名額、承辦單位、url、起跑時間、location。運動筆記補：address、報名起訖（有年份時間）、postponed_from、alt_names。
- 截止日兩邊差 >1 天 → 用較晚的並記 issue；跑者廣場寫「已截止」但運動筆記仍在期間 → closed（可能額滿）。
- 已知對不上的：同一場兩邊日期不同（如清水馬拉松嘉年華）、中英文不同名（臺灣極限超級鐵人賽／Taiwan Extreme Super Triathlon）。

## 資料格式（races.json 每筆）

`id, key, name, alt_names, date, start_time, location, address, county, region, distances[{label, km, category, fee, quota, quota_shared, time_limit?, time_limit_text?, start?}], categories, organizer, registration{raw, start, end, start_at, end_at, status, days_left}, url, certifications, flag, postponed_from, issues, sources[{name, url, scraped_at}]`

- id = 日期＋賽名的 hash（合併時用跑者廣場的賽名）。
- key = 穩定編號（有運動筆記就是 `biji-<cid>`，否則同 id），網站網址與歷史紀錄都用它。

- category：full / half(20–22K) / 10k(9–20K) / short(<9K) / long(25–42K) / ultra / triathlon / relay / timed / virtual / other
- `categories` 另外可能有 `trail`（越野）：兩個網站都沒這欄，`scraper.tag_trail` 用賽名判斷（越野、trail、山徑、天空跑、skyrun），合併後才加。
- status：open / closing_soon（有確切截止時間且 ≤72 小時）/ upcoming / closed / full / unknown（待確認）；days_left 只在有確切截止時間時才有值
- region：北部 / 中部 / 南部 / 東部 / 離島

## 設計（手機版 MVP，在 Claude 的設計畫布上）

三個畫面：賽事列表（預設只顯示可報名、距離多選篩選、卡片顯示最低報名費）、篩選、賽事詳情。
品牌字「跑事」用黑體 Noto Sans TC 700、字距 0.1em（原本是 Noto Serif TC 300，Sean 改成黑體；標題下的「靈氣仙境 · 白天」已取消）；數字用 Barlow Condensed；內文 Noto Sans TC。

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

## 下一步（依優先序，與策略書一致）

1. 寫信給跑者廣場、運動筆記，徵求使用資料的同意。
2. 選定流量統計工具（不記錄姓名、Email、精確位置）。
3. 收藏、比較、底部導覽、篩選條件寫進網址。
4. 開報提醒（LINE 或 Email）。
5. 路線、海拔（運動筆記詳情頁的簡介裡是圖片，不好結構化）。
