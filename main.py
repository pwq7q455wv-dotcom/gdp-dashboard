import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import datetime
import time
import threading
import requests
import openai
import alpaca_trade_api as tradeapi
from telegram import Bot

# --- LOAD SECRETS ---
ALPACA_API_KEY = st.secrets["ALPACA_API_KEY"]
ALPACA_SECRET = st.secrets["ALPACA_SECRET"]
BASE_URL = "https://paper-api.alpaca.markets"
OPENAI_API_KEY = st.secrets["OPENAI_API_KEY"]
NEWSAPI_KEY = st.secrets["NEWSAPI_KEY"]
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
TICKER = st.secrets["TICKER"]
SHORT_WINDOW = int(st.secrets["SHORT_WINDOW"])
LONG_WINDOW = int(st.secrets["LONG_WINDOW"])
MAX_POSITION = int(st.secrets["MAX_POSITION"])

# --- INIT APIs ---
alpaca = tradeapi.REST(ALPACA_API_KEY, ALPACA_SECRET, BASE_URL, api_version='v2')
openai.api_key = OPENAI_API_KEY
bot = Bot(token=TELEGRAM_TOKEN)

# --- FUNCTIONS ---
def fetch_news(ticker):
    try:
        url = f"https://newsapi.org/v2/everything?q={ticker}&sortBy=publishedAt&apiKey={NEWSAPI_KEY}"
        resp = requests.get(url).json()
        headlines = [a["title"] for a in resp.get("articles", [])[:5]]
    except:
        headlines = []
    return headlines

def get_sentiment(headlines):
    if not headlines: return "NEUTRAL"
    prompt = f"Analyze these headlines about {TICKER} and return POSITIVE, NEGATIVE, or NEUTRAL:\n{headlines}"
    try:
        resp = openai.ChatCompletion.create(model="gpt-4",
            messages=[{"role":"user","content":prompt}], max_tokens=10)
        sentiment = resp["choices"][0]["message"]["content"].strip().upper()
    except:
        sentiment = "NEUTRAL"
    return sentiment

def get_signal(df):
    df["Short_MA"] = df["Close"].rolling(SHORT_WINDOW).mean()
    df["Long_MA"] = df["Close"].rolling(LONG_WINDOW).mean()
    if df["Short_MA"].iloc[-1] > df["Long_MA"].iloc[-1] and df["Short_MA"].iloc[-2] <= df["Long_MA"].iloc[-2]:
        return "BUY"
    elif df["Short_MA"].iloc[-1] < df["Long_MA"].iloc[-1] and df["Short_MA"].iloc[-2] >= df["Long_MA"].iloc[-2]:
        return "SELL"
    else:
        return "HOLD"

def log_trade(action, qty, price):
    df = pd.DataFrame([[datetime.datetime.now(), action, qty, price]],
                      columns=["Timestamp","Action","Quantity","Price"])
    try:
        df_existing = pd.read_csv("trade_log.csv")
        df = pd.concat([df_existing, df], ignore_index=True)
    except:
        pass
    df.to_csv("trade_log.csv", index=False)

def execute_trade(signal, sentiment):
    try: shares_held = int(alpaca.get_position(TICKER).qty)
    except: shares_held = 0
    price = float(yf.download(TICKER, period="1d", interval="1m")["Close"][-1])
    cash = float(alpaca.get_account().cash)
    if signal=="BUY" and sentiment=="POSITIVE" and cash>price:
        qty = min(MAX_POSITION, int(cash/price))
        if qty>0:
            alpaca.submit_order(TICKER, qty, "buy", "market", "gtc")
            log_trade("BUY", qty, price)
            bot.send_message(TELEGRAM_CHAT_ID, f"BUY {qty} {TICKER} at {price:.2f}")
    elif signal=="SELL" and sentiment=="NEGATIVE" and shares_held>0:
        alpaca.submit_order(TICKER, shares_held, "sell", "market", "gtc")
        log_trade("SELL", shares_held, price)
        bot.send_message(TELEGRAM_CHAT_ID, f"SELL {shares_held} {TICKER} at {price:.2f}")

def auto_trade_loop(interval):
    while True:
        df = yf.download(TICKER, period="5d", interval="5m")
        signal = get_signal(df)
        headlines = fetch_news(TICKER)
        sentiment = get_sentiment(headlines)
        execute_trade(signal, sentiment)
        time.sleep(interval)

# --- STREAMLIT DASHBOARD ---
st.markdown("<h1 style='text-align:center;font-size:28px;'>AI Trading Bot</h1>", unsafe_allow_html=True)
st.sidebar.header("Auto-Trading Settings")
auto_trade_enabled = st.sidebar.checkbox("Enable Auto Trading", value=True)
refresh_interval = st.sidebar.slider("Refresh interval (seconds)", 60, 600, 300, 30)

if auto_trade_enabled:
    threading.Thread(target=auto_trade_loop, args=(refresh_interval,), daemon=True).start()

placeholder = st.empty()
while True:
    df = yf.download(TICKER, period="5d", interval="5m")
    signal = get_signal(df)
    headlines = fetch_news(TICKER)
    sentiment = get_sentiment(headlines)
    with placeholder.container():
        st.subheader("Portfolio & Signals")
        st.write(f"Signal: {signal}")
        st.write(f"AI Sentiment: {sentiment}")
        try:
            trades = pd.read_csv("trade_log.csv")
            st.dataframe(trades.tail(10), height=200)
        except:
            st.write("No trades yet.")
        st.subheader("Price & Moving Averages")
        df["Short_MA"] = df["Close"].rolling(SHORT_WINDOW).mean()
        df["Long_MA"] = df["Close"].rolling(LONG_WINDOW).mean()
        st.line_chart(df[['Close','Short_MA','Long_MA']].tail(100))
    time.sleep(refresh_interval)
ALPACA_API_KEY
ALPACA_SECRET
OPENAI_API_KEY
NEWSAPI_KEY
TELEGRAM_TOKEN
TELEGRAM_CHAT_ID
TICKER=AAPL
SHORT_WINDOW=5
LONG_WINDOW=20
MAX_POSITION=10
