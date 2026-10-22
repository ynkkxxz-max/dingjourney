/**
 * DingJourney - Trading Calendar Dashboard Logic
 */

// Application State
const state = {
  currentYear: 2026,
  currentMonth: 10, // 10 = October (1-indexed)
  calendarMode: 'compact', // 'compact' (Day 1 on Mon, matches user drawing) or 'standard'
  trades: [],
  stats: {},
  config: {},
  selectedDate: null,
  activeTradeType: 'BUY',
  accountFilter: 'ALL', // 'ALL', 'REAL', or 'DEMO'
  manualAccountType: 'REAL' // 'REAL' or 'DEMO' for manual trade entry
};

const MONTH_NAMES = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"
];

// Safe listener helper to prevent any null reference exceptions
function addListener(id, event, handler) {
  const el = document.getElementById(id);
  if (el) {
    el.addEventListener(event, handler);
    return true;
  }
  return false;
}

// Document Ready - execute immediately if DOM is already ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', () => {
    initApp();
  });
} else {
  initApp();
}

async function initApp() {
  try {
    setupEventListeners();
  } catch (e) {
    console.error('Setup listeners notice:', e);
  }

  try {
    setupYearDropdown();
  } catch (e) {
    console.error('Year dropdown notice:', e);
  }

  // Fetch stats and trades immediately in parallel
  try {
    await refreshDashboard();
  } catch (e) {
    console.error('Dashboard refresh notice:', e);
  }

  loadConfig();
  checkMT5LiveStatus();
}

function setupYearDropdown() {
  const yearSelect = document.getElementById('yearSelect');
  if (!yearSelect) return;
  yearSelect.innerHTML = '';
  for (let y = 2024; y <= 2030; y++) {
    const opt = document.createElement('option');
    opt.value = y;
    opt.textContent = y;
    if (y === state.currentYear) opt.selected = true;
    yearSelect.appendChild(opt);
  }
}

function setupEventListeners() {
  // Calendar Mode Toggle (Compact vs Weekday)
  const btnToggle = document.getElementById('btnToggleCalendarMode');
  if (btnToggle) {
    btnToggle.addEventListener('click', () => {
      state.calendarMode = (state.calendarMode === 'compact') ? 'standard' : 'compact';
      const label = document.getElementById('calendarModeLabel');
      if (label) {
        label.textContent = (state.calendarMode === 'compact') ? '📅 Day 1 on Mon' : '📅 Weekday Offset';
      }
      renderCalendar();
    });
  }

  // Account Filter Tabs (ALL / REAL / DEMO)
  document.querySelectorAll('.account-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.account-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      state.accountFilter = tab.dataset.type;
      refreshDashboard();
    });
  });

  // Manual Trade Account Type Selector
  const btnReal = document.getElementById('btnAccReal');
  const btnDemo = document.getElementById('btnAccDemo');
  if (btnReal && btnDemo) {
    btnReal.addEventListener('click', () => {
      state.manualAccountType = 'REAL';
      btnReal.classList.add('real-active');
      btnDemo.classList.remove('demo-active');
    });
    btnDemo.addEventListener('click', () => {
      state.manualAccountType = 'DEMO';
      btnDemo.classList.add('demo-active');
      btnReal.classList.remove('real-active');
    });
  }

  // Month & Year changes
  addListener('monthSelect', 'change', (e) => {
    state.currentMonth = parseInt(e.target.value);
    refreshDashboard();
  });

  addListener('yearSelect', 'change', (e) => {
    state.currentYear = parseInt(e.target.value);
    refreshDashboard();
  });

  // Add Trade Modal Open & Close
  addListener('btnAddTrade', 'click', () => {
    openAddTradeModal();
  });

  addListener('closeAddTradeModal', 'click', () => {
    closeModal('addTradeModal');
  });

  // Refresh Button (Syncs active MT5 deals & refreshes calendar)
  addListener('btnRefresh', 'click', async () => {
    showToast('Syncing with MT5 & refreshing...', 'info');
    try {
      await fetch('/api/mt5/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ days_back: 7 })
      });
    } catch (e) {
      // Offline / passive
    }
    await refreshDashboard();
    checkMT5LiveStatus();
    showToast('Dashboard up to date!', 'success');
  });

  // Edit Capital Button
  addListener('btnEditCapital', 'click', () => {
    const capInput = document.getElementById('capitalInput');
    if (capInput) capInput.value = state.stats.starting_capital || 10000;
    openModal('capitalModal');
  });

  addListener('closeCapitalModal', 'click', () => {
    closeModal('capitalModal');
  });

  addListener('btnSaveCapital', 'click', async () => {
    const capInput = document.getElementById('capitalInput');
    const newCapital = capInput ? parseFloat(capInput.value) : NaN;
    if (!isNaN(newCapital) && newCapital > 0) {
      await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ starting_capital: newCapital })
      });
      closeModal('capitalModal');
      await refreshDashboard();
      showToast('Starting capital updated!', 'success');
    }
  });

  // Trade Type Selector (BUY / SELL)
  addListener('btnTypeBuy', 'click', () => {
    setTradeType('BUY');
  });
  addListener('btnTypeSell', 'click', () => {
    setTradeType('SELL');
  });

  // Submit Trade Form
  addListener('addTradeForm', 'submit', async (e) => {
    e.preventDefault();
    await submitNewTrade();
  });

  // Day Details Modal Close
  addListener('closeDayDetailModal', 'click', () => {
    closeModal('dayDetailModal');
  });

  // Add trade from inside day details modal
  addListener('btnAddTradeFromDay', 'click', () => {
    closeModal('dayDetailModal');
    openAddTradeModal(state.selectedDate);
  });

  // Close modals when clicking overlay outside box
  document.querySelectorAll('.modal-overlay').forEach(overlay => {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) {
        overlay.classList.remove('active');
      }
    });
  });
}

