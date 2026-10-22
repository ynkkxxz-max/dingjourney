"""
DingJourney - MetaTrader 5 Sync Engine
Connects directly to the Windows MT5 desktop terminal using official MetaTrader5 Python API.
Supports direct Account Login (Login, Password, Server) with auto-reconnection and deal synchronization.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from .database import insert_or_update_trade, get_db_connection, get_config, set_config

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    MT5_AVAILABLE = False

DEFAULT_MT5_PATH = r"C:\Program Files\MetaTrader 5\terminal64.exe"


def check_mt5_installed() -> Dict[str, Any]:
    return {
        "available": MT5_AVAILABLE,
        "message": "MetaTrader5 Python module is installed and ready." if MT5_AVAILABLE else "MetaTrader5 Python module not installed."
    }


def get_mt5_status() -> Dict[str, Any]:
    if not MT5_AVAILABLE:
        return {"connected": False, "error": "MT5 module missing"}
    
    try:
        terminal_info = mt5.terminal_info()
        if terminal_info is None:
            return {"connected": False, "error": "Terminal not running or not initialized"}
        account = mt5.account_info()
        if account is None:
            return {"connected": True, "terminal_running": True, "account_logged_in": False}
        return {
            "connected": True,
            "terminal_running": True,
            "account_logged_in": True,
            "account_number": str(account.login),
            "broker": account.company,
            "server": account.server,
            "currency": account.currency,
            "balance": account.balance,
            "equity": account.equity
        }
    except Exception as e:
        return {"connected": False, "error": str(e)}


def get_stored_credentials() -> Dict[str, Any]:
    config = get_config()
    return {
        "login": config.get("mt5_login", ""),
        "server": config.get("mt5_server", ""),
        "path": config.get("mt5_path", DEFAULT_MT5_PATH)
    }


def connect_and_login_mt5(login: Optional[int] = None, password: Optional[str] = None, server: Optional[str] = None, path: Optional[str] = None) -> Dict[str, Any]:
    """
    Connect to MT5. If no password provided, connects directly to active MT5 terminal without asking for password!
    """
    if not MT5_AVAILABLE:
        return {
            "success": False,
            "error": "MetaTrader5 Python module is not installed."
        }

    # If neither login nor password provided, perform active terminal sync
    if not login and not password:
        return sync_active_terminal()

    target_path = path or DEFAULT_MT5_PATH
    if not os.path.exists(target_path):
        target_path = None # Let mt5 auto-locate

    try:
        mt5.shutdown()
    except Exception:
        pass

    # 1. Initialize
    init_kwargs = {}
    if target_path:
        init_kwargs["path"] = target_path

    login_kwargs = {}
    if login:
        login_kwargs["login"] = int(login)
    if server:
        login_kwargs["server"] = server
    if password:
        login_kwargs["password"] = password

    # Try initializing with login credentials directly
    init_ok = mt5.initialize(**init_kwargs, **login_kwargs)

    if not init_ok:
        # Fallback: try initialize first, then login
        init_ok = mt5.initialize(**init_kwargs) if init_kwargs else mt5.initialize()
        if not init_ok:
            err = mt5.last_error()
            return {
                "success": False,
                "error": f"Failed to open MT5 Terminal: {err}. Please ensure MT5 is installed and running."
            }
        
        login_ok = mt5.login(**login_kwargs)
        if not login_ok:
            err = mt5.last_error()
            mt5.shutdown()
            return {
                "success": False,
                "error": f"MT5 Login failed: {err}. Please verify your Login ID and Server Name in MT5."
            }

    # Fetch Account Info
    account = mt5.account_info()
    if account is None:
        err = mt5.last_error()
        mt5.shutdown()
        return {
            "success": False,
            "error": f"Connected to MT5, but could not retrieve account information: {err}"
        }

    # Detect whether account is REAL or DEMO
    trade_mode = getattr(account, "trade_mode", 2)
    account_type = "REAL" if trade_mode == 2 else "DEMO"
    set_config("account_type", account_type)

    # Save credentials (excluding password for security)
    set_config("mt5_login", str(login))
    set_config("mt5_server", server)
    if target_path:
        set_config("mt5_path", target_path)

    # Save Account in DB
    conn = get_db_connection()
    conn.execute("""
    INSERT OR REPLACE INTO mt5_account (id, account_number, broker, server, currency, balance, equity, account_type, last_sync)
    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(account.login),
        account.company,
        account.server,
        account.currency,
        account.balance,
        account.equity,
        account_type,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()

    # Automatically sync deals
    sync_res = _pull_mt5_deals(days_back=180, account_type=account_type, account_number=str(account.login))

    # Note: Keep connection alive or shutdown gracefully
    mt5.shutdown()

    return {
        "success": True,
        "account": {
            "login": account.login,
            "broker": account.company,
            "server": account.server,
            "currency": account.currency,
            "balance": round(account.balance, 2),
            "equity": round(account.equity, 2),
            "profit": round(account.profit, 2),
            "leverage": account.leverage,
            "account_type": account_type
        },
        "synced_trades": sync_res.get("synced_count", 0),
        "message": f"Successfully connected to account {account.login} ({account.company})! Synced {sync_res.get('synced_count', 0)} trades."
    }


