"""
DingJourney - SQLite Database Layer
Stores trades, accounts, and application configuration.
"""

import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dingjourney.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Configuration table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS config (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)
    
    # Trades table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ticket TEXT UNIQUE,
        symbol TEXT NOT NULL,
        trade_type TEXT NOT NULL, -- BUY or SELL
        lots REAL NOT NULL,
        open_price REAL,
        close_price REAL,
        open_time TEXT,
        close_time TEXT NOT NULL, -- YYYY-MM-DD HH:MM:SS
        close_date TEXT NOT NULL, -- YYYY-MM-DD for indexing
        profit REAL NOT NULL,     -- Net profit/loss in $
        commission REAL DEFAULT 0.0,
        swap REAL DEFAULT 0.0,
        comment TEXT DEFAULT '',
        source TEXT DEFAULT 'manual', -- 'mt5_api', 'mt5_ea', 'mt5_import', 'manual'
        account_type TEXT DEFAULT 'REAL',
        account_number TEXT DEFAULT '',
        account_id TEXT DEFAULT '',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Accounts / MT5 info
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mt5_account (
        id INTEGER PRIMARY KEY,
        account_number TEXT,
        broker TEXT,
        server TEXT,
        currency TEXT DEFAULT 'USD',
        balance REAL DEFAULT 0.0,
        equity REAL DEFAULT 0.0,
        account_type TEXT DEFAULT 'REAL', -- 'REAL' or 'DEMO'
        last_sync TEXT
    )
    """)
    # Try adding columns if table already exists
    try:
        cursor.execute("ALTER TABLE mt5_account ADD COLUMN account_type TEXT DEFAULT 'REAL'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE trades ADD COLUMN account_type TEXT DEFAULT 'REAL'")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE trades ADD COLUMN account_number TEXT DEFAULT ''")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE trades ADD COLUMN account_id TEXT DEFAULT ''")
    except Exception:
        pass

    # Ensure phone trades have profit 2000.0 and correct account_id
    try:
        cursor.execute("UPDATE trades SET profit = 2000.0, account_id = 'phone_416474026', account_number = 'phone_416474026' WHERE ticket LIKE 'phone_%'")
        cursor.execute("UPDATE trades SET profit = 300.0, account_id = 'pc_account', account_number = 'pc_account' WHERE ticket LIKE 'pc_%'")
    except Exception:
        pass

    # Seed default config safely
    defaults = [
        ('starting_capital', '10000.00'),
        ('account_name', 'Base Account'),
        ('account_type', 'REAL'),
        ('currency', '$'),
        ('sync_pin', '77778888'),
        ('target_account', '416474026')
    ]
    for k, v in defaults:
        cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES (?, ?)", (k, v))

    # Seed initial real trades if database is completely empty
    cursor.execute("SELECT COUNT(*) FROM trades")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
        INSERT INTO trades (ticket, symbol, trade_type, lots, open_price, close_price, open_time, close_time, close_date, profit, commission, swap, comment, source, account_type, account_number, account_id)
        VALUES 
        ('phone_416474026_MANUAL-1792770710272', 'XAUUSD', 'BUY', 1.0, 0.0, 0.0, '2026-10-23 10:00:00', '2026-10-23 15:30:00', '2026-10-23', 2000.0, 0.0, 0.0, '', 'manual', 'REAL', 'phone_416474026', 'phone_416474026'),
        ('pc_account_MANUAL-1792770724145', 'XAUUSD', 'BUY', 1.0, 0.0, 0.0, '2026-10-23 10:00:00', '2026-10-23 15:30:00', '2026-10-23', 300.0, 0.0, 0.0, '', 'manual', 'REAL', 'pc_account', 'pc_account')
        """)
        
    conn.commit()
    conn.close()


def get_config() -> Dict[str, str]:
    conn = get_db_connection()
    rows = conn.execute("SELECT key, value FROM config").fetchall()
    conn.close()
    return {row["key"]: row["value"] for row in rows}

def set_config(key: str, value: str):
    conn = get_db_connection()
    conn.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()