function setTradeType(type) {
  state.activeTradeType = type;
  const buyBtn = document.getElementById('btnTypeBuy');
  const sellBtn = document.getElementById('btnTypeSell');
  if (type === 'BUY') {
    buyBtn.classList.add('buy-active');
    sellBtn.classList.remove('sell-active');
  } else {
    sellBtn.classList.add('sell-active');
    buyBtn.classList.remove('buy-active');
  }
}

async function loadConfig() {
  try {
    const res = await fetch('/api/config');
    state.config = await res.json();
  } catch (err) {
    console.error('Failed to load config:', err);
  }
}

async function refreshDashboard() {
  try {
    const filterParam = state.accountFilter !== 'ALL' ? `&account_type=${state.accountFilter}` : '';

    // Fetch Stats & Trades in parallel for 2x faster load
    const [statsRes, tradesRes] = await Promise.all([
      fetch(`/api/stats?year=${state.currentYear}&month=${state.currentMonth}${filterParam}`),
      fetch(`/api/trades?year=${state.currentYear}&month=${state.currentMonth}${filterParam}`)
    ]);

    const [statsData, tradesData] = await Promise.all([
      statsRes.json(),
      tradesRes.json()
    ]);

    state.stats = statsData;
    renderKpis();

    state.trades = tradesData.trades || [];
    renderCalendar();

    // Update Header indicators
    const monthName = MONTH_NAMES[state.currentMonth - 1];
    document.getElementById('calendarMonthTitle').textContent = `${monthName} ${state.currentYear}`;
    document.getElementById('brandBadgeYear').textContent = state.currentYear;
  } catch (err) {
    console.error('Error refreshing dashboard:', err);
  }
}

function renderKpis() {
  const s = state.stats;
  const curr = '$';
  // 1. Starting Capital & Account Type (REAL / DEMO)
  document.getElementById('kpiStartingCapital').textContent = `${curr}${formatMoney(s.starting_capital)}`;
  const accType = state.accountFilter !== 'ALL' ? state.accountFilter : (s.account_type || 'REAL');
  const badgeEl = document.getElementById('kpiAccountTypeBadge');
  if (badgeEl) {
    badgeEl.textContent = accType;
    badgeEl.className = `account-badge ${accType.toLowerCase()}`;
  }
  const accNameEl = document.getElementById('kpiAccountName');
  if (accNameEl) {
    accNameEl.textContent = s.account_name || 'Base Account';
  }

  // 2. Monthly Net P&L
  const netPnlEl = document.getElementById('kpiMonthlyNetPnl');
  const pnlSign = s.net_pnl >= 0 ? '+' : '-';
  const pnlColorClass = s.net_pnl >= 0 ? 'color-profit' : 'color-loss';
  netPnlEl.textContent = `${pnlSign}${curr}${formatMoney(Math.abs(s.net_pnl))}`;
  netPnlEl.className = `kpi-value ${pnlColorClass}`;

  const pctBadge = document.getElementById('kpiPnlPct');
  const pctSign = s.pnl_percentage >= 0 ? '+' : '';
  pctBadge.textContent = `${pctSign}${s.pnl_percentage.toFixed(2)}%`;
  pctBadge.style.color = s.pnl_percentage >= 0 ? 'var(--color-profit)' : 'var(--color-loss)';
  pctBadge.style.borderColor = s.pnl_percentage >= 0 ? 'rgba(0, 229, 153, 0.3)' : 'rgba(255, 71, 87, 0.3)';
  pctBadge.style.backgroundColor = s.pnl_percentage >= 0 ? 'rgba(0, 229, 153, 0.15)' : 'rgba(255, 71, 87, 0.15)';

  document.getElementById('kpiCurrentBalance').textContent = `Balance: ${curr}${formatMoney(s.current_balance)}`;

  // 3. Total Trades
  document.getElementById('kpiTotalTrades').textContent = s.total_trades;
  document.getElementById('kpiTradesBreakdown').innerHTML = `
    <span class="green-txt">${s.wins}W</span> • 
    <span class="red-txt">${s.losses}L</span> • 
    <span class="gray-txt">${s.breakeven}BE</span>
  `;

  // 4. Win Rate
  document.getElementById('kpiWinRate').textContent = `${s.win_rate}%`;
  document.getElementById('kpiWinRateBar').style.width = `${Math.min(100, Math.max(0, s.win_rate))}%`;

  // 5. Profit Factor
  document.getElementById('kpiProfitFactor').textContent = s.profit_factor;
  document.getElementById('kpiGrossWin').textContent = `Gross Win: ${curr}${formatMoney(s.gross_win)}`;
}

