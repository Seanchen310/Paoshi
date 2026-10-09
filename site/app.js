/* 跑事｜網頁程式
 * 讀 races.json（每天兩次由 GitHub Actions 更新），畫出三個畫面：
 *   /                 賽事列表
 *   （篩選是列表上的底部面板）
 *   /race/<key>/      賽事詳情（每場一個真正的網址，build_site.py 會預先產生靜態網頁給 Google）
 */
(function () {
  'use strict';

  // Buy Me a Coffee 帳號（buymeacoffee.com/ 後面那段）；空白就不顯示按鈕
  const BMC_SLUG = 'sean310';

  // ---------- 小工具 ----------
  const $ = (sel) => document.querySelector(sel);
  const esc = (s) => String(s == null ? '' : s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const WD = ['日', '一', '二', '三', '四', '五', '六'];
  const DAY = 86400000;

  function store(key, val) {
    try {
      if (val === undefined) return JSON.parse(localStorage.getItem(key) || 'null');
      localStorage.setItem(key, JSON.stringify(val));
    } catch (e) { return null; }
  }

  // 台灣時間的今天 'YYYY-MM-DD' 與現在幾點
  function taipeiNow() {
    const parts = {};
    new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Taipei', year: 'numeric', month: '2-digit',
      day: '2-digit', hour: '2-digit', hour12: false }).formatToParts(new Date())
      .forEach((p) => { parts[p.type] = p.value; });
    return { date: `${parts.year}-${parts.month}-${parts.day}`, hour: Number(parts.hour) % 24 };
  }
  const toDate = (iso) => new Date(iso + 'T00:00:00Z');           // 只比日期，用 UTC 避免時區偏移
  const daysBetween = (a, b) => Math.round((toDate(b) - toDate(a)) / DAY);
  const md = (iso) => `${Number(iso.slice(5, 7))}/${Number(iso.slice(8, 10))}`;
  const weekday = (iso) => WD[toDate(iso).getUTCDay()];

  const ICON = {
    sun: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
    moon: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z"/></svg>',
    filter: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M7 12h10M10 18h4"/></svg>',
    search: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/></svg>',
    back: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
    share: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V4M8 8l4-4 4 4M5 13v6h14v-6"/></svg>',
    cal: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4M12 13v4M10 15h4"/></svg>',
    calendar: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="5" width="16" height="15" rx="2"/><path d="M4 10h16M9 3v4M15 3v4"/></svg>',
    list: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M9 6h11M9 12h11M9 18h11M4 6h.01M4 12h.01M4 18h.01"/></svg>',
    prev: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
    next: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg>',
    coffee: '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9h13v5a5 5 0 01-5 5H9a5 5 0 01-5-5V9zM17 10h1.5a2.5 2.5 0 010 5H17M8 3v3M12 3v3"/></svg>',
    out: '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17L17 7M9 7h8v8"/></svg>',
  };

  // ---------- 日夜主題 ----------
  // 06:00–18:00 白天、其他時間夜晚；手動切換只維持到下一個 6 點或 18 點
  function autoMode() { const h = taipeiNow().hour; return h >= 6 && h < 18 ? 'day' : 'night'; }
  function currentMode() {
    const o = store('paoshi-theme');
    return o && o.until > Date.now() ? o.mode : autoMode();
  }
  function applyTheme() {
    const mode = currentMode();
    document.documentElement.setAttribute('data-theme', mode);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute('content', mode === 'night' ? '#1A1C23' : '#E8F1F8');
    return mode;
  }
  function toggleTheme() {
    const next = currentMode() === 'night' ? 'day' : 'night';
    const now = new Date();
    const h = taipeiNow().hour;
    const hoursLeft = h < 6 ? 6 - h : h < 18 ? 18 - h : 30 - h;    // 到下一個切換點
    const until = now.getTime() + hoursLeft * 3600000 - now.getMinutes() * 60000;
    store('paoshi-theme', { mode: next, until: until });
    applyTheme();
    render();
  }
  setInterval(() => { const before = document.documentElement.getAttribute('data-theme');
    if (applyTheme() !== before) render(); }, 60000);

  // ---------- 資料 ----------
  const CAT_CHIPS = [['full', '全馬'], ['half', '半馬'], ['10k', '10K'], ['short', '10K 以下'], ['ultra', '超馬'], ['trail', '越野'], ['triathlon', '鐵人']];
  const REGIONS = ['北部', '中部', '南部', '東部', '離島'];
  const DATES = [['any', '不限'], ['month', '本月'], ['3m', '未來 3 個月'], ['weekend', '只看週末']];
  const TABS = [['open', '可報名'], ['upcoming', '即將開報'], ['all', '全部']];
  const CERT_LABEL = { AIMS: 'AIMS', IAAF: 'IAAF', measured: '丈量認證' };

  let DATA = null;          // { races, updated }
  let failed = false;
  const saved = store('paoshi-filters') || {};
  const F = {
    tab: 'open', q: '',
    dists: saved.dists || [], regions: saved.regions || [], county: saved.county || '',
    date: saved.date || 'any', cert: !!saved.cert,
    view: saved.view === 'cal' ? 'cal' : 'list',   // 列表／日曆
    calBy: 'race',                                // 日曆標示：比賽日／報名截止日
  };
  const CAL = { month: null, day: null };          // 日曆目前看的月份（YYYY-MM）與選到的日期
  function saveFilters() {
    store('paoshi-filters', { dists: F.dists, regions: F.regions, county: F.county, date: F.date, cert: F.cert, view: F.view });
  }

  // 報名狀態依「今天」重新計算，資料一天只更新兩次，剩幾天才不會差一天
  // 報名狀態規則（2026-10-10 決定）：寧可說待確認，也不說錯。
  // 和 scraper.py 的 live_status() 是同一套規則；這裡依使用者打開網頁的「現在」重算。
  const STALE_MS = 7 * DAY, SOON_MS = 72 * 3600000;
  const atMs = (iso) => iso ? Date.parse(iso + ':00+08:00') : null;   // 台灣時間 → 毫秒
  function liveStatus(reg, now, scraped) {
    const raw = reg.raw || '';
    if (raw.indexOf('額滿') >= 0) return { status: 'full', left: null, reason: 'source_full' };
    if (raw === '已截止' || raw === '已截止報名') return { status: 'closed', left: null, reason: 'source_closed' };
    const start = reg.start, end = reg.end, startAt = atMs(reg.start_at), endAt = atMs(reg.end_at);
    if (!start && !end && !raw) return { status: 'unknown', left: null, reason: 'no_info' };
    const today = taipeiNow().date;
    if (endAt) {
      if (now >= endAt) return { status: 'closed', left: null, reason: 'passed' };
    } else if (end) {
      if (today > end) return { status: 'closed', left: null, reason: 'passed' };
      if (today === end) return { status: 'unknown', left: null, reason: 'deadline_today' };   // 不假設當晚還報得到
    }
    const opens = startAt || (start ? atMs(start + 'T00:00') : null);
    if (opens && now < opens) return { status: 'upcoming', left: null, reason: '' };
    if (opens && scraped < opens) return { status: 'unknown', left: null, reason: 'should_have_opened' };
    if (now - scraped > STALE_MS) return { status: 'unknown', left: null, reason: 'stale' };
    if (endAt) {
      const ms = endAt - now;
      return { status: ms <= SOON_MS ? 'closing_soon' : 'open', left: Math.floor(ms / DAY), reason: '' };
    }
    return { status: 'open', left: null, reason: '' };      // 只知道截止日期：不倒數
  }

  function prepare(json) {
    const today = taipeiNow().date, now = Date.now();
    const races = json.races.filter((r) => r.date && r.date >= today).map((r) => {
      const scraped = r.sources[0] && r.sources[0].scraped_at ? Date.parse(r.sources[0].scraped_at) : now;
      const st = liveStatus(r.registration, now, scraped);
      const fees = r.distances.map((d) => d.fee).filter((f) => f != null);
      const shortLoc = (r.location || r.address || '').replace(r.county || '', '').replace(/^台(北|中|南)市|^臺(北|中|南)市/, '');
      return Object.assign({}, r, {
        st: st.status, left: st.left, why: st.reason,
        minFee: fees.length ? Math.min.apply(null, fees) : null,
        cert: r.certifications.find((c) => CERT_LABEL[c]) || null,
        trail: r.categories.indexOf('trail') >= 0,
        place: [r.county, shortLoc].filter(Boolean).join(' · '),
        hay: [r.name].concat(r.alt_names || [], [r.county, r.location, r.address]).join(' ').toLowerCase().replace(/台/g, '臺'),
      });
    });
    const stamps = json.races.map((r) => r.sources[0] && r.sources[0].scraped_at).filter(Boolean).sort();
    return { races: races, updated: stamps[stamps.length - 1] || '' };
  }

  function load() {
    failed = false;
    fetch('/races.json', { cache: 'no-cache' })
      .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
      .then((j) => { DATA = prepare(j); render(); })
      .catch(() => { failed = true; render(); });
  }

  // ---------- 篩選 ----------
  function inTab(r, tab) {
    if (tab === 'all') return true;
    if (tab === 'open') return r.st === 'open' || r.st === 'closing_soon';
    return r.st === 'upcoming';
  }
  function inDate(r, today) {
    if (F.date === 'month') return r.date.slice(0, 7) === today.slice(0, 7);
    if (F.date === '3m') return daysBetween(today, r.date) <= 92;
    if (F.date === 'weekend') { const d = toDate(r.date).getUTCDay(); return d === 0 || d === 6; }
    return true;
  }
  function matches(r, today, opts) {
    if (F.dists.length && !F.dists.some((c) => r.categories.indexOf(c) >= 0)) return false;
    if (F.regions.length && F.regions.indexOf(r.region) < 0) return false;
    if (F.county && r.county !== F.county) return false;
    if (F.cert && !r.cert) return false;
    if (!inDate(r, today)) return false;
    if (!(opts && opts.ignoreSearch) && F.q) {
      const words = F.q.toLowerCase().replace(/台/g, '臺').split(/\s+/).filter(Boolean);
      if (!words.every((w) => r.hay.indexOf(w) >= 0)) return false;
    }
    return true;
  }
  const extraFilterCount = () => F.regions.length + (F.county ? 1 : 0) + (F.cert ? 1 : 0) + (F.date !== 'any' ? 1 : 0);

  // ---------- 畫面：共用片段 ----------
  function distPills(r, max) {
    const seen = new Set();
    const ds = r.distances.filter((d) => !seen.has(d.label) && seen.add(d.label));
    const shown = max ? ds.slice(0, max) : ds;
    let html = shown.map((d) => `<span class="d ${d.category === 'full' || d.category === 'half' ? d.category : ''}">${esc(d.label)}</span>`).join('');
    if (shown.length < ds.length) html += `<span class="d">+${ds.length - shown.length}</span>`;
    return html;
  }
  function statusText(r) {
    const reg = r.registration;
    if (r.st === 'open') {
      if (r.left != null) return `報名中 · 剩 ${r.left} 天`;                    // 有確切截止時間才倒數
      return '報名中 · ' + (reg.end ? `截止日 ${md(reg.end)}` : '截止日未公布');
    }
    if (r.st === 'closing_soon') {
      const day = reg.end_at.slice(0, 10) === taipeiNow().date ? '今天' : md(reg.end_at.slice(0, 10));
      return `快截止 · ${day} ${reg.end_at.slice(11, 16)} 截止`;
    }
    if (r.st === 'upcoming') {
      const t = reg.start_at ? ' ' + reg.start_at.slice(11, 16) : '';
      return '即將開報 · ' + (reg.start ? `${md(reg.start)}${t} 開報` : '開報日未公布');
    }
    if (r.st === 'closed') return '已截止';
    if (r.st === 'full') return '額滿';
    return {
      deadline_today: '待確認 · 今天截止',
      should_have_opened: '待確認 · 應已開放報名',
      stale: '待確認 · 資料超過 7 天未更新',
    }[r.why] || '報名資訊未公布';
  }
  const feeText = (f) => f === 0 ? '免費' : 'NT$' + f.toLocaleString();

  function card(r) {
    return `<a class="card" href="/race/${encodeURIComponent(r.key || r.id)}/">
      <div class="date"><span class="mon">${Number(r.date.slice(5, 7))} 月</span><span class="day">${Number(r.date.slice(8, 10))}</span><span>週${weekday(r.date)}</span></div>
      <div class="card-body">
        <div class="title-row"><span class="name">${esc(r.name)}</span>${r.postponed_from ? '<span class="tag alert">已延期</span>' : ''}${r.trail ? '<span class="tag">越野</span>' : ''}${r.cert ? `<span class="cert">${CERT_LABEL[r.cert]}</span>` : ''}</div>
        <div class="place-row"><span class="place">${esc(r.place)}</span>${r.minFee != null ? `<span class="fee">${feeText(r.minFee)}${r.minFee ? ' 起' : ''}</span>` : ''}</div>
        <div class="dists">${distPills(r, 6)}</div>
        <span class="status ${r.st}">${statusText(r)}</span>
      </div>
    </a>`;
  }

  function updatedText() {
    const u = DATA && DATA.updated;
    return u ? `${md(u.slice(0, 10))} ${u.slice(11, 16)} 更新` : '';
  }

  // ---------- 畫面：日曆 ----------
  const ymOf = (iso) => iso.slice(0, 7);
  function addMonths(ym, n) {
    const y = Number(ym.slice(0, 4)), m = Number(ym.slice(5, 7)) - 1 + n;
    const d = new Date(Date.UTC(y, m, 1));
    return d.toISOString().slice(0, 7);
  }
  // 一個月的格子
  function monthGrid(ym, byDay, today, byDeadline) {
    const first = toDate(ym + '-01');
    const lead = first.getUTCDay();
    const total = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0)).getUTCDate();
    let cells = '';
    for (let i = 0; i < lead; i++) cells += '<span class="cal-cell blank"></span>';
    for (let d = 1; d <= total; d++) {
      const iso = `${ym}-${String(d).padStart(2, '0')}`;
      const list = byDay[iso] || [];
      const cls = ['cal-cell', list.length ? 'has' : '', iso === CAL.day ? 'sel' : '', iso === today ? 'today' : '', iso < today ? 'past' : ''].join(' ');
      const dots = list.slice(0, 3).map((r) => `<i class="dot-${r.st}"></i>`).join('');
      const label = `${Number(ym.slice(5))}月${d}日${list.length ? `，${list.length} 場${byDeadline ? '截止' : '比賽'}` : ''}`;
      cells += list.length
        ? `<button type="button" class="${cls}" data-day="${iso}" aria-label="${label}" aria-pressed="${iso === CAL.day}"><b>${d}</b><span class="dots">${dots}${list.length > 3 ? '<em>+</em>' : ''}</span></button>`
        : `<span class="${cls}" aria-hidden="true"><b>${d}</b></span>`;
    }
    return `<div class="cal-grid">${WD.map((w) => `<span class="cal-wd">${w}</span>`).join('')}${cells}</div>`;
  }

  // 電腦版一次看兩個月，手機和 iPad 一個月；箭頭一次移動一個月
  function calendarHtml(rows, today) {
    const byDeadline = F.calBy === 'deadline';
    const keyOf = (r) => byDeadline ? r.registration.end : r.date;
    const byDay = {};
    rows.forEach((r) => {
      const k = keyOf(r);
      if (!k || k < today) return;                 // 截止日已過的不標
      (byDay[k] = byDay[k] || []).push(r);
    });
    const days = Object.keys(byDay).sort();
    const span = isWide() ? 2 : 1;
    const minYm = ymOf(today);
    const lastYm = days.length ? ymOf(days[days.length - 1]) : minYm;
    const maxStart = lastYm > minYm && span === 2 ? addMonths(lastYm, -1) : lastYm;   // 最後一頁的第一個月
    if (!CAL.month || CAL.month < minYm || CAL.month > maxStart) CAL.month = minYm;
    const months = Array.from({ length: span }, (_, i) => addMonths(CAL.month, i));
    const shown = days.filter((d) => months.indexOf(ymOf(d)) >= 0);
    if (!CAL.day || months.indexOf(ymOf(CAL.day)) < 0 || !byDay[CAL.day]) CAL.day = shown[0] || null;
    const count = shown.reduce((n, d) => n + byDay[d].length, 0);

    const y0 = months[0].slice(0, 4), y1 = months[span - 1].slice(0, 4);
    const title = span === 1
      ? `${y0} 年 ${Number(months[0].slice(5))} 月`
      : `${y0} 年 ${Number(months[0].slice(5))} 月 – ${y1 !== y0 ? y1 + ' 年 ' : ''}${Number(months[1].slice(5))} 月`;
    const grids = months.map((ym) => `<div class="month">${span > 1 ? `<h3>${Number(ym.slice(5))} 月</h3>` : ''}${monthGrid(ym, byDay, today, byDeadline)}</div>`).join('');

    const picked = CAL.day ? byDay[CAL.day] : [];
    const dayHead = CAL.day
      ? `<h3 class="day-head">${md(CAL.day)}（週${weekday(CAL.day)}）${byDeadline ? '報名截止' : ''} · ${picked.length} 場</h3>${picked.map(card).join('')}`
      : `<div class="notice">${span > 1 ? '這兩個月' : '這個月'}沒有符合條件的${byDeadline ? '報名截止' : '比賽'}。</div>`;
    return `<div class="cal-wrap${span > 1 ? ' two' : ''}"><section class="cal box">
        <div class="cal-top">
          <button type="button" class="icon-btn" data-cal="-1" aria-label="上個月" ${CAL.month <= minYm ? 'disabled' : ''}>${ICON.prev}</button>
          <h2>${title}<small>${count ? `${count} 場` : ''}</small></h2>
          <button type="button" class="icon-btn" data-cal="1" aria-label="下個月" ${CAL.month >= maxStart ? 'disabled' : ''}>${ICON.next}</button>
        </div>
        <div class="seg" role="radiogroup" aria-label="日曆標示">
          <button type="button" role="radio" aria-checked="${!byDeadline}" data-calby="race">比賽日</button>
          <button type="button" role="radio" aria-checked="${byDeadline}" data-calby="deadline">報名截止日</button>
        </div>
        <div class="months">${grids}</div>
        <div class="legend"><span><i class="dot-open"></i>報名中</span><span><i class="dot-closing_soon"></i>快截止</span><span><i class="dot-upcoming"></i>即將開報</span><span><i class="dot-closed"></i>已截止／待確認</span></div>
      </section>
      <div class="day-list">${dayHead}</div></div>`;
  }

  // 列表依月份分段，每段一個小標題（「2026 年 11 月 · 30 場」），長列表比較好掃
  function monthGroups(rows, today) {
    const groups = [];
    rows.forEach((r) => {
      const ym = ymOf(r.date);
      if (!groups.length || groups[groups.length - 1].ym !== ym) groups.push({ ym: ym, rows: [] });
      groups[groups.length - 1].rows.push(r);
    });
    // 少於兩場的月份，和相鄰也只有一場的月份併成同一段（同一列），右邊才不會空一格
    const merged = [];
    groups.forEach((g) => {
      const last = merged[merged.length - 1];
      if (g.rows.length < 2 && last && last.small) { last.yms.push(g.ym); last.rows = last.rows.concat(g.rows); }
      else merged.push({ yms: [g.ym], rows: g.rows, small: g.rows.length < 2 });
    });
    const monthName = (ym, showYear) => (showYear ? `${ym.slice(0, 4)} 年 ` : '') + `${Number(ym.slice(5))} 月`;
    return merged.map((g) => {
      const label = g.yms.map((ym, i) => monthName(ym, ym.slice(0, 4) !== today.slice(0, 4) && (i === 0 || ym.slice(0, 4) !== g.yms[i - 1].slice(0, 4)))).join('、');
      return `<section class="month-group" aria-label="${label}">
        <h3 class="month-head">${label}<small>${g.rows.length} 場</small></h3>
        <div class="cards">${g.rows.map(card).join('')}</div>
      </section>`;
    }).join('');
  }

  // ---------- 畫面：列表 ----------
  // 桌機（≥1024px）篩選常駐在左側欄；手機、iPad 用底部面板
  const wideMQ = window.matchMedia('(min-width: 1024px)');
  const isWide = () => wideMQ.matches;

  function filterGroups() {
    const counties = DATA ? Array.from(new Set(DATA.races
      .filter((r) => r.county && (!F.regions.length || F.regions.indexOf(r.region) >= 0)).map((r) => r.county))) : [];
    const opt = (on, attrs, label) => `<button type="button" class="opt" aria-pressed="${on}" ${attrs}>${label}</button>`;
    return `
      <section class="group"><h2>報名狀態</h2><div class="opts">
        ${TABS.map(([k, label]) => opt(F.tab === k, `data-tab="${k}"`, label === '全部' ? '含已截止' : label)).join('')}
      </div></section>
      <section class="group"><h2>距離<small>可多選</small></h2><div class="opts">
        ${CAT_CHIPS.map(([k, label]) => opt(F.dists.indexOf(k) >= 0, `data-dist="${k}"`, label)).join('')}
      </div></section>
      <section class="group"><h2>比賽日期</h2><div class="opts">
        ${DATES.map(([k, label]) => opt(F.date === k, `data-date="${k}"`, label)).join('')}
      </div></section>
      <section class="group"><h2>地區<small>可多選</small></h2><div class="opts">
        ${REGIONS.map((k) => opt(F.regions.indexOf(k) >= 0, `data-region="${k}"`, k)).join('')}
      </div></section>
      <label class="field">縣市
        <select id="county"><option value="">${F.regions.length ? F.regions.join('、') + '全部' : '全部縣市'}</option>
          ${counties.map((c) => `<option value="${esc(c)}" ${F.county === c ? 'selected' : ''}>${esc(c)}</option>`).join('')}
        </select>
      </label>
      <div class="switch-row">
        <div><b>只看認證賽道</b><small>AIMS／IAAF 認證或經丈量，適合追 PB</small></div>
        <button type="button" class="switch" role="switch" aria-checked="${F.cert}" aria-label="只看認證賽道" data-act="cert"></button>
      </div>`;
  }

  const bmcInline = () => BMC_SLUG
    ? `<a class="bmc-inline" href="https://buymeacoffee.com/${encodeURIComponent(BMC_SLUG)}" target="_blank" rel="noopener" aria-label="請跑事喝杯咖啡">${ICON.coffee}<span>請跑事喝杯咖啡</span></a>`
    : '';
  const footerHtml = () => `<footer class="foot">
      ${bmcInline()}
      <p>資料來源：<a href="http://www.taipeimarathon.org.tw/contest.aspx" target="_blank" rel="noopener">跑者廣場</a>、<a href="https://running.biji.co/index.php?q=competition" target="_blank" rel="noopener">運動筆記</a>。<br>報名與最新內容以主辦單位官網為準。</p>
    </footer>`;

  function renderList(onlyResults) {
    const mode = currentMode();
    const today = taipeiNow().date;
    const base = DATA ? DATA.races.filter((r) => matches(r, today)) : [];
    const rows = base.filter((r) => inTab(r, F.tab));
    const extra = extraFilterCount();

    let body;
    if (failed) body = `<div class="notice">賽事資料載入失敗，請檢查網路後再試。<br><button type="button" data-act="reload">重新載入</button></div>`;
    else if (!DATA) body = `<div class="notice">載入賽事中…</div>`;
    else if (!rows.length) body = `<div class="notice">沒有符合條件的比賽。<br><button type="button" data-act="clear">清除所有篩選</button></div>`;
    else body = F.view === 'cal' ? calendarHtml(rows, today) : monthGroups(rows, today);

    const tabsHtml = TABS.map(([k, label]) => `<button type="button" role="tab" aria-selected="${F.tab === k}" data-tab="${k}">${label}<span class="num">${DATA ? base.filter((r) => inTab(r, k)).length : ''}</span></button>`).join('');
    // 列表／日曆切換：有文字、看得出目前在哪一種，放在內容正上方
    const viewSwitch = `<div class="view-switch" role="radiogroup" aria-label="瀏覽方式">
        <button type="button" role="radio" aria-checked="${F.view === 'list'}" data-view="list">${ICON.list}列表</button>
        <button type="button" role="radio" aria-checked="${F.view === 'cal'}" data-view="cal">${ICON.calendar}日曆</button>
      </div>`;
    const listHtml = `<div class="meta">${viewSwitch}<span>${updatedText()}</span></div>${body}`;
    if (onlyResults && $('#q')) {        // 打字搜尋時只換結果，不動搜尋框（注音輸入才不會被打斷）
      $('.tabs').innerHTML = tabsHtml;
      $('.list').innerHTML = listHtml;
      if ($('#side-count')) $('#side-count').textContent = rows.length;
      return;
    }

    const side = isWide() ? `<aside class="side" aria-label="篩選">
        <div class="sheet-head"><h2 class="side-title">篩選 <small>共 <span id="side-count">${rows.length}</span> 場</small></h2><button type="button" class="text-btn" data-act="clear">全部清除</button></div>
        ${filterGroups()}
      </aside>` : '';
    const prevSide = $('.side') ? $('.side').scrollTop : 0;

    $('#app').innerHTML = `
      <header class="top">
        <div class="brand-row">
          <b class="brand">跑事</b>
          <div class="icon-row">
            <button type="button" class="round accent" data-act="theme" aria-label="${mode === 'night' ? '切換為白天主題' : '切換為夜晚主題'}">${mode === 'night' ? ICON.moon : ICON.sun}</button>
            <button type="button" class="round only-narrow" data-act="filter" aria-label="篩選${extra ? `（已套用 ${extra} 項）` : ''}">${ICON.filter}${extra ? '<span class="dot"></span>' : ''}</button>
          </div>
        </div>
        <div class="controls">
          <label class="search">${ICON.search}<input id="q" type="search" placeholder="搜尋賽名、縣市" aria-label="搜尋賽事" value="${esc(F.q)}" enterkeyhint="search"></label>
          <div class="tabs" role="tablist">${tabsHtml}</div>
        </div>
        <div class="chips only-narrow">
          ${CAT_CHIPS.map(([k, label]) => `<button type="button" class="chip" aria-pressed="${F.dists.indexOf(k) >= 0}" data-dist="${k}">${label}</button>`).join('')}
        </div>
      </header>
      <div class="layout">
        ${side}
        <div class="content">
          <main class="list">${listHtml}</main>
          ${footerHtml()}
        </div>
      </div>`;
    if ($('.side')) $('.side').scrollTop = prevSide;
  }

  // ---------- 畫面：篩選面板（手機、iPad） ----------
  let sheetOpen = false;
  function renderSheet() {
    if (isWide()) sheetOpen = false;
    document.body.style.overflow = sheetOpen ? 'hidden' : '';
    if (!sheetOpen) { $('#sheet').innerHTML = ''; return; }
    const prevScroll = $('.sheet') ? $('.sheet').scrollTop : 0;
    const today = taipeiNow().date;
    const n = DATA ? DATA.races.filter((r) => matches(r, today) && inTab(r, F.tab)).length : 0;
    $('#sheet').innerHTML = `
      <div class="sheet-wrap" data-act="close">
        <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title">
          <div class="grip"></div>
          <div class="sheet-head"><h1 id="sheet-title">篩選</h1><button type="button" class="text-btn" data-act="clear">全部清除</button></div>
          ${filterGroups()}
          <button type="button" class="cta" data-act="close">顯示 <span class="num">${n}</span> 場比賽</button>
        </div>
      </div>`;
    $('.sheet').scrollTop = prevScroll;
  }
  wideMQ.addEventListener('change', () => render());

  // ---------- 畫面：詳情 ----------
  function renderDetail(id) {
    if (!DATA) {
      if ($('#app').dataset.prerendered) return;    // 靜態網頁已經有內容，等資料到了再換成即時狀態
      $('#app').innerHTML = `<div class="list"><div class="notice">${failed ? '賽事資料載入失敗。' : '載入賽事中…'}</div></div>`;
      return;
    }
    delete $('#app').dataset.prerendered;
    const r = DATA.races.find((x) => x.key === id || x.id === id);
    if (!r) {
      $('#app').innerHTML = `<div class="bar"><a class="icon-btn" href="/" data-act="back" aria-label="返回列表">${ICON.back}</a></div>
        <div class="detail"><div class="notice">找不到這場比賽，可能已經結束或改了名稱。<br><button type="button" data-act="home">回到賽事列表</button></div></div>`;
      return;
    }
    const reg = r.registration;
    const period = reg.start || reg.end
      ? `${reg.start ? reg.start.replace(/-/g, '/') + (reg.start_at ? ' ' + reg.start_at.slice(11, 16) : '') : '未公布'} – ${reg.end ? md(reg.end) + (reg.end_at ? ' ' + reg.end_at.slice(11, 16) : '') : '未公布'}`
      : (reg.raw && reg.raw !== '已截止' && reg.raw !== '已截止報名' ? reg.raw : '未公布');
    const info = [
      ['地點', esc(r.location || r.address || '未公布') + (r.location && r.address ? `<small>${esc(r.address)}</small>` : '')],
      ['報名期間', esc(period)],
    ];
    if (r.organizer) info.push(['承辦單位', esc(r.organizer)]);
    if (r.postponed_from) info.push(['延期', `原訂 ${esc(r.postponed_from.replace(/-/g, '/'))}`]);

    const seen = new Set();
    const groups = r.distances.filter((d) => !seen.has(d.label) && seen.add(d.label));
    const hasFee = groups.some((d) => d.fee != null || d.quota != null || d.time_limit);
    // 只提醒會影響報名的不一致：截止日、可能額滿、比賽改期；開報日不同只在還沒開報時才重要
    const conflict = r.issues.some((i) => /截止日兩邊不同|可能額滿|舊日期/.test(i) ||
      (r.st === 'upcoming' && i.indexOf('開始日兩邊不同') >= 0));
    const certs = r.certifications.filter((c) => CERT_LABEL[c])
      .map((c) => `<span class="cert">${CERT_LABEL[c]}${c === 'measured' ? '' : ' 認證'}</span>`).join('');
    const src = r.sources.map((s) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.name)}</a>`).join('、');

    let remind = '';
    if (r.st === 'open' || r.st === 'closing_soon') remind = reg.end ? '截止前提醒我' : '';
    else if (r.st === 'upcoming') remind = reg.start ? '開報時提醒我' : '';
    // 「前往報名」只在：報名中或快截止、比賽日還沒過、有報名連結；否則改成查看官網或賽事資訊
    const canSignup = (r.st === 'open' || r.st === 'closing_soon') && r.date >= taipeiNow().date && r.url;
    const signup = canSignup
      ? `<a class="cta" href="${esc(r.url)}" target="_blank" rel="noopener">前往報名 ${ICON.out}</a>`
      : r.url
        ? `<a class="cta" href="${esc(r.url)}" target="_blank" rel="noopener">查看官方網站 ${ICON.out}</a>`
        : `<a class="cta" href="${esc(r.sources[r.sources.length - 1].url)}" target="_blank" rel="noopener">看賽事資訊 ${ICON.out}</a>`;

    $('#app').innerHTML = `
      <div class="bar">
        <a class="icon-btn" href="/" data-act="back" aria-label="返回列表">${ICON.back}</a>
        <button type="button" class="icon-btn" data-act="share" aria-label="分享">${ICON.share}</button>
      </div>
      <main class="detail">
        <section class="hero">
          <div class="badges">${r.postponed_from ? `<span class="tag alert">已延期（原訂 ${md(r.postponed_from)}）</span>` : ''}${r.trail ? '<span class="tag">越野</span>' : ''}${certs}<span class="status ${r.st}">${statusText(r)}</span></div>
          <h1>${esc(r.name)}</h1>
          ${r.alt_names && r.alt_names.length ? `<div class="aka">也稱：${r.alt_names.map(esc).join('、')}</div>` : ''}
          <div class="when"><span class="big">${r.date.slice(5, 7)}.${r.date.slice(8, 10)}</span>
            <span>${r.date.slice(0, 4)} · 週${weekday(r.date)}${r.start_time ? ' ' + esc(r.start_time) + ' 起跑' : ''}</span></div>
        </section>
        <dl class="box info">${info.map(([k, v]) => `<div><dt>${k}</dt><dd>${v}</dd></div>`).join('')}</dl>
        ${groups.length ? `<section class="sec"><h2>組別</h2><div class="box groups">
          ${groups.map((d) => `<div class="grp"><span class="d ${d.category === 'full' || d.category === 'half' ? d.category : ''}">${esc(d.label)}</span>
            <span class="q">${groupNote(d, hasFee)}</span>
            <span class="f">${d.fee != null ? feeText(d.fee) : ''}</span></div>`).join('')}
        </div>${hasFee ? '' : '<p class="fine">報名費與名額請見主辦單位簡章。</p>'}</section>` : ''}
        ${conflict ? '<div class="warn">兩個資料來源的日期不一致，報名前請以主辦單位官網為準。</div>' : ''}
        ${bmcInline()}
        <p class="fine">賽事資訊整理自${src}，報名與最新內容以主辦單位官網為準。</p>
      </main>
      <div class="actions">
        <button type="button" class="sq" data-act="ics-race" aria-label="比賽日加到行事曆">${ICON.cal}</button>
        ${remind ? `<button type="button" class="ghost" data-act="ics-remind">${remind}</button>` : ''}
        ${signup}
      </div>`;
    window.scrollTo(0, 0);
  }

  // 組別的小字：名額、限時（關門時間）、各組起跑時間
  function minutesText(m) {
    if (m % 60 === 0) return `${m / 60} 小時`;
    if (m > 60) return m % 30 === 0 ? `${m / 60} 小時` : `${Math.floor(m / 60)} 小時 ${m % 60} 分`;
    return `${m} 分鐘`;
  }
  function groupNote(d, hasFee) {
    const parts = [];
    if (d.quota != null) parts.push(`名額 ${d.quota.toLocaleString()}${d.quota_shared ? '（共用）' : ''}`);
    else if (hasFee) parts.push('名額未公布');
    if (d.time_limit) parts.push(`限時 ${minutesText(d.time_limit)}`);
    if (d.start) parts.push(`${d.start} 起跑`);
    return parts.join('<br>');
  }

  // ---------- 加到行事曆：選 Apple 行事曆或 Google 日曆 ----------
  // .ics 檔在部署時就產生好（build_site.py）放在 /race/<key>/ 底下：iPhone 點了直接跳出「加入行事曆」，不會變成下載。
  // Google 日曆不能自訂提醒時間，所以截止提醒＝在「截止前一天早上 9 點」建立一個提醒行程。
  const UA = navigator.userAgent;
  const IS_APPLE = /iPhone|iPad|iPod|Macintosh/.test(UA) && !/Android/.test(UA);
  const IS_ANDROID = /Android/.test(UA);
  const gStamp = (ms) => new Date(ms).toISOString().replace(/[-:]/g, '').replace(/\.\d+/, '');
  const gDay = (iso) => iso.replace(/-/g, '');
  let calSheet = null;      // { race, kind }

  function calEvent(r, kind) {
    const reg = r.registration;
    const page = `${location.origin}/race/${r.key || r.id}/`;
    const link = r.url || page;
    const base = { file: `/race/${r.key || r.id}/${kind}.ics`, location: r.address || r.location || '' };
    if (kind === 'race') {
      const at = r.start_time ? atMs(`${r.date}T${r.start_time}`) : null;
      return Object.assign(base, {
        heading: '比賽日加到行事曆',
        apple: r.start_time ? '比賽前一天、起跑前 2 小時提醒' : '比賽前一天早上 9 點提醒',
        google: '比賽日加到你的 Google 日曆',
        text: r.name,
        dates: at ? `${gStamp(at)}/${gStamp(at + 5 * 3600000)}` : `${gDay(r.date)}/${gDay(new Date(toDate(r.date).getTime() + DAY).toISOString().slice(0, 10))}`,
        details: `${r.distances.map((d) => d.label).join(' / ')}\n報名：${link}\n跑事：${page}`,
      });
    }
    if (kind === 'open') {
      const at = reg.start_at ? atMs(reg.start_at) : atMs(reg.start + 'T09:00');
      return Object.assign(base, {
        heading: '開報時提醒我',
        apple: reg.start_at ? '開報前一天、開報前 10 分鐘提醒' : '開報前一天早上 9 點提醒',
        google: `開報時間（${md(reg.start)}${reg.start_at ? ' ' + reg.start_at.slice(11, 16) : ' 09:00'}）建立提醒行程`,
        text: `開放報名：${r.name}`,
        dates: `${gStamp(at)}/${gStamp(at + 30 * 60000)}`,
        details: `比賽日 ${r.date}\n報名：${link}\n跑事：${page}`,
      });
    }
    // 報名截止
    const exact = reg.end_at && !reg.end_at.endsWith('T00:00');
    let at = atMs(reg.end + 'T09:00') - DAY;                 // 截止前一天早上 9 點
    let text = `明天截止報名：${r.name}`;
    if (at < Date.now()) { at = exact ? atMs(reg.end_at) - 3 * 3600000 : atMs(reg.end + 'T09:00'); text = `今天截止報名：${r.name}`; }
    return Object.assign(base, {
      heading: '截止前提醒我',
      apple: exact ? '截止前 3 天、前 1 天、前 3 小時各提醒一次' : '截止前 3 天、前 1 天早上 9 點各提醒一次',
      google: '截止前一天早上 9 點建立提醒行程',
      text: text,
      dates: `${gStamp(at)}/${gStamp(at + 30 * 60000)}`,
      details: `報名截止：${md(reg.end)}${exact ? ' ' + reg.end_at.slice(11, 16) : ''}\n比賽日 ${r.date}\n報名：${link}\n跑事：${page}`,
    });
  }
  function gcalUrl(ev) {
    const q = new URLSearchParams({ action: 'TEMPLATE', text: ev.text, dates: ev.dates, details: ev.details,
      location: ev.location, ctz: 'Asia/Taipei' });
    return 'https://calendar.google.com/calendar/render?' + q.toString();
  }
  const APPLE_ICON = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="5" width="16" height="15" rx="3"/><path d="M4 10h16M9 3v4M15 3v4"/></svg>';
  const GOOGLE_ICON = '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><rect x="4" y="5" width="16" height="15" rx="3"/><path d="M4 10h16M9 3v4M15 3v4M10 14h4v4"/></svg>';
  function renderCalSheet() {
    if (!calSheet) return;
    const ev = calEvent(calSheet.race, calSheet.kind);
    const apple = `<a class="choice" href="${esc(ev.file)}" data-act="cal-pick">${APPLE_ICON}<span><b>Apple 行事曆</b><small>iPhone、iPad、Mac · ${esc(ev.apple)}</small></span>${IS_APPLE ? '<em>建議</em>' : ''}</a>`;
    const google = `<a class="choice" href="${esc(gcalUrl(ev))}" target="_blank" rel="noopener" data-act="cal-pick">${GOOGLE_ICON}<span><b>Google 日曆</b><small>Android、電腦 · ${esc(ev.google)}</small></span>${IS_ANDROID ? '<em>建議</em>' : ''}</a>`;
    document.body.style.overflow = 'hidden';
    $('#sheet').innerHTML = `
      <div class="sheet-wrap" data-act="close">
        <div class="sheet" role="dialog" aria-modal="true" aria-labelledby="cal-title">
          <div class="grip"></div>
          <div class="sheet-head"><h1 id="cal-title">${ev.heading}</h1><button type="button" class="text-btn" data-act="close">取消</button></div>
          <p class="fine sheet-sub">${esc(calSheet.race.name)}<br>選你手機上用的行事曆，提醒會自動加進去。</p>
          <div class="choices">${IS_ANDROID ? google + apple : apple + google}</div>
          <a class="other-ics" href="${esc(ev.file)}" download data-act="cal-pick">其他行事曆（Outlook 等）：下載 .ics 檔</a>
        </div>
      </div>`;
  }
  function openCal(r, kind) { calSheet = { race: r, kind: kind }; renderCalSheet(); }

  // ---------- 提示訊息、分享 ----------
  let toastTimer;
  function toast(msg) {
    const el = $('#toast');
    el.textContent = msg;
    el.classList.remove('hidden');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.add('hidden'), 3200);
  }
  function share(r) {
    const data = { title: r.name + '｜跑事', text: `${r.name}（${r.date}）`, url: location.href };
    if (navigator.share) { navigator.share(data).catch(() => {}); return; }
    if (navigator.clipboard) navigator.clipboard.writeText(location.href).then(() => toast('已複製連結'), () => toast(location.href));
    else toast(location.href);
  }

  // ---------- 路由與事件 ----------
  let listScroll = 0;
  let cameFromList = false;
  const LIST_TITLE = '跑事｜台灣路跑賽事，現在還能報名哪些';
  function route() {
    const m = location.pathname.match(/^\/race\/([^/]+)\/?$/);
    if (m) return { page: 'detail', id: decodeURIComponent(m[1]) };
    const old = location.hash.match(/^#\/race\/(.+)$/);              // 舊網址 #/race/<id> 也認得
    return old ? { page: 'detail', id: decodeURIComponent(old[1]) } : { page: 'list' };
  }
  function render() {
    const rt = route();
    $('#app').className = 'app ' + (rt.page === 'detail' ? 'is-detail' : 'is-list');
    document.body.dataset.page = rt.page;
    if (rt.page === 'detail') {
      sheetOpen = false; renderSheet(); renderDetail(rt.id);
      const r = DATA && DATA.races.find((x) => x.key === rt.id || x.id === rt.id);
      if (r) {
        document.title = `${r.name} 報名資訊｜跑事`;
        if (location.hash && r.key) history.replaceState(null, '', `/race/${r.key}/`);   // 舊網址換成新網址
      }
    } else { document.title = LIST_TITLE; renderList(); renderSheet(); }
  }
  // 站內換頁不重新載入：網址照樣是真的 /race/<key>/，可以分享、可以被 Google 收錄
  function go(url) { history.pushState(null, '', url); render(); }
  window.addEventListener('popstate', () => {
    const rt = route();
    render();
    if (rt.page === 'list') { window.scrollTo(0, listScroll); cameFromList = false; }
  });

  function toggleIn(arr, v) { return arr.indexOf(v) >= 0 ? arr.filter((x) => x !== v) : arr.concat([v]); }
  function refresh() { saveFilters(); render(); }

  document.addEventListener('click', (e) => {
    const t = e.target.closest('[data-act],[data-tab],[data-dist],[data-date],[data-region],[data-day],[data-cal],[data-calby],[data-view]');
    if (!t) {
      const a = e.target.closest('a.card');
      if (a && !e.metaKey && !e.ctrlKey && !e.shiftKey && e.button === 0) {   // 一般點擊：站內換頁；按著 ⌘ 照樣開新分頁
        e.preventDefault();
        listScroll = window.scrollY; cameFromList = true;
        go(a.getAttribute('href'));
        window.scrollTo(0, 0);
      }
      return;
    }
    const d = t.dataset;
    if (d.tab) { F.tab = d.tab; return refresh(); }
    if (d.view) { F.view = d.view; saveFilters(); return renderList(true); }
    if (d.day) { CAL.day = d.day; return renderList(true); }
    if (d.cal) { CAL.month = addMonths(CAL.month, Number(d.cal)); CAL.day = null; return renderList(true); }
    if (d.calby) { F.calBy = d.calby; CAL.day = null; return renderList(true); }
    if (d.dist) { F.dists = toggleIn(F.dists, d.dist); return refresh(); }
    if (d.date) { F.date = d.date; return refresh(); }
    if (d.region) {
      F.regions = toggleIn(F.regions, d.region);
      if (F.county && DATA && F.regions.length && !DATA.races.some((r) => r.county === F.county && F.regions.indexOf(r.region) >= 0)) F.county = '';
      return refresh();
    }
    const rt = route();
    const race = rt.page === 'detail' && DATA ? DATA.races.find((x) => x.key === rt.id || x.id === rt.id) : null;
    switch (d.act) {
      case 'theme': return toggleTheme();
      case 'filter': sheetOpen = true; return renderSheet();
      case 'close':
        if (t.classList.contains('sheet-wrap') && e.target !== t) return;   // 點面板內部不關
        sheetOpen = false; calSheet = null; return render();
      case 'clear':
        Object.assign(F, { tab: 'open', q: '', dists: [], regions: [], county: '', date: 'any', cert: false });
        return refresh();
      case 'cert': F.cert = !F.cert; return refresh();
      case 'reload': return load();
      case 'home': e.preventDefault(); return go('/');
      case 'back':
        e.preventDefault();
        if (cameFromList) history.back();      // 回到列表原本捲到的位置
        else go('/');
        return;
      case 'share': return race && share(race);
      case 'ics-race': return race && openCal(race, 'race');
      case 'ics-remind': return race && openCal(race, race.st === 'upcoming' ? 'open' : 'deadline');
      case 'cal-pick':
        setTimeout(() => { calSheet = null; render(); toast('已打開行事曆，確認後就會加入提醒'); }, 400);
        return;
    }
  });
  function onSearch(e) {
    if (e.target.id !== 'q' || e.isComposing) return;   // 注音還在選字時先不搜尋
    F.q = e.target.value;
    renderList(true);
  }
  document.addEventListener('input', onSearch);
  document.addEventListener('compositionend', onSearch);
  document.addEventListener('change', (e) => {
    if (e.target.id === 'county') { F.county = e.target.value; refresh(); }
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && (sheetOpen || calSheet)) { sheetOpen = false; calSheet = null; render(); }
  });

  // 「請跑事喝杯咖啡」：手機＝右下角懸浮膠囊（圖示＋文字）；電腦＝頁尾資料來源上方的圓鈕（bmcInline，滑鼠移過去展開文字）
  if (BMC_SLUG && !$('.fab-bmc')) {
    const a = document.createElement('a');
    a.className = 'fab-bmc';
    a.href = `https://buymeacoffee.com/${encodeURIComponent(BMC_SLUG)}`;
    a.target = '_blank'; a.rel = 'noopener';
    a.setAttribute('aria-label', '請跑事喝杯咖啡');
    a.innerHTML = `${ICON.coffee}<span>請跑事喝杯咖啡</span>`;
    document.body.appendChild(a);
    // 往下捲時藏起來（不擋內容），往上捲或回到頂端時再出現
    let lastY = window.scrollY;
    window.addEventListener('scroll', () => {
      const y = window.scrollY;
      if (y > lastY + 6 && y > 80) a.classList.add('fab-hide');
      else if (y < lastY - 6 || y <= 80) a.classList.remove('fab-hide');
      lastY = y;
    }, { passive: true });
  }

  applyTheme();
  render();
  load();
})();
