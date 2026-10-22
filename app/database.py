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

    # Update demo trades to DEMO account_type
    try:
        cursor.execute("UPDATE trades SET account_type = 'DEMO' WHERE source = 'demo' OR ticket IN ('152620448744', '152620460980')")
    except Exception:
        pass

    # Seed default config if empty
    cursor.execute("SELECT value FROM config WHERE key = 'starting_capital'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO config (key, value) VALUES ('starting_capital', '10000.00')")
        cursor.execute("INSERT INTO config (key, value) VALUES ('account_name', 'Base Account')")
        cursor.execute("INSERT INTO config (key, value) VALUES ('account_type', 'REAL')")
        cursor.execute("INSERT INTO config (key, value) VALUES ('currency', '$')")

    # Seed Sync PIN & Bound Target Account
    cursor.execute("SELECT value FROM config WHERE key = 'sync_pin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO config (key, value) VALUES ('sync_pin', 'JN-8899')")
    cursor.execute("SELECT value FROM config WHERE key = 'target_account'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO config (key, value) VALUES ('target_account', '')")

    # Seed sample trades matching the screenshot if no trades exist yet
    cursor.execute("SELECT COUNT(*) as count FROM trades")
    if cursor.fetchone()["count"] == 0:
        seed_sample_trades(cursor)
        
    conn.commit()
    conn.close()

def seed_sample_trades(cursor):
    """Seed the trades shown in the screenshot for October 2026 so user immediately sees their dashboard!"""
    sample_trades = [
        # Mon Oct 1 2026 (or Thu Oct 1 depending on calendar, matches screenshot: Mon 1st: +815.00)
        ("100101", "XAUUSD", "BUY", 1.0, 2650.0, 2658.15, "2026-10-01 08:30:00", "2026-10-01 14:45:00", "2026-10-01", 815.00, -5.0, 0.0, "Trend break"),
        ("100102", "EURUSD", "SELL", 2.0, 1.0920, 1.0932, "2026-10-02 10:15:00", "2026-10-02 16:30:00", "2026-10-02", -250.00, -6.0, 0.0, "Pullback stop hit"),
        ("100105", "XAUUSD", "BUY", 0.5, 2655.0, 2661.40, "2026-10-05 09:00:00", "2026-10-05 15:20:00", "2026-10-05", 320.00, -3.0, 0.0, "London breakout"),
        ("100106", "BTCUSD", "BUY", 0.2, 65000.0, 68750.0, "2026-10-06 11:00:00", "2026-10-06 20:00:00", "2026-10-06", 750.00, -4.0, 0.0, "Weekend momentum"),
        ("100108", "GBPUSD", "SELL", 1.5, 1.3050, 1.3070, "2026-10-08 08:00:00", "2026-10-08 11:30:00", "2026-10-08", -300.00, -5.0, 0.0, "News volatility"),
        ("100112", "US30", "BUY", 0.2, 42000.0, 42110.0, "2026-10-12 14:30:00", "2026-10-12 17:00:00", "2026-10-12", 220.00, -2.0, 0.0, "US session sweep"),
        ("100114", "XAUUSD", "BUY", 1.2, 2660.0, 2667.50, "2026-10-14 13:00:00", "2026-10-14 19:30:00", "2026-10-14", 900.00, -6.0, 0.0, "Gold rally TP hit"),
        ("100115", "USDJPY", "BUY", 1.0, 149.50, 149.35, "2026-10-15 07:30:00", "2026-10-15 12:10:00", "2026-10-15", -130.00, -4.0, 0.0, "Resistance rejection")
    ]
    for t in sample_trades:
        cursor.execute("""
        INSERT OR IGNORE INTO trades (ticket, symbol, trade_type, lots, open_price, close_price, open_time, close_time, close_date, profit, commission, swap, comment, source)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'demo')
        """, t)

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

def get_trades(year: Optional[int] = None, month: Optional[int] = None, account_type: Optional[str] = None) -> List[Dict[str, Any]]:
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
    account_number = str(trade.get("account_number", "")).strip()
    
    # Composite ticket identifier to isolate across different MT5 accounts
    if account_number and not raw_ticket.startswith(f"{account_number}_"):
        ticket = f"{account_number}_{raw_ticket}"
    else:
        ticket = raw_ticket
    
    cursor.execute("""
    INSERT INTO trades (ticket, symbol, trade_type, lots, open_price, close_price, open_time, close_time, close_date, profit, commission, swap, comment, source, account_type, account_number)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
        account_number = excluded.account_number
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
        account_number
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

def clear_all_trades(account_type: Optional[str] = None):
    conn = get_db_connection()
    if account_type and account_type.upper() in ("REAL", "DEMO"):
        conn.execute("DELETE FROM trades WHERE UPPER(account_type) = ?", (account_type.upper(),))
    else:
        conn.execute("DELETE FROM trades")
    conn.commit()
    conn.close()

def get_stats(year: Optional[int] = None, month: Optional[int] = None, account_type: Optional[str] = None) -> Dict[str, Any]:
    trades = get_trades(year=year, month=month, account_type=account_type)
    all_year_trades = get_trades(year=year, account_type=account_type) if year else trades
    config = get_config()
    
    starting_capital = float(config.get("starting_capital", 10000.0))
    
    # Calculate stats for the selected period (month or year)
    total_trades = len(trades)
    winning_trades = [t for t in trades if t["profit"] > 0]
    losing_trades = [t for t in trades if t["profit"] < 0]
    breakeven_trades = [t for t in trades if t["profit"] == 0]
    
    wins_count = len(winning_trades)
    losses_count = len(losing_trades)
    be_count = len(breakeven_trades)
    
    gross_win = sum(t["profit"] for t in winning_trades)
    gross_loss = abs(sum(t["profit"] for t in losing_trades))
    net_pnl = gross_win - gross_loss
    
    win_rate = (wins_count / total_trades * 100) if total_trades > 0 else 0.0
    profit_factor = (gross_win / gross_loss) if gross_loss > 0 else (gross_win if gross_win > 0 else 0.0)
    
    # ROI & Balance
    pnl_percentage = (net_pnl / starting_capital * 100) if starting_capital > 0 else 0.0
    current_balance = starting_capital + net_pnl
    
    # Annual Stats
    annual_wins = [t for t in all_year_trades if t["profit"] > 0]
    annual_losses = [t for t in all_year_trades if t["profit"] < 0]
    annual_net_pnl = sum(t["profit"] for t in all_year_trades)
    annual_orders = len(all_year_trades)
    annual_wr = (len(annual_wins) / annual_orders * 100) if annual_orders > 0 else 0.0
    annual_roi = (annual_net_pnl / starting_capital * 100) if starting_capital > 0 else 0.0
    
    return {
        "starting_capital": starting_capital,
        "current_balance": current_balance,
        "net_pnl": net_pnl,
        "pnl_percentage": pnl_percentage,
        "total_trades": total_trades,
        "wins": wins_count,
        "losses": losses_count,
        "breakeven": be_count,
        "win_rate": round(win_rate, 1),
        "profit_factor": round(profit_factor, 2),
        "gross_win": round(gross_win, 2),
        "gross_loss": round(gross_loss, 2),
        "account_type": config.get("account_type", "REAL"),
        "account_name": config.get("account_name", "Base Account"),
        # Annual breakdown
        "annual_net_pnl": annual_net_pnl,
        "annual_roi": round(annual_roi, 1),
        "annual_orders": annual_orders,
        "annual_wins": len(annual_wins),
        "annual_losses": len(annual_losses),
        "annual_win_rate": round(annual_wr, 1)
    }