function renderCalendar() {
  const grid = document.getElementById('calendarGrid');
  grid.innerHTML = '';

  const year = state.currentYear;
  const month = state.currentMonth; // 1-indexed

  // Group trades by date (YYYY-MM-DD)
  const tradesByDate = {};
  state.trades.forEach(t => {
    const dateKey = t.close_date;
    if (!tradesByDate[dateKey]) {
      tradesByDate[dateKey] = [];
    }
    tradesByDate[dateKey].push(t);
  });

  // Calculate days in month & starting day of week
  const firstDay = new Date(year, month - 1, 1);
  const totalDays = new Date(year, month, 0).getDate();

  let startDayOfWeek = 0;
  if (state.calendarMode === 'standard') {
    let dayIdx = firstDay.getDay(); // 0 is Sunday, 1 is Monday...
    startDayOfWeek = (dayIdx === 0) ? 6 : dayIdx - 1; // Mon = 0, Sun = 6
  }

  // Total calendar slots (multiples of 7)
  const totalSlotsNeeded = startDayOfWeek + totalDays;
  const totalGridCells = Math.ceil(totalSlotsNeeded / 7) * 7;

  // Render leading empty slots from previous month if in standard mode
  if (startDayOfWeek > 0) {
    const prevMonthDays = new Date(year, month - 1, 0).getDate();
    for (let i = startDayOfWeek - 1; i >= 0; i--) {
      const dayNum = prevMonthDays - i;
      const cell = document.createElement('div');
      cell.className = 'day-cell inactive-month';
      cell.innerHTML = `
        <div class="day-cell-top">
          <span class="day-plain-number">${dayNum}</span>
        </div>
      `;
      grid.appendChild(cell);
    }
  }

  // Render active month days
  const now = new Date();
  const todayStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;

  for (let day = 1; day <= totalDays; day++) {
    const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const dayTrades = tradesByDate[dateStr] || [];
    const isToday = (dateStr === todayStr);
    
    const cell = document.createElement('div');
    cell.className = 'day-cell';
    cell.dataset.date = dateStr;
    if (isToday) cell.classList.add('today-cell');

    const todayTag = isToday ? '<span class="today-indicator-tag">TODAY</span>' : '';

    if (dayTrades.length > 0) {
      // Trades exist for this day!
      const dayNetProfit = dayTrades.reduce((acc, t) => acc + t.profit, 0);
      const isProfit = dayNetProfit >= 0;
      
      cell.classList.add(isProfit ? 'profit-day' : 'loss-day');

      const sign = isProfit ? '+' : '-';
      const statusLabel = isProfit ? 'PROFIT' : 'LOSS';
      const formattedPnl = `${sign}$${formatMoney(Math.abs(dayNetProfit))}`;

      cell.innerHTML = `
        <div class="day-cell-top">
          <div style="display: flex; align-items: center; gap: 5px;">
            ${todayTag}
            <span class="trade-count-label">Trades: ${dayTrades.length}</span>
          </div>
          <div class="day-badge">${day}</div>
        </div>
        <div class="day-cell-center">
          <div class="day-pnl-value">${formattedPnl}</div>
        </div>
        <div class="day-cell-bottom">
          <span class="status-pill">${statusLabel}</span>
        </div>
      `;
    } else {
      // Empty / No trade day
      cell.innerHTML = `
        <div class="day-cell-top" style="justify-content: space-between;">
          ${todayTag || '<div></div>'}
          <span class="day-plain-number">${day}</span>
        </div>
        <div class="day-cell-center">
          <div class="day-empty-mark">-</div>
        </div>
        <div class="day-cell-bottom"></div>
      `;
    }

    cell.addEventListener('click', () => {
      openDayDetailModal(dateStr, dayTrades);
    });

    grid.appendChild(cell);
  }

  // Render trailing summary cards immediately after day 31
  renderSummaryCards(grid);
}

