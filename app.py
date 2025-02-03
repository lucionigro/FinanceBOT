import os
from flask import Flask, render_template, request
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime
import config

app = Flask(__name__)

# Funciones existentes (get_technical_analysis, get_fundamental_analysis, generate_recommendation, get_investment_recommendations)
# ... [Pega aquí todas las funciones que proporcionaste] ...
# ------------------------------------------------------------------------------------
# Sección 1: Análisis Técnico Mejorado
# ------------------------------------------------------------------------------------

def get_technical_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")
        
        if hist.empty:
            return None, "No hay datos suficientes para este ticker."
        
        # Media Móvil Simple (SMA)
        hist['SMA20'] = hist['Close'].rolling(window=20).mean()
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
        
        # RSI
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        hist['EMA12'] = hist['Close'].ewm(span=12, adjust=False).mean()
        hist['EMA26'] = hist['Close'].ewm(span=26, adjust=False).mean()
        hist['MACD'] = hist['EMA12'] - hist['EMA26']
        hist['Signal'] = hist['MACD'].ewm(span=9, adjust=False).mean()
        
        # Bollinger Bands (SMA20 ± 2 desviaciones estándar)
        hist['STD'] = hist['Close'].rolling(window=20).std()
        hist['UpperBand'] = hist['SMA20'] + (2 * hist['STD'])
        hist['LowerBand'] = hist['SMA20'] - (2 * hist['STD'])
        latest = hist.iloc[-1].copy()

        # Porcentaje respecto a Bollinger Bands
        price = latest['Close']
        upper = latest['UpperBand']
        lower = latest['LowerBand']
        latest['BB_Percent'] = ((price - lower) / (upper - lower)) * 100
        
        # Volumen promedio (últimos 5 días)
        latest['AvgVolume'] = hist['Volume'].tail(5).mean()
        
        return hist, latest
    
    except Exception as e:
        return None, f"Error: {str(e)}"

def get_fundamental_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        fundamental = {
            'P/E Ratio': info.get('trailingPE', 'N/A'),
            'P/B Ratio': info.get('priceToBook', 'N/A'),
            'ROE': info.get('returnOnEquity', 'N/A'),
            'EPS': info.get('trailingEps', 'N/A'),
            'Market Cap': info.get('marketCap', 'N/A'),
            'Dividend Yield': info.get('dividendYield', 'N/A'),
            'Debt/Equity': info.get('debtToEquity', 'N/A')
        }
        
        # Formatear valores numéricos
        if isinstance(fundamental['Market Cap'], float):
            fundamental['Market Cap'] = f"${fundamental['Market Cap']/1e9:.2f}B"
            
        analysis = [
            "📊 Análisis Fundamental:",
            f"- 📈 Ratio P/E (Valoración): {fundamental['P/E Ratio']}",
            f"- 📉 Ratio P/B (Valoración): {fundamental['P/B Ratio']}",
            f"- 💹 ROE (Rentabilidad): {fundamental['ROE']}",
            f"- 💵 EPS (Beneficios): {fundamental['EPS']}",
            f"- 🏦 Capitalización: {fundamental['Market Cap']}",
            f"- 📊 Deuda/Patrimonio: {fundamental['Debt/Equity']}",
            f"- 💰 Dividendo: {fundamental['Dividend Yield'] or '0'}%"
        ]
        
        return "\n".join(analysis)
    
    except Exception as e:
        return f"Error en análisis fundamental: {str(e)}"

