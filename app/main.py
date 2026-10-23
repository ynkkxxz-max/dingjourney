"""
DingJourney - Main FastAPI Backend Application
Trading Calendar Dashboard & MetaTrader 5 Sync
"""

import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .database import (
    init_db,
    get_trades,
    insert_or_update_trade,
    delete_trade,
    get_stats,
    get_config,
    set_config,
    clear_all_trades
)
from .mt5_sync import (
    check_mt5_installed,
    get_mt5_status,
    connect_and_login_mt5,
    sync_active_terminal,
    get_current_account_info,
    get_stored_credentials
)
from .report_parser import parse_csv_statement, parse_html_statement

# Initialize DB
init_db()

app = FastAPI(title="Journa NextGen Trading Journal", version="1.0.0")

# CORS middleware for mobile/iOS access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")


# Pydantic models
class TradeModel(BaseModel):
    ticket: Optional[str] = None
    symbol: str
    trade_type: str # BUY or SELL
    lots: float
    open_price: Optional[float] = 0.0
    close_price: Optional[float] = 0.0
    open_time: Optional[str] = None
    close_time: Optional[str] = None
    close_date: Optional[str] = None
    profit: float
    commission: Optional[float] = 0.0
    swap: Optional[float] = 0.0
    comment: Optional[str] = ""
    source: Optional[str] = "manual"
    account_type: Optional[str] = "REAL"
    account_number: Optional[str] = ""

class ConfigModel(BaseModel):
    starting_capital: Optional[float] = None
    account_name: Optional[str] = None
    account_type: Optional[str] = None
    currency: Optional[str] = None
    sync_pin: Optional[str] = None
    target_account: Optional[str] = None

class MT5SyncModel(BaseModel):
    days_back: Optional[int] = 180
    login: Optional[int] = None
    password: Optional[str] = None
    server: Optional[str] = None
    target_account: Optional[str] = None
    sync_pin: Optional[str] = None


@app.api_route("/health", methods=["GET", "HEAD"])
def health_check():
    return {"status": "ok", "app": "Journa NextGen", "timestamp": str(os.getenv("RENDER_GIT_COMMIT", "live"))}


@app.get("/api/status")
def api_status():
    return {
        "status": "online",
        "app": "Journa NextGen",
        "version": "1.0.0",
        "mt5_module": check_mt5_installed()
    }


@app.get("/api/config")
def api_get_config():
    return get_config()


@app.post("/api/config")
def api_save_config(config: ConfigModel):
    acc_type = (config.account_type or "").lower().strip()
    if config.starting_capital is not None:
        if acc_type in ("real", "demo"):
            set_config(f"starting_capital_{acc_type}", str(config.starting_capital))
        set_config("starting_capital", str(config.starting_capital))
    if config.account_name is not None:
        if acc_type in ("real", "demo"):
            set_config(f"account_name_{acc_type}", config.account_name)
        set_config("account_name", config.account_name)
    if config.account_type is not None:
        set_config("account_type", config.account_type)
    if config.currency is not None:
        set_config("currency", config.currency)
    if config.sync_pin is not None:
        set_config("sync_pin", config.sync_pin.strip())
    if config.target_account is not None:
        set_config("target_account", config.target_account.strip())
    return {"success": True, "config": get_config()}


@app.get("/api/trades")
def api_get_trades(year: Optional[int] = None, month: Optional[int] = None, account_type: Optional[str] = None):
    trades = get_trades(year=year, month=month, account_type=account_type)
    return {"trades": trades}


@app.post("/api/trades")
def api_save_trade(trade: TradeModel):
    trade_id = insert_or_update_trade(trade.dict())
    return {"success": True, "id": trade_id}


@app.delete("/api/trades/{trade_id}")
def api_delete_trade(trade_id: int):
    delete_trade(trade_id)
    return {"success": True}


@app.post("/api/trades/clear")
def api_clear_trades(account_type: Optional[str] = None):
    clear_all_trades(account_type=account_type)
    return {"success": True}


@app.get("/api/stats")
def api_get_stats(year: Optional[int] = None, month: Optional[int] = None, account_type: Optional[str] = None):
    stats = get_stats(year=year, month=month, account_type=account_type)
    return stats


# MT5 Endpoints
class MT5LoginModel(BaseModel):
    login: Optional[int] = None
    password: Optional[str] = None
    server: Optional[str] = None
    path: Optional[str] = None
    account_type: Optional[str] = "REAL"
    days_back: Optional[int] = 180