def get_trades(year: Optional[int] = None, month: Optional[int] = None, account_type: Optional[str] = None, account_id: Optional[str] = None) -> List[Dict[str, Any]]:
    conn = get_db_connection()
    conditions = []
    params = []
    
    if year and month:
        prefix = f"{year:04d}-{month:02d}-%"
        conditions.append("close_date LIKE ?")
        params.append(prefix)
    elif year:
        prefix = f"{year:04d}-%"
        conditions.append("close_date LIKE ?")
        params.append(prefix)

    if account_type and account_type.upper() in ("REAL", "DEMO"):
        conditions.append("UPPER(account_type) = ?")
        params.append(account_type.upper())

    if account_id and account_id.strip():
        acc = account_id.strip()
        conditions.append("(account_id = ? OR account_number = ?)")
        params.append(acc)
        params.append(acc)
        
    query = "SELECT * FROM trades"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
        
    query += " ORDER BY close_time DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def insert_or_update_trade(trade: Dict[str, Any]) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    close_time = trade.get("close_time", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    close_date = trade.get("close_date") or close_time.split(" ")[0]
    
    raw_ticket = str(trade.get("ticket") or int(datetime.now().timestamp() * 1000)).strip()
    account_type = str(trade.get("account_type", "REAL")).upper()
    account_id = str(trade.get("account_id") or trade.get("account_number", "")).strip()
    account_number = str(trade.get("account_number") or account_id).strip()
    
    # Composite ticket identifier to isolate across different MT5 accounts
    prefix = account_number or account_id
    if prefix and not raw_ticket.startswith(f"{prefix}_"):
        ticket = f"{prefix}_{raw_ticket}"
    else:
        ticket = raw_ticket
    
    cursor.execute("""
    INSERT INTO trades (ticket, symbol, trade_type, lots, open_price, close_price, open_time, close_time, close_date, profit, commission, swap, comment, source, account_type, account_number, account_id)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(ticket) DO UPDATE SET
        symbol = excluded.symbol,
        trade_type = excluded.trade_type,
        lots = excluded.lots,
        open_price = excluded.open_price,
        close_price = excluded.close_price,
        close_time = excluded.close_time,
        close_date = excluded.close_date,
        profit = excluded.profit,
        commission = excluded.commission,
        swap = excluded.swap,
        comment = excluded.comment,
        source = excluded.source,
        account_type = excluded.account_type,
        account_number = excluded.account_number,
        account_id = excluded.account_id
    """, (
        ticket,
        trade.get("symbol", "UNKNOWN").upper(),
        trade.get("trade_type", "BUY").upper(),
        float(trade.get("lots", 0.01)),
        float(trade.get("open_price", 0.0)),
        float(trade.get("close_price", 0.0)),
        trade.get("open_time", close_time),
        close_time,
        close_date,
        float(trade.get("profit", 0.0)),
        float(trade.get("commission", 0.0)),
        float(trade.get("swap", 0.0)),
        trade.get("comment", ""),
        trade.get("source", "manual"),
        account_type,
        account_number,
        account_id
    ))
    conn.commit()
    trade_id = cursor.lastrowid
    conn.close()
    return trade_id

def delete_trade(trade_id: int):
    conn = get_db_connection()
    conn.execute("DELETE FROM trades WHERE id = ?", (trade_id,))
    conn.commit()
    conn.close()

def clear_all_trades(account_type: Optional[str] = None, account_id: Optional[str] = None):
    conn = get_db_connection()
    conditions = []
    params = []
    if account_type and account_type.upper() in ("REAL", "DEMO"):
        conditions.append("UPPER(account_type) = ?")
        params.append(account_type.upper())
    if account_id and account_id.strip():
        conditions.append("(account_id = ? OR account_number = ?)")
        params.append(account_id.strip())
        params.append(account_id.strip())
    
    query = "DELETE FROM trades"
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    conn.execute(query, params)
    conn.commit()
    conn.close()