def generate_recommendation(hist, latest_data):
    reasons = []
    price = latest_data['Close']
    
    # 1. Comparar SMA20 y SMA50
    sma20 = latest_data['SMA20']
    sma50 = latest_data['SMA50']
    trend = "alcista📈" if sma20 > sma50 else "bajista📉"
    reasons.append(f"SMA20 (${sma20:.2f}) < SMA50 (${sma50:.2f}) → Tendencia {trend}")
    
     # 2. RSI
    rsi = latest_data['RSI']
    if rsi < 30:
        reasons.append(f" RSI: {rsi:.2f} (Sobreventa, <30)")
    elif rsi > 70:
        reasons.append(f" RSI: {rsi:.2f} (Sobrecompra, >70)")
    else:
        reasons.append(f" RSI: {rsi:.2f} (Neutral)")
    
    
    # 3. MACD
    macd = latest_data['MACD']
    signal = latest_data['Signal']
    if macd > signal:
        reasons.append(f"MACD ({macd:.2f}) > Señal ({signal:.2f}) → Momentum alcista📉")
    else:
        reasons.append(f"MACD ({macd:.2f}) < Señal ({signal:.2f}) → Momentum bajista📈")
    
    # 4. Bollinger Bands
    bb_percent = latest_data['BB_Percent']
    if bb_percent > 80:
        reasons.append(f"Bollinger Bands: Precio cerca de banda superior ({bb_percent:.2f}%)")
    elif bb_percent < 20:
        reasons.append(f"Bollinger Bands: Precio cerca de banda inferior ({bb_percent:.2f}%)")
    else:
        reasons.append(f"Bollinger Bands: Precio en zona media ({bb_percent:.2f}%)")
    
    # 5. Volumen
    avg_volume = latest_data['AvgVolume']
    latest_volume = latest_data['Volume']
    if latest_volume > avg_volume * 1.5:
        reasons.append(f"Volumen actual ({latest_volume:.0f}) > Promedio ({avg_volume:.0f}) → Alta actividad")
    
    # Decisión final
    buy_score = sum([
        1 if "alcista" in reason else 
        -1 if "bajista" in reason else 
        0 for reason in reasons
    ])
    
    # Recomendación de plazo temporal
    time_horizon = []
    time_reasons = []
    
    # Corto plazo (1-4 semanas)
    if (macd > signal) and (30 < rsi < 70) and (price > sma20):
        time_horizon.append("corto plazo")
        time_reasons.append("Momentum positivo con indicadores técnicos favorables para movimientos recientes")
    
    # Mediano plazo (1-6 meses)
    if (sma20 > sma50) and (hist['SMA20'].iloc[-10] < sma20) and (hist['SMA50'].iloc[-20] < sma50):
        time_horizon.append("mediano plazo") 
        time_reasons.append("Tendencia intermedia positiva con cruce alcista de medias móviles")
    
    # Largo plazo (>6 meses)
    if (sma50 > hist['SMA50'].iloc[-60]) and (price > sma50):
        time_horizon.append("largo plazo")
        time_reasons.append("Tendencia secular alcista y fundamentos sólidos para crecimiento sostenido")
    
    # Determinar recomendación final
    if buy_score > 1:
        recommendation = "COMPRAR"
    elif buy_score < -1:
        recommendation = "NO COMPRAR"
    else:
        recommendation = "NEUTRAL"
    
    # Formatear horizonte temporal
    if not time_horizon:
        time_str = "No se recomienda para ningún horizonte temporal específico"
    else:
        time_str = f"Recomendado para: {', '.join(time_horizon)}\n" + "\n".join(time_reasons)
    
    return recommendation, reasons, time_str

# ------------------------------------------------------------------------------------
# Sección 2: Notificaciones por Telegram
# ------------------------------------------------------------------------------------

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    return response.ok

def load_sp500_tickers(csv_path=config.CSV_PATH):
    """Carga los tickers del S&P 500 desde un archivo CSV."""
    try:
        df = pd.read_csv(csv_path)
        if 'Symbol' in df.columns:
            return df['Symbol'].tolist()
        else:
            print("Error: El archivo CSV no tiene una columna 'Symbol'.")
            return []
    except Exception as e:
        print(f"Error al cargar el archivo CSV: {e}")
        return []


def get_investment_recommendations():
    tickers = load_sp500_tickers()
    
    if not tickers:
        print("No se pudieron cargar los tickers. Usando lista por defecto.")
        tickers = ['NVDA', 'TSLA', 'AAPL', 'AMD', 'META', 'AMZN', 'GOOG', 'MSFT', 'BTC-USD', 'ETH-USD']
    recommendations = []
    
    for ticker in tickers:
        try:
            data, latest = get_technical_analysis(ticker)
            if data is None:
                continue
                
            recommendation, reasons, time_analysis = generate_recommendation(data, latest)
            
            # Filtrar solo recomendaciones COMPRAR con horizonte corto plazo
            if recommendation == "COMPRAR" and "corto plazo" in time_analysis:
                price = latest['Close']
                entry_price = latest['LowerBand'] if latest['BB_Percent'] < 30 else latest['SMA20']
                
                reasons_filtered = [
                    r for r in reasons 
                    if any(keyword in r for keyword in ['SMA20', 'RSI', 'MACD', 'Bollinger', 'Volumen'])
                ][:3]  # Mostrar solo las 3 señales más fuertes
                
                recommendations.append({
                    'ticker': ticker,
                    'price': f"${price:.2f}",
                    'entry': f"${entry_price:.2f}",
                    'target': f"${latest['UpperBand']:.2f}",
                    'reasons': reasons_filtered
                })
                
                if len(recommendations) >= 5:
                    break
                    
        except Exception as e:
            continue
    
    return recommendations