@app.get("/api/mt5/status")
def api_mt5_status():
    status = get_mt5_status()
    stored_acc = get_current_account_info()
    return {**status, "stored_account": stored_acc}

@app.get("/api/mt5/credentials")
def api_mt5_credentials():
    return get_stored_credentials()

@app.post("/api/mt5/login")
def api_mt5_login(creds: MT5LoginModel):
    result = connect_and_login_mt5(
        login=creds.login,
        password=creds.password,
        server=creds.server,
        path=creds.path
    )
    return result

@app.post("/api/mt5/sync")
def api_mt5_sync(body: MT5SyncModel):
    result = sync_active_terminal(
        days_back=body.days_back or 180,
        target_account=body.target_account,
        sync_pin=body.sync_pin
    )
    return result


@app.post("/api/mt5/webhook")
def api_mt5_webhook(payload: Dict[str, Any]):
    """
    Webhook endpoint for MetaTrader 5 Expert Advisor (JournaNextGen_Sync.mq5).
    Verifies Secret Sync PIN & Target Account to prevent cross-account collisions.
    """
    # 1. Verify Secret Sync PIN
    saved_pin = get_config().get("sync_pin", "JN-8899").strip()
    received_pin = str(payload.get("sync_pin") or payload.get("pin") or "").strip()
    if not received_pin or received_pin != saved_pin:
        raise HTTPException(
            status_code=401,
            detail=f"Secret Sync PIN មិនត្រឹមត្រូវឡើយ! (Invalid Sync PIN). Please verify the PIN in your MT5 EA settings."
        )

    # 2. Check Target Account if specified
    saved_target = get_config().get("target_account", "").strip()
    account_number = str(payload.get("account_number") or "").strip()
    if saved_target and account_number and saved_target != account_number:
        raise HTTPException(
            status_code=403,
            detail=f"គណនី MT5 [{account_number}] មិនត្រូវនឹងគណនីគោលដៅ [{saved_target}] ឡើយ! ត្រូវបានបដិសេធដើម្បីកុំឱ្យជាន់ទិន្នន័យគ្នា។"
        )

    try:
        trades_data = payload.get("trades", [payload]) if "trades" in payload else [payload]
        count = 0
        account_type = str(payload.get("account_type", "REAL")).upper()
        for t in trades_data:
            if "symbol" in t and "profit" in t:
                t["source"] = "mt5_ea"
                if "account_type" not in t:
                    t["account_type"] = account_type
                if "account_number" not in t and account_number:
                    t["account_number"] = account_number
                insert_or_update_trade(t)
                count += 1
                
        # Also update account balance if provided by EA
        if payload.get("balance"):
            conn = get_db_connection()
            conn.execute("""
            INSERT OR REPLACE INTO mt5_account (id, account_number, broker, currency, balance, equity, account_type, last_sync)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?)
            """, (
                account_number,
                payload.get("broker", "MT5 EA"),
                payload.get("currency", "USD"),
                float(payload.get("balance", 0.0)),
                float(payload.get("equity", payload.get("balance", 0.0))),
                account_type,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ))
            conn.commit()
            conn.close()

        return {"success": True, "saved_trades": count, "account_number": account_number}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/trades/import")
async def api_import_statement(file: UploadFile = File(...)):
    """
    Upload and parse MT5 HTML or CSV statement report.
    """
    content_bytes = await file.read()
    filename = file.filename.lower()
    
    try:
        # Decode text
        try:
            content_text = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            content_text = content_bytes.decode("latin-1", errors="ignore")
            
        if filename.endswith(".csv"):
            trades = parse_csv_statement(content_text)
        elif filename.endswith(".html") or filename.endswith(".htm"):
            trades = parse_html_statement(content_text)
        else:
            # Try HTML first, then CSV
            trades = parse_html_statement(content_text)
            if not trades:
                trades = parse_csv_statement(content_text)
                
        return {
            "success": True,
            "imported_count": len(trades),
            "filename": file.filename
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {str(e)}")


EA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "ea")

@app.get("/api/download/ea/{filename}")
def download_ea(filename: str):
    file_path = os.path.join(EA_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(file_path, filename=filename, media_type="application/octet-stream")
    raise HTTPException(status_code=404, detail="EA file not found")

# Serve Static files & PWA
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.api_route("/", methods=["GET", "HEAD"])
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(
            index_file,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return JSONResponse({"status": "DingJourney API is running. Static files loading..."})

@app.get("/manifest.json")
def serve_manifest():
    return FileResponse(os.path.join(STATIC_DIR, "manifest.json"))

@app.get("/sw.js")
def serve_sw():
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"), media_type="application/javascript")
