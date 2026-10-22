//+------------------------------------------------------------------+
//|                                           DingJourney_Sync.mq5   |
//|                        DingJourney Trading Journal Auto-Sync     |
//|                                  https://github.com/dingjourney  |
//+------------------------------------------------------------------+
#property copyright "DingJourney"
#property link      "http://localhost:8000"
#property version   "1.00"
#property description "Auto-syncs closed trades and balance from MetaTrader 5 to DingJourney Dashboard"

input string   InpSyncPin             = "JN-8899";                                // Secret Sync PIN (Match your Dashboard PIN)
input string   InpServerUrl           = "http://localhost:8000/api/mt5/webhook"; // DingJourney Webhook URL
input int      InpSyncIntervalSeconds = 60;                                       // Sync Interval (Seconds)
input bool     InpSyncOnTradeClose    = true;                                     // Sync immediately on trade close

datetime g_lastSyncTime = 0;
ulong    g_lastDealTicket = 0;

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   Print("DingJourney Auto-Sync EA Started.");
   Print("Sync PIN: ", InpSyncPin);
   Print("Syncing to: ", InpServerUrl);
   EventSetTimer(InpSyncIntervalSeconds);
   SyncHistoryTrades();
   return(INIT_SUCCEEDED);
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   Print("DingJourney Auto-Sync EA Stopped.");
}

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
{
   SyncHistoryTrades();
}

//+------------------------------------------------------------------+
//| TradeTransaction event                                           |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
   if(InpSyncOnTradeClose && trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      SyncHistoryTrades();
   }
}

//+------------------------------------------------------------------+
//| Sync all recent closed deals                                     |
//+------------------------------------------------------------------+
void SyncHistoryTrades()
{
   datetime fromDate = TimeCurrent() - (90 * 86400); // Past 90 days
   datetime toDate   = TimeCurrent() + 86400;

   if(!HistorySelect(fromDate, toDate))
   {
      Print("Failed to select MT5 history");
      return;
   }

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
         // Format YYYY.MM.DD HH:MM:SS -> YYYY-MM-DD HH:MM:SS
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
      long accLogin = AccountInfoInteger(ACCOUNT_LOGIN);
      string accBroker = AccountInfoString(ACCOUNT_COMPANY);
      string accCurrency = AccountInfoString(ACCOUNT_CURRENCY);
      double accBalance = AccountInfoDouble(ACCOUNT_BALANCE);
      double accEquity = AccountInfoDouble(ACCOUNT_EQUITY);
      long accMode = AccountInfoInteger(ACCOUNT_TRADE_MODE);
      string accType = (accMode == ACCOUNT_TRADE_MODE_REAL) ? "REAL" : "DEMO";

      string payload = StringFormat(
         "{\"sync_pin\":\"%s\",\"account_number\":\"%I64d\",\"broker\":\"%s\",\"currency\":\"%s\",\"balance\":%.2f,\"equity\":%.2f\",\"account_type\":\"%s\",\"trades\":%s}",
         InpSyncPin, accLogin, accBroker, accCurrency, accBalance, accEquity, accType, jsonArray
      );
      SendHttpPost(payload);
   }
}

//+------------------------------------------------------------------+
//| Send HTTP Post to DingJourney Server                             |
//+------------------------------------------------------------------+
void SendHttpPost(string postData)
{
   char postBytes[];
   char result[];
   string resultHeaders;
   StringToCharArray(postData, postBytes, 0, WHOLE_ARRAY, CP_UTF8);
   ArrayResize(postBytes, ArraySize(postBytes) - 1); // Remove null terminator

   string headers = "Content-Type: application/json\r\n";
   int timeout = 5000;

   // Note: User must add InpServerUrl to MT5 -> Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL
   int res = WebRequest("POST", InpServerUrl, headers, timeout, postBytes, result, resultHeaders);
   if(res == 200)
   {
      // Successfully synced
      Print("DingJourney sync success!");
   }
   else if(res == -1)
   {
      int err = GetLastError();
      if(err == 4014) // ERR_WEBREQUEST_NOT_ALLOWED
      {
         Print("DingJourney Warning: Please allow WebRequest for URL '", InpServerUrl, "' in MT5 Tools -> Options -> Expert Advisors");
      }
      else
      {
         Print("DingJourney WebRequest error: ", err);
      }
   }
}