def get_stats(year: Optional[int] = None, month: Optional[int] = None, account_type: Optional[str] = None, account_id: Optional[str] = None) -> Dict[str, Any]:
    trades = get_trades(year=year, month=month, account_type=account_type, account_id=account_id)
    all_year_trades = get_trades(year=year, account_type=account_type, account_id=account_id) if year else trades
    config = get_config()
    
    acc_key = (account_id or "").strip()
    type_key = (account_type or "REAL").lower().strip()
    
    if acc_key:
        cap_val = config.get(f"starting_capital_{acc_key}_{type_key}") or config.get(f"starting_capital_{acc_key}")
    else:
        cap_val = None
    if not cap_val:
        cap_val = config.get(f"starting_capital_{type_key}") or config.get("starting_capital", 10000.0)
    starting_capital = float(cap_val)
    
    if acc_key:
        account_name = config.get(f"account_name_{acc_key}_{type_key}") or config.get(f"account_name_{acc_key}") or ("📱 Phone Account" if "phone" in acc_key else ("💻 PC Account" if "pc" in acc_key else f"Account #{acc_key}"))
    else:
        account_name = config.get(f"account_name_{type_key}") or config.get("account_name", "Base Account")
    
    # 1. Day-based Evaluation: Each trading day counts as 1 unit
    # (e.g. 7 positions on same day with net loss = 1 Loss (1L))
    day_pnl_map = {}
    for t in trades:
        date_key = t["close_date"]
        day_pnl_map[date_key] = day_pnl_map.get(date_key, 0.0) + float(t["profit"])
    
    total_days_count = len(day_pnl_map)
    winning_days = [p for p in day_pnl_map.values() if p > 0]
    losing_days = [p for p in day_pnl_map.values() if p < 0]
    breakeven_days = [p for p in day_pnl_map.values() if p == 0]
    
    wins_count = len(winning_days)
    losses_count = len(losing_days)
    be_count = len(breakeven_days)
    
    # Financial metrics across all individual trades
    winning_trades = [t for t in trades if t["profit"] > 0]
    losing_trades = [t for t in trades if t["profit"] < 0]
    gross_win = sum(t["profit"] for t in winning_trades)
    gross_loss = abs(sum(t["profit"] for t in losing_trades))
    net_pnl = gross_win - gross_loss
    
    # Win rate based on Trading Days
    win_rate = (wins_count / total_days_count * 100) if total_days_count > 0 else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (gross_win if gross_win > 0 else 0.0)
    
    # ROI & Live Balance
    pnl_percentage = (net_pnl / starting_capital * 100) if starting_capital > 0 else 0.0
    current_balance = starting_capital + net_pnl

    conn = get_db_connection()
    mt5_row = None
    if acc_key and account_type:
        mt5_row = conn.execute("SELECT balance, equity FROM mt5_account WHERE (account_number = ? OR account_type = ?) AND UPPER(account_type) = ?", (acc_key, account_type.upper(), account_type.upper())).fetchone()
    elif account_type:
        mt5_row = conn.execute("SELECT balance, equity FROM mt5_account WHERE UPPER(account_type) = ?", (account_type.upper(),)).fetchone()
    else:
        mt5_row = conn.execute("SELECT balance, equity FROM mt5_account WHERE id = 1").fetchone()
    conn.close()
    if mt5_row and mt5_row["balance"] is not None:
        current_balance = float(mt5_row["balance"])
    
    # Annual Stats (Day-based evaluation as well)
    annual_day_pnl_map = {}
    for t in all_year_trades:
        date_key = t["close_date"]
        annual_day_pnl_map[date_key] = annual_day_pnl_map.get(date_key, 0.0) + float(t["profit"])
    
    annual_wins = [p for p in annual_day_pnl_map.values() if p > 0]
    annual_losses = [p for p in annual_day_pnl_map.values() if p < 0]
    annual_net_pnl = sum(t["profit"] for t in all_year_trades)
    annual_days = len(annual_day_pnl_map)
    annual_wr = (len(annual_wins) / annual_days * 100) if annual_days > 0 else 0.0
    annual_roi = (annual_net_pnl / starting_capital * 100) if starting_capital > 0 else 0.0
    
    return {
        "starting_capital": starting_capital,
        "current_balance": current_balance,
        "net_pnl": net_pnl,
        "pnl_percentage": pnl_percentage,
        "total_trades": total_days_count, # Total trading days
        "total_positions": len(trades),
        "wins": wins_count,
        "losses": losses_count,
        "breakeven": be_count,
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "gross_win": round(gross_win, 2),
        "gross_loss": round(gross_loss, 2),
        "account_type": account_type or config.get("account_type", "REAL"),
        "account_name": account_name,
        # Annual breakdown
        "annual_net_pnl": annual_net_pnl,
        "annual_roi": round(annual_roi, 1),
        "annual_orders": annual_days,
        "annual_wins": len(annual_wins),
        "annual_losses": len(annual_losses),
        "annual_win_rate": round(annual_wr, 1)
    }
