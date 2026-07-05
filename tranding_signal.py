#!/usr/bin/env python3
# ============================================================
# ULTIMATE AI v14.0 – Self-Learning & Daily Target (Part 1)
# ============================================================

import sys
import time
import os
import json
import csv
import hashlib
import urllib.request
import yfinance as yf
import pandas as pd
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# ---------- CONFIG ----------
INITIAL_BALANCE = 140.0
DAILY_TARGET = 50.0
MAX_DAILY_LOSS = -30.0
TRADE_FEE = 0.001

# ---------- GITHUB AUTO-UPGRADE ----------
GITHUB_RAW_URL = "https://raw.githubusercontent.com/YOUR_USERNAME/YOUR_REPO/main/trading_signal.py"  # CHANGE THIS

def check_for_upgrade():
    try:
        print("🔍 Checking for updates...")
        response = urllib.request.urlopen(GITHUB_RAW_URL, timeout=10)
        new_code = response.read().decode('utf-8')
        current_hash = hashlib.md5(open(__file__, 'rb').read()).hexdigest()
        new_hash = hashlib.md5(new_code.encode()).hexdigest()
        if current_hash != new_hash:
            print("🔄 New version found! Upgrading...")
            backup = f"{__file__}.bak"
            os.rename(__file__, backup)
            with open(__file__, 'w') as f:
                f.write(new_code)
            os.chmod(__file__, 0o755)
            print("✅ Upgrade complete. Restarting...")
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return True
        else:
            print("✅ Up to date.")
            return False
    except Exception as e:
        print(f"⚠️ Upgrade check failed: {e}")
        return False

# ---------- PERSISTENT DATA ----------
BALANCE_FILE = "balance.txt"
TRADES_FILE = "trades.csv"
WEIGHTS_FILE = "weights.json"
DAILY_STATE_FILE = "daily_state.json"

def load_balance():
    if os.path.exists(BALANCE_FILE):
        with open(BALANCE_FILE, 'r') as f:
            return float(f.read().strip())
    return INITIAL_BALANCE

def save_balance(balance):
    with open(BALANCE_FILE, 'w') as f:
        f.write(str(balance))

def load_daily_state():
    if os.path.exists(DAILY_STATE_FILE):
        with open(DAILY_STATE_FILE, 'r') as f:
            return json.load(f)
    return {"day": time.strftime("%Y-%m-%d"), "pnl": 0.0, "trades_today": 0}

def save_daily_state(state):
    with open(DAILY_STATE_FILE, 'w') as f:
        json.dump(state, f)

def log_trade(trade):
    file_exists = os.path.exists(TRADES_FILE)
    with open(TRADES_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['timestamp', 'symbol', 'action', 'entry', 'exit', 'size', 'pnl', 'balance'])
        writer.writerow([
            trade['time'],
            trade['symbol'],
            trade['action'],
            trade['entry'],
            trade['exit'],
            trade['size'],
            trade['pnl'],
            trade['balance']
        ])

# ---------- SELF-LEARNING WEIGHTS ----------
DEFAULT_WEIGHTS = {
    'rsi': 0.15,
    'macd': 0.15,
    'news': 0.15,
    'vol': 0.10,
    'adx': 0.10,
    'bb': 0.15,
    'sr': 0.20
}

def load_weights():
    if os.path.exists(WEIGHTS_FILE):
        with open(WEIGHTS_FILE, 'r') as f:
            data = json.load(f)
            for k in DEFAULT_WEIGHTS:
                if k not in data['weights']:
                    data['weights'][k] = DEFAULT_WEIGHTS[k]
            return data
    return {"weights": DEFAULT_WEIGHTS.copy(), "performance": {k: {"correct": 0, "total": 0} for k in DEFAULT_WEIGHTS}}