def sync_active_terminal(days_back: int = 180, target_account: Optional[str] = None, sync_pin: Optional[str] = None) -> Dict[str, Any]:
    """
    Sync trades directly from the currently active/running MT5 terminal.
    Verifies Sync PIN and Target Account to prevent collisions across multiple MT5 instances.
    """
    if not MT5_AVAILABLE:
        return {"success": False, "error": "MetaTrader5 module is not installed."}

    # 1. Verify Sync PIN if provided
    saved_pin = get_config().get("sync_pin", "JN-8899").strip()
    if sync_pin and sync_pin.strip() != saved_pin:
        return {
            "success": False,
            "error": "❌ លេខកូដសម្ងាត់ Sync PIN មិនត្រឹមត្រូវឡើយ! (Invalid Sync PIN)"
        }

    # 2. Connect to active terminal (Try without path first to attach to active terminal)
    initialized = mt5.initialize()
    if not initialized and os.path.exists(DEFAULT_MT5_PATH):
        initialized = mt5.initialize(path=DEFAULT_MT5_PATH)

    if not initialized:
        err = mt5.last_error()
        if err and len(err) > 0 and err[0] == -6:
            return {
                "success": False,
                "error": "MT5 លើ PC មិនទាន់ Login ជាប់នៅឡើយទេ! សូមបើកកម្មវិធី MT5 លើកុំព្យូទ័រ -> File -> Login to Trade Account -> ធីកលើ 'Save password' រួចចុច Connect ម្ដងទៀត។"
            }
        return {
            "success": False,
            "error": f"មិនអាចភ្ជាប់ទៅកាន់ MT5 បានទេ ({err})។ សូមប្រាកដថាកម្មវិធី MetaTrader 5 កំពុងបើកនៅលើកុំព្យូទ័រ Windows របស់អ្នក។"
        }

    account = mt5.account_info()
    if account is None:
        err = mt5.last_error()
        mt5.shutdown()
        return {
            "success": False,
            "error": "កម្មវិធី MT5 កំពុងបើកពិតមែន តែមិនទាន់មានគណនី Login ឡើយ។ សូម Login ចូលគណនីរបស់អ្នកក្នុង MT5 ជាមុនសិន។"
        }

    # 3. Target Account Collision Check
    current_login = str(account.login).strip()
    expected_target = (target_account or get_config().get("target_account", "")).strip()
    if expected_target and current_login != expected_target:
        mt5.shutdown()
        return {
            "success": False,
            "error": f"⚠️ MT5 កំពុងដំណើរការគណនី [{current_login}] ({account.company}) ដែលខុសពីលេខសម្គាល់គណនីគោលដៅ [{expected_target}] របស់អ្នក! សូមប្តូរចូលគណនីឱ្យបានត្រឹមត្រូវសិន ដើម្បីការពារកុំឱ្យជាន់ទិន្នន័យគ្នា។",
            "detected_account": current_login,
            "target_account": expected_target
        }

    # Auto-bind target account if not set yet
    if not expected_target:
        set_config("target_account", current_login)

    # Detect whether account is REAL or DEMO
    trade_mode = getattr(account, "trade_mode", 2)
    account_type = "REAL" if trade_mode == 2 else "DEMO"
    set_config("account_type", account_type)

    # Update account in DB
    conn = get_db_connection()
    conn.execute("""
    INSERT OR REPLACE INTO mt5_account (id, account_number, broker, server, currency, balance, equity, account_type, last_sync)
    VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        str(account.login),
        account.company,
        account.server,
        account.currency,
        account.balance,
        account.equity,
        account_type,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    conn.commit()
    conn.close()

    sync_res = _pull_mt5_deals(days_back=days_back, account_type=account_type, account_number=str(account.login))
    mt5.shutdown()

    return {
        "success": True,
        "synced_trades": sync_res.get("synced_count", 0),
        "account": {
            "login": account.login,
            "broker": account.company,
            "server": account.server,
            "balance": account.balance,
            "equity": account.equity,
            "currency": account.currency,
            "account_type": account_type
        }
    }


def _pull_mt5_deals(days_back: int = 180, account_type: str = "REAL", account_number: str = "") -> Dict[str, Any]:
    from_date = datetime.now() - timedelta(days=days_back)
    to_date = datetime.now() + timedelta(days=1)

    deals = mt5.history_deals_get(from_date, to_date)
    if deals is None:
        return {"synced_count": 0, "error": str(mt5.last_error())}

    synced_count = 0
    for deal in deals:
        if deal.type not in (0, 1): # Only BUY / SELL deals
            continue

        if deal.entry in (1, 2, 3) or deal.profit != 0:
            deal_time = datetime.fromtimestamp(deal.time)
            close_time_str = deal_time.strftime("%Y-%m-%d %H:%M:%S")
            close_date_str = deal_time.strftime("%Y-%m-%d")
            action_type = "SELL" if deal.type == 1 else "BUY"

            trade_record = {
                "ticket": str(deal.ticket),
                "symbol": deal.symbol,
                "trade_type": action_type,
                "lots": deal.volume,
                "open_price": deal.price,
                "close_price": deal.price,
                "open_time": close_time_str,
                "close_time": close_time_str,
                "close_date": close_date_str,
                "profit": round(deal.profit, 2),
                "commission": round(deal.commission, 2),
                "swap": round(deal.swap, 2),
                "comment": deal.comment or "MT5 Live Deal",
                "source": "mt5_api",
                "account_type": account_type,
                "account_number": account_number
            }
            insert_or_update_trade(trade_record)
            synced_count += 1

    return {"synced_count": synced_count}


def get_current_account_info() -> Dict[str, Any]:
    """Retrieve saved account from database."""
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM mt5_account WHERE id = 1").fetchone()
    conn.close()
    if row:
        return dict(row)
    return {}
