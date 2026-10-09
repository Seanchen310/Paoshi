# 跑事｜賽事資料爬蟲

從跑者廣場「全國賽會」頁抓取賽事，整理成：

- `output/races.json`：給網站／App 使用的結構化資料
- `output/races.csv`：用 Excel 或 Numbers 打開檢查
- `output/source.html`：當次抓到的原始網頁（備份，出問題時可重跑解析）

只用 Python 內建功能，不用另外安裝套件。

## 在 Mac 上執行

1. 把整個 `paoshi` 資料夾放到「文件」裡，例如 `文件/GitHub/paoshi`。
2. 打開「終端機」（Spotlight 搜尋 Terminal）。
3. 進入資料夾：
   ```
   cd ~/Documents/GitHub/paoshi
   ```
4. 執行：
   ```
   python3 scraper.py
   ```
   第一次執行時，如果 Mac 跳出「要安裝命令列開發者工具」，按「安裝」，裝完再執行一次。
5. 看到「已輸出」就完成了，結果在 `output` 資料夾。

## 每天自動執行（GitHub Actions）

`.github/workflows/scrape.yml` 會讓 GitHub 在台灣時間每天 06:07、18:07 自動抓一次，
結果存回 repo 的 `output/` 資料夾。你的電腦不用開著。

第一次設定：

1. 打開 GitHub Desktop → File → Add Local Repository → 選 `paoshi` 資料夾
   （如果它說這不是 repo，按「create a repository」）。
2. 按 Publish repository，名稱填 `paoshi`。要不要勾 Keep this code private 都可以。
3. 到 github.com 打開這個 repo → 上方 Actions 分頁 → 左邊「抓取賽事資料」→ Run workflow，
   手動跑一次確認成功（綠色勾勾）。
4. 之後就會自動執行。每次更新會出現一筆「更新賽事資料」的 commit。

## 整理出來的欄位

| 欄位 | 說明 |
|---|---|
| `date`, `start_time` | 比賽日期（自動補上年份）與起跑時間 |
| `county`, `region` | 縣市、地區（北部／中部／南部／東部／離島） |
| `distances` | 每個組別的距離、分類、報名費、名額 |
| `categories` | 分類：full 全馬、half 半馬、10k、short 10K 以下、long 25–42K、ultra 超馬、triathlon 鐵人、relay 接力、timed 計時賽 |
| `registration` | 報名開始、截止、狀態（open 報名中／closing_soon 7 天內截止／upcoming 即將開報／closed 已截止／unknown 未知）、剩幾天 |
| `certifications` | AIMS、IAAF、measured（賽道經丈量） |
| `flag` | 跑者廣場標記的 new／updated |
| `issues` | 自動偵測的資料問題（年份不符、日期顛倒、缺連結等） |
| `source` | 資料來源與抓取時間 |

## 使用原則

- 一天執行一到兩次就好，每次只對網站發出 1 個請求。
- 網站上顯示資料時，標明「資料來源：跑者廣場」，並保留到主辦單位的報名連結。

## 測試

```
python3 -m unittest discover tests
```