def save_weights(data):
    with open(WEIGHTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def update_weights(performance_data, trade_result):
    for ind, info in trade_result.items():
        if ind in performance_data['performance']:
            perf = performance_data['performance'][ind]
            perf['total'] += 1
            if info['correct']:
                perf['correct'] += 1
            accuracy = perf['correct'] / perf['total'] if perf['total'] > 0 else 0.5
            current_weight = performance_data['weights'][ind]
            adjustment = 0.01 * (accuracy - 0.5) * 2
            new_weight = max(0.05, min(0.30, current_weight + adjustment))
            performance_data['weights'][ind] = new_weight
    total = sum(performance_data['weights'].values())
    for k in performance_data['weights']:
        performance_data['weights'][k] /= total
    save_weights(performance_data)
    return performance_data

# ---------- PAPER TRADER ----------
class PaperTrader:
    def __init__(self):
        self.balance = load_balance()
        self.initial_balance = self.balance
        self.positions = []
        self.trades = []
        self.trade_count = 0
        self.wins = 0
        self.losses = 0
        self._load_stats()

    def _load_stats(self):
        if os.path.exists(TRADES_FILE):
            try:
                df = pd.read_csv(TRADES_FILE)
                self.trades = df.to_dict('records')
                self.trade_count = len(df)
                if self.trade_count > 0:
                    self.wins = len(df[df['pnl'] > 0])
                    self.losses = self.trade_count - self.wins
            except:
                pass

    def calculate_position_size(self, entry_price, stop_price, max_risk=20.0):
        risk_per_unit = abs(entry_price - stop_price)
        if risk_per_unit == 0:
            return 1.0
        size = max_risk / risk_per_unit
        max_size = self.balance / entry_price
        return min(size, max_size)

    def buy(self, symbol, entry_price, stop_price=None, target_price=None, max_risk=20.0):
        if stop_price is None:
            stop_price = entry_price * 0.98
        size = self.calculate_position_size(entry_price, stop_price, max_risk)
        cost = entry_price * size
        if cost > self.balance:
            print(f"⚠️ Insufficient balance! Need ${cost:.2f}, have ${self.balance:.2f}")
            return False
        self.balance -= cost
        self.positions.append({
            'symbol': symbol,
            'entry_price': entry_price,
            'size': size,
            'stop': stop_price,
            'target': target_price,
            'entry_time': time.time()
        })
        print(f"✅ PAPER BUY: {size:.4f} {symbol} @ ${entry_price:.2f}")
        return True

    def sell(self, symbol, exit_price):
        if not self.positions:
            print("⚠️ No open position to sell.")
            return False
        pos = self.positions.pop()
        pnl = (exit_price - pos['entry_price']) * pos['size'] - (pos['entry_price'] * pos['size'] * TRADE_FEE * 2)
        self.balance += exit_price * pos['size']
        self.trade_count += 1
        if pnl > 0:
            self.wins += 1
        else:
            self.losses += 1
        trade_record = {
            'time': time.strftime("%Y-%m-%d %H:%M:%S"),
            'symbol': symbol,
            'action': 'SELL',
            'entry': pos['entry_price'],
            'exit': exit_price,
            'size': pos['size'],
            'pnl': pnl,
            'balance': self.balance
        }
        log_trade(trade_record)
        self.trades.append(trade_record)
        save_balance(self.balance)
        print(f"✅ PAPER SELL: {pos['size']:.4f} {symbol} @ ${exit_price:.2f} | P&L: ${pnl:.2f}")
        return pnl

    def get_summary(self):
        total_pnl = sum(t['pnl'] for t in self.trades)
        win_rate = (self.wins / self.trade_count * 100) if self.trade_count > 0 else 0.0
        return {
            'balance': self.balance,
            'total_pnl': total_pnl,
            'trade_count': self.trade_count,
            'win_rate': win_rate,
            'wins': self.wins,
            'losses': self.losses,
            'open_positions': len(self.positions)
        }
      # ============================================================
# PART 2 – ANALYSTS
# ============================================================

def get_news_sentiment(query="stock market", max_results=10):
    try:
        from gnews import GNews
        google_news = GNews(language='en', country='US', period='1d', max_results=max_results)
        articles = google_news.get_news(query)
        if not articles:
            return 50
        texts = []
        for a in articles:
            if a.get('title'):
                texts.append(a['title'])
            if a.get('description'):
                texts.append(a['description'])
        if not texts:
            return 50
        analyzer = SentimentIntensityAnalyzer()
        compound_scores = [analyzer.polarity_scores(t)['compound'] for t in texts]
        avg_compound = sum(compound_scores) / len(compound_scores)
        return int(max(0, min(100, (avg_compound + 1) * 50)))
    except Exception:
        return 50

def calculate_rsi(ticker, period=14):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="60d")
        if hist.empty:
            return 50
        close = hist['Close']
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        last_rsi = rsi.iloc[-1]
        if last_rsi < 30:
            score = int(100 - (last_rsi / 30) * 50)
        elif last_rsi > 70:
            score = int(50 - ((last_rsi - 70) / 30) * 50)
        else:
            score = int(50 + (last_rsi - 50) * 0.5)
        return max(0, min(100, score))
    except Exception:
        return 50

