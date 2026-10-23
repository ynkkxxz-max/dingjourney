import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "app", "dingjourney.db")
conn = sqlite3.connect(DB_PATH)
conn.execute("UPDATE trades SET profit = 2000.0 WHERE ticket LIKE 'phone_%'")
conn.commit()
rows = conn.execute("SELECT id, ticket, profit, account_id, account_type FROM trades").fetchall()
for r in rows:
    print(r)
conn.close()
