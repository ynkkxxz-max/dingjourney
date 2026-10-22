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

class MT5SyncModel(BaseModel):
    days_back: Optional[int] = 180
    login: Optional[int] = None
    password: Optional[str] = None
    server: Optional[str] = None


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
    if config.starting_capital is not None:
        set_config("starting_capital", str(config.starting_capital))
    if config.account_name is not None:
        set_config("account_name", config.account_name)
    if config.account_type is not None:
        set_config("account_type", config.account_type)
    if config.currency is not None:
        set_config("currency", config.currency)
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
    result = sync_active_terminal(days_back=body.days_back or 180)
    return result


@app.post("/api/mt5/webhook")
def api_mt5_webhook(payload: Dict[str, Any]):
    """
    Webhook endpoint for MetaTrader 5 Expert Advisor (DingJourney_Sync.mq5).
    Receives trade events in real-time.
    """
    try:
        # Handles single trade or list of trades
        trades_data = payload.get("trades", [payload]) if "trades" in payload else [payload]
        count = 0
        for t in trades_data:
            if "symbol" in t and "profit" in t:
                t["source"] = "mt5_ea"
                insert_or_update_trade(t)
                count += 1
        return {"success": True, "saved_trades": count}
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


# Serve Static files & PWA
if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"status": "DingJourney API is running. Static files loading..."})

@app.get("/manifest.json")
def serve_manifest():
    return FileResponse(os.path.join(STATIC_DIR, "manifest.json"))

@app.get("/sw.js")
def serve_sw():
    return FileResponse(os.path.join(STATIC_DIR, "sw.js"), media_type="application/javascript")