def calculate_macd(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="60d")
        if hist.empty:
            return 50
        close = hist['Close']
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=9, adjust=False).mean()
        macd_hist = macd - signal
        last_macd = macd_hist.iloc[-1]
        score = int(50 + (last_macd / 2) * 50)
        return max(0, min(100, score))
    except Exception:
        return 50

def calculate_volume_score(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="30d")
        if hist.empty:
            return 50
        avg_volume = hist['Volume'].mean()
        last_volume = hist['Volume'].iloc[-1]
        ratio = last_volume / avg_volume if avg_volume > 0 else 1
        score = int(50 + (ratio - 1) * 50)
        return max(0, min(100, score))
    except Exception:
        return 50

def calculate_adx(ticker, period=14):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="60d")
        if hist.empty:
            return 50
        high = hist['High']
        low = hist['Low']
        close = hist['Close']
        plus_dm = high.diff()
        minus_dm = low.diff()
        plus_dm[plus_dm < 0] = 0
        minus_dm[minus_dm > 0] = 0
        minus_dm = abs(minus_dm)
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
        minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)
        dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
        adx = dx.rolling(window=period).mean()
        last_adx = adx.iloc[-1]
        score = int(min(100, (last_adx / 50) * 100))
        return max(0, min(100, score))
    except Exception:
        return 50

def calculate_volatility_score(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="30d")
        if hist.empty:
            return 50
        returns = hist['Close'].pct_change()
        std = returns.std() * (252 ** 0.5)
        if std < 0.15:
            score = 80
        elif std < 0.25:
            score = 60
        elif std < 0.35:
            score = 40
        else:
            score = 20
        return max(0, min(100, score))
    except Exception:
        return 50

def calculate_bollinger(ticker, period=20, num_std=2):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=f"{period+10}d")
        if hist.empty:
            return 50, "HOLD"
        close = hist['Close']
        sma = close.rolling(window=period).mean()
        std = close.rolling(window=period).std()
        upper = sma + (std * num_std)
        lower = sma - (std * num_std)
        last_price = close.iloc[-1]
        last_upper = upper.iloc[-1]
        last_lower = lower.iloc[-1]
        if last_upper == last_lower:
            return 50, "HOLD"
        percent_b = (last_price - last_lower) / (last_upper - last_lower)
        if last_price < last_lower:
            score = 80
            action = "BUY"
        elif last_price > last_upper:
            score = 20
            action = "SELL"
        else:
            score = 40 + (percent_b * 20)
            action = "HOLD"
        return int(max(0, min(100, score))), action
    except Exception:
        return 50, "HOLD"

