//+------------------------------------------------------------------+
//|                                         JournaNextGen_Sync.mq5   |
//|                         Journa NextGen Real-Time Auto-Sync EA    |
//|                    Auto-syncs closed trades on BUY / SELL TP/SL  |
//+------------------------------------------------------------------+
#property copyright "Journa NextGen"
#property link      "http://localhost:8000"
#property version   "1.00"
#property description "Auto-syncs closed trades instantly to Journa NextGen Dashboard whenever a trade is closed"

input string   InpWebhookUrl          = "http://127.0.0.1:8000/api/mt5/webhook"; // Webhook URL (Local or Cloudflare)
input int      InpSyncIntervalSeconds = 10;                                       // Backup Sync Interval (Seconds)
input bool     InpInstantSyncOnDeal   = true;                                     // Instant sync on BUY/SELL close

datetime g_lastSyncTime = 0;
ulong    g_lastSyncedTicket = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("Journa NextGen Real-Time Sync EA started.");
   Print("Webhook Endpoint: ", InpWebhookUrl);
   EventSetTimer(InpSyncIntervalSeconds);
   SyncClosedTrades(30); // Sync past 30 days on launch
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("Journa NextGen Sync EA stopped.");
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
   SyncClosedTrades(7); // Check last 7 days
}

//+------------------------------------------------------------------+
//| TradeTransaction event - fires immediately when trade occurs     |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
   if(InpInstantSyncOnDeal && trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      // A deal has just completed (BUY or SELL opened/closed)
      SyncClosedTrades(1); // Check today's trades instantly
   }
}

//+------------------------------------------------------------------+
//| Sync closed deals to Journa NextGen                              |
//+------------------------------------------------------------------+
void SyncClosedTrades(int daysBack)
{
   datetime fromDate = TimeCurrent() - (daysBack * 86400);
   datetime toDate   = TimeCurrent() + 86400;

   if(!HistorySelect(fromDate, toDate))
      return;

   int totalDeals = HistoryDealsTotal();
   if(totalDeals <= 0) return;

   string jsonArray = "[";
   int addedCount = 0;

   for(int i = 0; i < totalDeals; i++)
   {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket <= 0) continue;

      long dealType = HistoryDealGetInteger(ticket, DEAL_TYPE);
      if(dealType != DEAL_TYPE_BUY && dealType != DEAL_TYPE_SELL) continue;

      long dealEntry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
      double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT);

      // Only sync closed deals or deals with profit/loss
      if(dealEntry == DEAL_ENTRY_OUT || dealEntry == DEAL_ENTRY_INOUT || profit != 0.0)
      {
         string symbol = HistoryDealGetString(ticket, DEAL_SYMBOL);
         double volume = HistoryDealGetDouble(ticket, DEAL_VOLUME);
         double price  = HistoryDealGetDouble(ticket, DEAL_PRICE);
         double comm   = HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         double swap   = HistoryDealGetDouble(ticket, DEAL_SWAP);
         datetime time = (datetime)HistoryDealGetInteger(ticket, DEAL_TIME);
         string comment= HistoryDealGetString(ticket, DEAL_COMMENT);

         string timeStr = TimeToString(time, TIME_DATE|TIME_SECONDS);
         StringReplace(timeStr, ".", "-");

         string tradeType = (dealType == DEAL_TYPE_SELL) ? "SELL" : "BUY";

         if(addedCount > 0) jsonArray += ",";

         jsonArray += StringFormat(
            "{\"ticket\":\"%I64u\",\"symbol\":\"%s\",\"trade_type\":\"%s\",\"lots\":%.2f,\"open_price\":%.5f,\"close_price\":%.5f,\"close_time\":\"%s\",\"profit\":%.2f,\"commission\":%.2f,\"swap\":%.2f,\"comment\":\"%s\"}",
            ticket, symbol, tradeType, volume, price, price, timeStr, profit, comm, swap, comment
         );
         addedCount++;
      }
   }
   jsonArray += "]";

   if(addedCount > 0)
   {
      string payload = "{\"trades\":" + jsonArray + "}";
      SendHttpPost(payload);
   }
}

//+------------------------------------------------------------------+
//| Send HTTP Post to Journa NextGen Server                          |
//+------------------------------------------------------------------+
void SendHttpPost(string postData)
{
   char postBytes[];
   char result[];
   string resultHeaders;
   StringToCharArray(postData, postBytes, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(postBytes, ArraySize(postBytes) - 1);

   string headers = "Content-Type: application/json\r\n";
   int timeout = 5000;

   int res = WebRequest("POST", InpWebhookUrl, headers, timeout, postBytes, result, resultHeaders);
   if(res == 200)
   {
      Print("Journa NextGen Auto-Sync: Trade synced successfully!");
   }
   else if(res == -1)
   {
      int err = GetLastError();
      if(err == 4014)
      {
         Print("Journa NextGen: Please allow WebRequest for URL '", InpWebhookUrl, "' in MT5 Tools -> Options -> Expert Advisors");
      }
      else
      {
         Print("Journa NextGen WebRequest error: ", err);
      }
   }
}
