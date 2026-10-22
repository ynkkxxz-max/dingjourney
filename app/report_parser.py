"""
DingJourney - MT5 Statement Parser
Parses HTML and CSV trade history exported from MetaTrader 5 (Desktop or Mobile).
"""

import re
import csv
import io
from datetime import datetime
from typing import List, Dict, Any
from .database import insert_or_update_trade


def parse_csv_statement(content: str) -> List[Dict[str, Any]]:
    """
    Parses MT5 CSV trade history.
    """
    reader = csv.reader(io.StringIO(content))
    trades = []
    
    headers = []
    for row in reader:
        if not row:
            continue
        # Find header row
        lower_row = [c.strip().lower() for c in row]
        if "ticket" in lower_row or "order" in lower_row or "deal" in lower_row:
            headers = lower_row
            continue
            
        if headers and len(row) >= len(headers):
            row_dict = {headers[i]: row[i].strip() for i in range(len(headers))}
            
            # Extract common columns
            ticket = row_dict.get("deal") or row_dict.get("ticket") or row_dict.get("order") or str(len(trades)+1)
            symbol = row_dict.get("symbol", "UNKNOWN")
            trade_type = row_dict.get("type", "BUY").upper()
            
            try:
                lots = float(row_dict.get("volume", row_dict.get("lots", "0.01")).replace(" ", ""))
            except ValueError:
                lots = 0.01
                
            try:
                profit = float(row_dict.get("profit", "0").replace(" ", "").replace("$", ""))
            except ValueError:
                profit = 0.0
                
            close_time = row_dict.get("time", row_dict.get("close time", datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            close_date = close_time.split(" ")[0] if " " in close_time else close_time[:10]
            
            trade = {
                "ticket": ticket,
                "symbol": symbol,
                "trade_type": "BUY" if "buy" in trade_type.lower() else "SELL",
                "lots": lots,
                "open_price": float(row_dict.get("price", 0.0)),
                "close_price": float(row_dict.get("price", 0.0)),
                "open_time": close_time,
                "close_time": close_time,
                "close_date": close_date,
                "profit": profit,
                "commission": float(row_dict.get("commission", 0.0)),
                "swap": float(row_dict.get("swap", 0.0)),
                "comment": row_dict.get("comment", "CSV Import"),
                "source": "mt5_csv"
            }
            insert_or_update_trade(trade)
            trades.append(trade)
            
    return trades


def parse_html_statement(content: str) -> List[Dict[str, Any]]:
    """
    Parses standard MetaTrader 5 HTML Report (ReportHistory-XXXXX.html).
    """
    trades = []
    
    # Matches table rows in MT5 HTML report
    # Standard MT5 format has rows with: Time, Deal, Order, Symbol, Type, Direction, Volume, Price, Order, Commission, Swap, Profit, Balance, Comment
    # We can match rows with regex
    row_pattern = re.compile(r'<tr[^>]*>(.*?)</tr>', re.DOTALL | re.IGNORECASE)
    cell_pattern = re.compile(r'<td[^>]*>(.*?)</td>', re.DOTALL | re.IGNORECASE)
    
    for row_match in row_pattern.finditer(content):
        row_html = row_match.group(1)
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cell_pattern.findall(row_html)]
        
        # An MT5 deal row typically has 10 to 14 cells
        if len(cells) >= 9:
            # Check if cell[0] is a date-time like '2026.10.15 14:30:00'
            date_match = re.match(r'(\d{4})[./-](\d{2})[./-](\d{2})\s+(\d{2}:\d{2}(?::\d{2})?)', cells[0])
            if date_match:
                year, month, day, time_part = date_match.groups()
                formatted_date = f"{year}-{month}-{day}"
                formatted_time = f"{formatted_date} {time_part}"
                
                deal_ticket = cells[1] if len(cells) > 1 and cells[1].isdigit() else str(len(trades)+1)
                symbol = cells[3] if len(cells) > 3 else "UNKNOWN"
                direction = cells[4].upper() if len(cells) > 4 else "BUY"
                
                # Check for BUY / SELL
                if not any(k in direction for k in ("BUY", "SELL")):
                    continue
                    
                trade_type = "BUY" if "BUY" in direction else "SELL"
                
                try:
                    volume = float(cells[5].replace(" ", "")) if len(cells) > 5 else 0.01
                except ValueError:
                    volume = 0.01
                    
                try:
                    price = float(cells[6].replace(" ", "")) if len(cells) > 6 else 0.0
                except ValueError:
                    price = 0.0
                    
                # Look for profit in the last few cells
                profit = 0.0
                for c in reversed(cells):
                    clean_c = c.replace(" ", "").replace(",", "").replace("$", "")
                    try:
                        val = float(clean_c)
                        # The last numeric cell is usually balance or profit
                        profit = val
                        break
                    except ValueError:
                        continue
                        
                trade = {
                    "ticket": deal_ticket,
                    "symbol": symbol,
                    "trade_type": trade_type,
                    "lots": volume,
                    "open_price": price,
                    "close_price": price,
                    "open_time": formatted_time,
                    "close_time": formatted_time,
                    "close_date": formatted_date,
                    "profit": profit,
                    "comment": "MT5 HTML Report",
                    "source": "mt5_html"
                }
                insert_or_update_trade(trade)
                trades.append(trade)
                
    return trades