function renderSummaryCards(grid) {
  const s = state.stats;
  const pnlSign = s.net_pnl >= 0 ? '+' : '-';
  const monthPnl = `${pnlSign}$${formatMoney(Math.abs(s.net_pnl))}`;

  // 1. Monthly Total Card
  const monthlyCard = document.createElement('div');
  monthlyCard.className = 'summary-card-monthly';
  monthlyCard.innerHTML = `
    <div class="header">
      <span class="title">MONTHLY TOTAL</span>
      <span class="sum-badge">SUM</span>
    </div>
    <div class="pnl">${monthPnl}</div>
    <div class="footer">
      <div><b>${s.total_trades}</b> Trades</div>
      <div class="wr-gold">${s.win_rate}% WR</div>
    </div>
  `;
  grid.appendChild(monthlyCard);

  // 2. Annual Total Card
  const annualSign = s.annual_net_pnl >= 0 ? '+' : '-';
  const annualPnl = `${annualSign}$${formatMoney(Math.abs(s.annual_net_pnl))}`;
  const annualRoiSign = s.annual_roi >= 0 ? '+' : '';

  const annualCard = document.createElement('div');
  annualCard.className = 'summary-card-annual';
  annualCard.innerHTML = `
    <div class="header">
      <div class="title-group">
        <span class="title">ANNUAL TOTAL (${state.currentYear})</span>
      </div>
      <div class="roi-badge">${annualRoiSign}${s.annual_roi}% ROI</div>
    </div>
    <div class="pnl-row">
      <div class="annual-pnl">${annualPnl}</div>
      <div class="annual-wr">${s.annual_win_rate}% Win Rate</div>
    </div>
    <div class="footer">
      <div><b>${s.annual_orders}</b> Total Orders</div>
      <div>${s.annual_wins}W / ${s.annual_losses}L</div>
    </div>
  `;
  grid.appendChild(annualCard);
}

// Modal Handlers
function openModal(id) {
  document.getElementById(id).classList.add('active');
}

function closeModal(id) {
  document.getElementById(id).classList.remove('active');
}

function openAddTradeModal(prefillDate = null) {
  const dateInput = document.getElementById('tradeDateInput');
  const now = new Date();
  
  if (prefillDate) {
    dateInput.value = prefillDate;
  } else {
    // Current date in YYYY-MM-DD
    const y = state.currentYear;
    const m = String(state.currentMonth).padStart(2, '0');
    const d = String(Math.min(now.getDate(), 28)).padStart(2, '0');
    dateInput.value = `${y}-${m}-${d}`;
  }

  setTradeType('BUY');
  document.getElementById('tradeSymbolInput').value = 'XAUUSD';
  document.getElementById('tradeLotsInput').value = '1.0';
  document.getElementById('tradeProfitInput').value = '';
  document.getElementById('tradeNotesInput').value = '';

  openModal('addTradeModal');
}

async function submitNewTrade() {
  const dateVal = document.getElementById('tradeDateInput').value;
  const symbol = document.getElementById('tradeSymbolInput').value.trim().toUpperCase() || 'XAUUSD';
  const lots = parseFloat(document.getElementById('tradeLotsInput').value) || 0.1;
  const profit = parseFloat(document.getElementById('tradeProfitInput').value) || 0.0;
  const comment = document.getElementById('tradeNotesInput').value.trim();

  const tradeData = {
    ticket: `MANUAL-${Date.now()}`,
    symbol: symbol,
    trade_type: state.activeTradeType,
    lots: lots,
    open_price: 0.0,
    close_price: 0.0,
    open_time: `${dateVal} 10:00:00`,
    close_time: `${dateVal} 15:30:00`,
    close_date: dateVal,
    profit: profit,
    commission: 0.0,
    swap: 0.0,
    comment: comment,
    source: 'manual',
    account_type: state.manualAccountType || 'REAL'
  };

  try {
    const res = await fetch('/api/trades', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(tradeData)
    });
    const result = await res.json();
    if (result.success) {
      closeModal('addTradeModal');
      await refreshDashboard();
      showToast('Trade added successfully!', 'success');
    }
  } catch (err) {
    console.error('Failed to save trade:', err);
    showToast('Failed to save trade', 'error');
  }
}