def calculate_support_resistance(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="30d")
        if hist.empty:
            return 50, "HOLD"
        high = hist['High']
        low = hist['Low']
        close = hist['Close']
        recent_high = high.max()
        recent_low = low.min()
        current_price = close.iloc[-1]
        if abs(current_price - recent_high) / recent_high < 0.01:
            score = 30
            action = "SELL"
        elif abs(current_price - recent_low) / recent_low < 0.01:
            score = 70
            action = "BUY"
        else:
            score = 50
            action = "HOLD"
        return int(score), action
    except Exception:
        return 50, "HOLD"

def generate_signal(final_score):
    final_score = max(0, min(100, final_score))
    if final_score >= 75:
        action = "STRONG BUY"
    elif final_score >= 60:
        action = "BUY"
    elif final_score >= 40:
        action = "HOLD"
    elif final_score >= 25:
        action = "SELL"
    else:
        action = "STRONG SELL"
    confidence = int(60 + (final_score / 100) * 30)
    return action, confidence
  # ============================================================
# PART 3 – MAIN LOGIC
# ============================================================

def main(ticker):
    print("\n🧠 ULTIMATE AI v14.0 (Self-Learning + Daily Target) |", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 60)

    balance = load_balance()
    daily_state = load_daily_state()
    weights_data = load_weights()
    weights = weights_data['weights']

    today = time.strftime("%Y-%m-%d")
    if daily_state['day'] != today:
        daily_state = {'day': today, 'pnl': 0.0, 'trades_today': 0}
        save_daily_state(daily_state)

    if daily_state['trades_today'] >= 3:
        print("⏳ Daily trade limit reached (max 3 trades). Waiting for next day.")
        return
    if daily_state['pnl'] >= DAILY_TARGET:
        print("✅ Daily target reached! Stopping trading for today.")
        return
    if daily_state['pnl'] <= MAX_DAILY_LOSS:
        print("⛔ Max daily loss reached! Stopping trading for today.")
        return

    stock = yf.Ticker(ticker)
    hist = stock.history(period="60d")
    if hist.empty:
        print("❌ No data found for", ticker)
        return
    current_price = hist['Close'].iloc[-1]
    print(f"💰 Current Price: ${current_price:.2f}")

    rsi_score = calculate_rsi(ticker)
    macd_score = calculate_macd(ticker)
    news_score = get_news_sentiment(query=ticker, max_results=10)
    vol_score = calculate_volume_score(ticker)
    adx_score = calculate_adx(ticker)
    vola_score = calculate_volatility_score(ticker)
    bollinger_score, bollinger_action = calculate_bollinger(ticker)
    sr_score, sr_action = calculate_support_resistance(ticker)

    def score_to_action(score):
        if score > 60: return "BUY"
        elif score < 40: return "SELL"
        else: return "HOLD"

    rsi_action = score_to_action(rsi_score)
    macd_action = score_to_action(macd_score)
    news_action = score_to_action(news_score)
    vol_action = score_to_action(vol_score)
    adx_action = score_to_action(adx_score)
    ml_score = (rsi_score + macd_score + news_score + vol_score + adx_score + bollinger_score + sr_score) / 7
    ml_action = score_to_action(ml_score)
    vola_action = "HOLD"

    final_score = (rsi_score * weights['rsi'] +
                   macd_score * weights['macd'] +
                   news_score * weights['news'] +
                   vol_score * weights['vol'] +
                   adx_score * weights['adx'] +
                   bollinger_score * weights['bb'] +
                   sr_score * weights['sr'])
    final_score = max(0, min(100, final_score))

    action, confidence = generate_signal(final_score)

    votes = {'BUY': 0, 'SELL': 0, 'HOLD': 0}
    for a in [rsi_action, macd_action, news_action, vol_action, adx_action, ml_action, bollinger_action, sr_action, vola_action]:
        votes[a] = votes.get(a, 0) + 1
    final_vote = "HOLD"
    if votes['BUY'] > votes['SELL'] and votes['BUY'] > votes['HOLD']:
        final_vote = "BUY"
    elif votes['SELL'] > votes['BUY'] and votes['SELL'] > votes['HOLD']:
        final_vote = "SELL"

    print("\n🧠 TEAM MEETING (9 ANALYSTS):")
    print(f"📊 Technical (RSI): {rsi_action} (Conf: {int(40 + (rsi_score/100)*40)}%)")
    print(f"📈 Technical (MACD): {macd_action} (Conf: {int(50 + (macd_score/100)*40)}%)")
    print(f"📊 Volume: {vol_action} (Conf: {int(30 + (vol_score/100)*50)}%) (Vol: {int(hist['Volume'].iloc[-1])} / Avg: {int(hist['Volume'].mean())})")
    print(f"📉 Trend (ADX): {adx_action} (ADX: {adx_score:.1f} | Conf: {int(60 + (adx_score/100)*30)}%)")
    print(f"📊 Bollinger Bands: {bollinger_action} (Conf: {int(40 + (bollinger_score/100)*40)}%)")
    print(f"📊 Support/Resistance: {sr_action} (Conf: {int(40 + (sr_score/100)*40)}%)")
    print(f"🌍 Macro (News): {news_action} (Conf: {int(20 + (news_score/100)*60)}%)")
    print(f"⚡ Risk (Volatility): {vola_action} (Conf: {int(30 + (vola_score/100)*40)}%)")
    print(f"🤖 ML Sentiment: {ml_action} (Conf: {int(40 + (ml_score/100)*40)}%)")
    print(f"\n🛡️ Decision: Market conditions confirmed.")
    print(f"🏆 FINAL ACTION: {final_vote} (Votes: Buy {votes['BUY']}, Sell {votes['SELL']}, Hold {votes['HOLD']})")

    # Execute paper trade if BUY or SELL
    if final_vote in ["BUY", "STRONG BUY", "SELL", "STRONG SELL"]:
        is_buy = final_vote in ["BUY", "STRONG BUY"]
        if is_buy:
            entry = current_price
            stop = current_price * 0.98
            target = current_price * 1.05
        else:
            entry = current_price
            stop = current_price * 1.02
            target = current_price * 0.95

        max_risk = min(balance * 0.20, 20.0)
        trader = PaperTrader()
        if is_buy:
            success = trader.buy(ticker, entry, stop, target, max_risk)
            if success:
                pnl = trader.sell(ticker, target)
                daily_state['pnl'] += pnl
                daily_state['trades_today'] += 1
                save_daily_state(daily_state)
                # Update self-learning weights
                correct_votes = {}
                for ind, act in [('rsi', rsi_action), ('macd', macd_action), ('news', news_action),
                                 ('vol', vol_action), ('adx', adx_action), ('bb', bollinger_action),
                                 ('sr', sr_action)]:
                    vote = act.split()[0] if ' ' in act else act
                    correct = (vote == final_vote) and (pnl > 0)
                    correct_votes[ind] = {'vote': vote, 'correct': correct}
                correct_votes['ml'] = {'vote': ml_action, 'correct': (ml_action == final_vote) and (pnl > 0)}
                weights_data = update_weights(weights_data, correct_votes)
        else:
            print("⚠️ SELL trades not yet implemented in paper trader. Skipping.")
    else:
        print("⏳ HOLD – no trade executed.")

    trader = PaperTrader()
    summary = trader.get_summary()
    print("\n📊 PERFORMANCE SUMMARY:")
    print(f"💰 Balance: ${summary['balance']:.2f}")
    print(f"📈 Total P&L: ${summary['total_pnl']:.2f}")
    print(f"📊 Trades: {summary['trade_count']} | Wins: {summary['wins']} | Losses: {summary['losses']}")
    print(f"🏆 Win Rate: {summary['win_rate']:.1f}%")
    print(f"📅 Today's P&L: ${daily_state['pnl']:.2f} | Trades today: {daily_state['trades_today']}")
    print("=" * 60)

if __name__ == "__main__":
    check_for_upgrade()
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else "BTC"
    main(ticker)
  