def get_top_movers():
    try:
        url = "https://query2.finance.yahoo.com/v1/finance/screener"
        params = {
            "count": 10,
            "sortField": "percentchange",
            "sortType": "DESC",
            "quoteType": "EQUITY"
        }
        
        response = requests.get(url, params=params)
        data = response.json()['finance']['result'][0]['quotes']
        
        return [{
            'symbol': item['symbol'],
            'name': item.get('shortName', item['symbol']),
            'price': round(item['regularMarketPrice'], 2),
            'change': round(item['regularMarketChange'], 2),
            'percent_change': round(item['regularMarketChangePercent'], 2)
        } for item in data]
        
    except Exception as e:
        print(f"Error obteniendo top movers: {str(e)}")
        return []

# ------------------------------------------------------------------------------------
# Sección 3: Análisis con DeepSeek (IA)
# ------------------------------------------------------------------------------------

def get_ai_analysis(ticker, technical_data, fundamental_analysis):
    try:
        import requests
        import json
        
        # Prepara el prompt con los datos técnicos
        technical_summary = "\n".join([f"- {d}" for d in technical_data])
        prompt = f"""
        Eres un experto analista financiero de Wall Street. Analiza el activo {ticker} considerando:
        
        **Datos Técnicos:**
        {technical_summary}
        
        **Análisis Fundamental:**
        {fundamental_analysis}
        
        Proporciona:
        1. Análisis de sentimiento (1 párrafo)
        2. Factores de riesgo clave (3-5 puntos)
        3. Escenarios probables (Alcista/Neutral/Bajista)
        4. Estrategia de trading recomendada
        """
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.DEEPSEEK_API_KEY}"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Eres un analista financiero experto en mercados bursátiles."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        
        response = requests.post("https://api.deepseek.com/v1/chat/completions", 
                               headers=headers, 
                               json=payload)
        
        if response.status_code == 200:
            return response.json()['choices'][0]['message']['content']
        else:
            return "⚠️ Error en el análisis de IA"
            
    except Exception as e:
        print(f"Error en IA: {str(e)}")
        return "No se pudo obtener análisis de IA"
    

# ------------------------------------------------------------------------------------
# Sección 4: Gestión de Portfolio
# ------------------------------------------------------------------------------------

PORTFOLIO_CSV = 'db/portfolio.csv'

def get_portfolio():
    try:
        df = pd.read_csv(PORTFOLIO_CSV, parse_dates=['purchase_date'])
        return df.to_dict('records')
    except FileNotFoundError:
        return []

def save_to_portfolio(data):
    df = pd.DataFrame([data])
    df.to_csv(PORTFOLIO_CSV, mode='a', header=not os.path.exists(PORTFOLIO_CSV), index=False)

def calculate_portfolio_performance():
    portfolio = get_portfolio()
    if not portfolio:
        return []
    
    # Agrupar por ticker
    grouped = {}
    for entry in portfolio:
        ticker = entry['ticker']
        if ticker not in grouped:
            grouped[ticker] = []
        grouped[ticker].append(entry)
    
    # Calcular rendimiento
    performance = []
    for ticker, entries in grouped.items():
        try:
            stock = yf.Ticker(ticker)
            current_price = stock.history(period='1d')['Close'].iloc[-1]
            
            total_quantity = sum([e['quantity'] for e in entries])
            total_cost = sum([e['quantity'] * e['purchase_price'] for e in entries])
            current_value = total_quantity * current_price
            pnl = current_value - total_cost
            pnl_percent = (pnl / total_cost) * 100 if total_cost != 0 else 0
            
            performance.append({
                'ticker': ticker,
                'entries': entries,
                'total_quantity': total_quantity,
                'avg_cost': total_cost / total_quantity,
                'current_price': current_price,
                'pnl': pnl,
                'pnl_percent': pnl_percent
            })
        except Exception as e:
            print(f"Error calculando {ticker}: {str(e)}")
    
    return performance


def calculate_total_values(performance):
    total_current = sum([p['current_price'] * p['total_quantity'] for p in performance])
    total_cost = sum([p['avg_cost'] * p['total_quantity'] for p in performance])
    total_pnl = total_current - total_cost
    return {
        'total_current': round(total_current, 2),
        'total_cost': round(total_cost, 2),
        'total_pnl': round(total_pnl, 2),
        'total_pnl_percent': round((total_pnl / total_cost) * 100, 2) if total_cost != 0 else 0
    }

