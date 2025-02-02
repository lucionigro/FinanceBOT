import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import requests

# Configuración inicial
CSV_PATH = "my_portfolio.csv"
TELEGRAM_TOKEN = "7762073373:AAE2sDZr-ea7G8EagEiK-WIDtcdIuTkOack"  # Reemplaza con tu token
TELEGRAM_CHAT_ID = "5443110528"          # Reemplaza con tu chat ID

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
            "Análisis Fundamental:",
            f"- Ratio P/E (Valoración): {fundamental['P/E Ratio']}",
            f"- Ratio P/B (Valoración): {fundamental['P/B Ratio']}",
            f"- ROE (Rentabilidad): {fundamental['ROE']}",
            f"- EPS (Beneficios): {fundamental['EPS']}",
            f"- Capitalización: {fundamental['Market Cap']}",
            f"- Deuda/Patrimonio: {fundamental['Debt/Equity']}",
            f"- Dividendo: {fundamental['Dividend Yield'] or '0'}%"
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
    trend = "alcista" if sma20 > sma50 else "bajista"
    reasons.append(f"SMA20 (${sma20:.2f}) < SMA50 (${sma50:.2f}) → Tendencia {trend}")
    
    # 2. RSI
    rsi = latest_data['RSI']
    if rsi < 30:
        reasons.append(f"RSI: {rsi:.2f} (Sobreventa, <30)")
    elif rsi > 70:
        reasons.append(f"RSI: {rsi:.2f} (Sobrecompra, >70)")
    else:
        reasons.append(f"RSI: {rsi:.2f} (Neutral)")
    
    # 3. MACD
    macd = latest_data['MACD']
    signal = latest_data['Signal']
    if macd > signal:
        reasons.append(f"MACD ({macd:.2f}) > Señal ({signal:.2f}) → Momentum alcista")
    else:
        reasons.append(f"MACD ({macd:.2f}) < Señal ({signal:.2f}) → Momentum bajista")
    
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
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    response = requests.post(url, json=payload)
    return response.ok

# ------------------------------------------------------------------------------------
# Interfaz de Usuario (CLI) Actualizada
# ------------------------------------------------------------------------------------

def main():
    while True:
        print("\n=== BOT FINANCIERO v2 ===")
        print("1. Analizar un ticker")
        print("2. Registrar una compra")
        print("3. Salir")
        
        choice = input("Selecciona una opción: ")
        
        if choice == "1":
            ticker = input("Ingresa el ticker (ej: NVDA): ").upper()
            data, latest = get_technical_analysis(ticker)
            
            if data is None:
                print(latest)
                continue
            
            recommendation, reasons, time_analysis = generate_recommendation(data, latest)
            price = latest['Close']
            
            # Resultado en consola
            print(f"\n📊 Análisis para {ticker} (Precio: ${price:.2f})")
            print(f"🚨 Recomendación: {recommendation}")
            print("\n🔍 Detalles Técnicos:")
            for reason in reasons:
                print(f"- {reason}")
            print("\n⏳ Horizonte Temporal:")
            print(time_analysis)
            
            # Análisis Fundamental
            fundamental_analysis = get_fundamental_analysis(ticker)
            print("\n📈 Análisis Fundamental:")
            print(fundamental_analysis)
            
            # Enviar a Telegram
            telegram_msg = (
                f"*Análisis de {ticker}*\n"
                f"Precio: ${price:.2f}\n"
                f"Recomendación: {recommendation}\n\n"
                "Detalles Técnicos:\n- " + "\n- ".join(reasons) + "\n\n"
                "Horizonte Temporal:\n" + time_analysis + "\n\n"
                "Análisis Fundamental:\n" + fundamental_analysis
            )
            if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
                success = send_telegram_message(telegram_msg)
                if success:
                    print("\n✅ Notificación enviada a Telegram.")
                else:
                    print("\n❌ Error al enviar a Telegram.")
                
        elif choice == "2":
            ticker = input("Ticker comprado (ej: TSLA): ").upper()
            price = float(input("Precio por acción: "))
            quantity = int(input("Cantidad: "))
            save_purchase(ticker, price, quantity)
            print("¡Compra registrada exitosamente!")
        
        elif choice == "3":
            print("¡Hasta luego!")
            break

if __name__ == "__main__":
    main()