function openDayDetailModal(dateStr, trades) {
  state.selectedDate = dateStr;
  document.getElementById('dayDetailDateTitle').textContent = `Trades for ${dateStr}`;
  const listContainer = document.getElementById('dayTradesList');
  listContainer.innerHTML = '';

  if (trades.length === 0) {
    listContainer.innerHTML = `
      <div style="text-align: center; padding: 24px; color: var(--text-muted);">
        No trades recorded for this day yet.
      </div>
    `;
  } else {
    trades.forEach(t => {
      const item = document.createElement('div');
      item.className = 'trade-item';
      
      const isProfit = t.profit >= 0;
      const pnlColor = isProfit ? 'var(--color-profit)' : 'var(--color-loss)';
      const pnlSign = isProfit ? '+' : '-';
      const formattedPnl = `${pnlSign}$${formatMoney(Math.abs(t.profit))}`;
      const accType = (t.account_type || 'REAL').toUpperCase();

      item.innerHTML = `
        <div class="trade-item-left">
          <span class="trade-badge ${t.trade_type.toLowerCase()}">${t.trade_type}</span>
          <div>
            <div class="trade-symbol" style="display: flex; align-items: center; gap: 8px;">
              <span>${t.symbol}</span>
              <span class="trade-acc-badge ${accType.toLowerCase()}">${accType}</span>
            </div>
            <div class="trade-lots">${t.lots} Lots • ${t.comment || t.source}</div>
          </div>
        </div>
        <div class="trade-item-right">
          <div class="trade-item-pnl" style="color: ${pnlColor};">${formattedPnl}</div>
          <button class="trade-delete-btn" title="Delete Trade" onclick="deleteTradeItem(${t.id})">
            <svg width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
            </svg>
          </button>
        </div>
      `;
      listContainer.appendChild(item);
    });
  }

  openModal('dayDetailModal');
}

async function deleteTradeItem(tradeId) {
  if (confirm('Are you sure you want to delete this trade?')) {
    try {
      await fetch(`/api/trades/${tradeId}`, { method: 'DELETE' });
      closeModal('dayDetailModal');
      await refreshDashboard();
      showToast('Trade deleted', 'success');
    } catch (err) {
      console.error(err);
      showToast('Failed to delete trade', 'error');
    }
  }
}

// MT5 Real-time status checker
async function checkMT5LiveStatus() {
  try {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 2500);
    const res = await fetch('/api/mt5/status', { signal: controller.signal });
    clearTimeout(timeoutId);
    if (!res.ok) return;
    const data = await res.json();
    const statusText = document.getElementById('mt5StatusText');
    const pulseDot = document.getElementById('mt5PulseDot');
    
    const stored = data.stored_account;
    if (stored && stored.account_number) {
      const typeStr = stored.account_type || 'REAL';
      statusText.textContent = `MT5: ${stored.account_number} [${typeStr}]`;
      pulseDot.style.background = (typeStr === 'REAL') ? 'var(--color-profit)' : 'var(--color-gold)';
      pulseDot.style.boxShadow = `0 0 8px ${pulseDot.style.background}`;
    } else if (data.connected && data.account_logged_in) {
      statusText.textContent = `MT5: ${data.account_number}`;
      pulseDot.style.background = 'var(--color-profit)';
      pulseDot.style.boxShadow = '0 0 8px var(--color-profit)';
    } else if (data.connected && data.terminal_running) {
      statusText.textContent = 'MT5 Terminal Active';
      pulseDot.style.background = 'var(--color-gold)';
    } else {
      statusText.textContent = 'MT5 Connect';
      pulseDot.style.background = '#64748b';
      pulseDot.style.boxShadow = 'none';
    }
  } catch (err) {
    // API starting, timeout, or offline
  }
}

// Helpers
function formatMoney(amount) {
  if (amount === undefined || amount === null || isNaN(amount)) return '0.00';
  return Number(amount).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}

function showToast(message, type = 'info') {
  let toast = document.getElementById('appToast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'appToast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.className = `toast show ${type}`;
  setTimeout(() => {
    toast.className = 'toast';
  }, 3500);
}