def get_portfolio_history(period='1mo'):
    portfolio = get_portfolio()
    if not portfolio:
        return []
    
    # Obtener fechas extremas
    min_date = pd.to_datetime(min([pd.to_datetime(e['purchase_date']) for e in portfolio]))
    
    # Obtener todos los tickers únicos
    tickers = list(set([e['ticker'] for e in portfolio]))
    
    # Obtener datos históricos
    history = {}
    for ticker in tickers:
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(start=min_date, period=period)
            history[ticker] = hist[['Close']]
        except:
            continue
    
    # Calcular valor diario del portfolio
    dates = pd.date_range(start=min_date, end=datetime.today())
    portfolio_value = []
    
    for date in dates:
        daily_value = 0
        for entry in portfolio:
            ticker = entry['ticker']
            if ticker in history:
                # Encontrar el precio más cercano a la fecha
                try:
                    price = history[ticker].loc[:date.strftime('%Y-%m-%d')]['Close'].iloc[-1]
                    daily_value += entry['quantity'] * price
                except:
                    continue
        portfolio_value.append({
            'date': date.strftime('%Y-%m-%d'),
            'value': round(daily_value, 2)
        })
    
    return portfolio_value



# Rutas Flask
@app.route('/')
def index():
    # Obtener datos del mercado (Índices principales)
    indices = ['^GSPC', '^DJI', '^IXIC', '^FTSE', 'CL=F', 'GC=F', 'BTC-USD']
    
    market_data = []
    for symbol in indices:
        try:
            ticker = yf.Ticker(symbol)
            data = ticker.history(period='1d')
            info = ticker.info
            
            market_data.append({
                'symbol': symbol,
                'name': info.get('shortName', symbol),
                'price': round(data['Close'].iloc[-1], 2),
                'change': round(data['Close'].iloc[-1] - data['Open'].iloc[-1], 2),
                'percent_change': round(((data['Close'].iloc[-1] - data['Open'].iloc[-1]) / data['Open'].iloc[-1]) * 100, 2)
            })
        except Exception as e:
            print(f"Error obteniendo datos para {symbol}: {str(e)}")
            continue
    
    # Obtener acciones más activas
    top_movers = get_top_movers()
    
    return render_template('index.html', 
                         market_data=market_data,
                         top_movers=top_movers)

@app.route('/analyze', methods=['POST'])
def analyze():
    ticker = request.form['ticker'].upper()
    data, latest = get_technical_analysis(ticker)
    
    if data is None:
        return render_template('error.html', message=latest)
    
    recommendation, reasons, time_analysis = generate_recommendation(data, latest)
    fundamental = get_fundamental_analysis(ticker)
    
    # Nueva sección: Análisis con IA
    ai_analysis = get_ai_analysis(ticker, reasons, fundamental)
    
    price = latest['Close']
    entry_price = latest['LowerBand'] if latest['BB_Percent'] < 30 else latest['SMA20']
    target_price = latest['UpperBand']
    
    return render_template('analysis.html',
                          ticker=ticker,
                          price=price,
                          recommendation=recommendation,
                          entry_price=entry_price,
                          target_price=target_price,
                          reasons=reasons,
                          time_analysis=time_analysis,
                          fundamental=fundamental,
                          ai_analysis=ai_analysis)

@app.route('/recommendations')
def recommendations():
    recs = get_investment_recommendations()
    return render_template('recommendations.html', recommendations=recs)

# Nueva ruta para datos del gráfico
@app.route('/sp500-data')
def sp500_data():
    ticker = yf.Ticker("^GSPC")
    hist = ticker.history(period="1mo")
    
    return {
        'dates': hist.index.strftime('%Y-%m-%d').tolist(),
        'prices': hist['Close'].round(2).tolist()
    }

@app.route('/portfolio', methods=['GET', 'POST'])
def portfolio():
    if request.method == 'POST':
        try:
            ticker = request.form['ticker'].upper()
            quantity = float(request.form['quantity'])
            purchase_date = datetime.strptime(request.form['purchase_date'], '%Y-%m-%d')
            custom_price = request.form.get('custom_price', None)
            
            if custom_price:  # Si el usuario ingresó precio manual
                purchase_price = float(custom_price)
            else:  # Lógica original con Yahoo Finance
                stock = yf.Ticker(ticker)
                hist = stock.history(start=purchase_date, end=purchase_date + pd.Timedelta(days=1))
                
                if hist.empty:
                    raise ValueError("No hay datos para esta fecha")
                purchase_price = hist['Close'].iloc[0]
            
            new_entry = {
                'ticker': ticker,
                'quantity': quantity,
                'purchase_date': purchase_date.strftime('%Y-%m-%d'),
                'purchase_price': round(purchase_price, 2)
            }
            
            save_to_portfolio(new_entry)
            
        except Exception as e:
            return render_template('portfolio.html', 
                                performance=calculate_portfolio_performance(),
                                error=str(e))
    
    return render_template('portfolio.html',
                         performance=calculate_portfolio_performance(),
                         totals=calculate_total_values(calculate_portfolio_performance()))


if __name__ == '__main__':
    app.run(debug=True)