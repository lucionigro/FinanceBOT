import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import requests
import config


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


# ------------------------------------------------------------------------------------
# Interfaz de Usuario (CLI) Actualizada
# ------------------------------------------------------------------------------------

def main():
    while True:
        print("\n=== BOT FINANCIERO  ===")
        print("1. Analizar un ticker")
        print("2. Registrar una compra")
        print("3. Obtener recomendaciones del mercado Americano")
        print("4. Salir")
        
        choice = input("Selecciona una opción: ")
        
        if choice == "1":
            ticker = input("Ingresa el ticker (ej: NVDA): ").upper()
            data, latest = get_technical_analysis(ticker)
            
            if data is None:
                print(latest)
                continue
            
            recommendation, reasons, time_analysis = generate_recommendation(data, latest)
            price = latest['Close']

            entry_price = None
            target_price = None
            if recommendation == "COMPRAR":
                if latest['BB_Percent'] < 30:
                    entry_price = latest['LowerBand']
                else:
                    entry_price = latest['SMA20']
                target_price = latest['UpperBand']
            
            # Resultado en consola
            print(f"\n📊 Análisis para {ticker} (Precio: ${price:.2f})")
            print(f"🚨 Recomendación: {recommendation}")

            if recommendation == "COMPRAR":
                print(f"💡 Precio de entrada ideal: ${entry_price:.2f}")
                print(f"🎯 Objetivo técnico: ${target_price:.2f}")
                entry_target_msg = f"\n\n🎯 *Precios Clave:*\n- Precio de Entrada: ${entry_price:.2f}\n- Precio Objetivo: ${target_price:.2f}"

            
            else: entry_target_msg = ""  # Si no es "COMPRAR", no se agrega nada

                
                
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
                f"*📊Análisis de {ticker}*\n"
                f"Precio: ${price:.2f}\n"
                f"🚨Recomendación: {recommendation}"
                f"{entry_target_msg}\n\n"  # Aquí se inserta el mensaje con precios clave

                "🔍Detalles Técnicos:\n- " + "\n- ".join(reasons) + "\n\n"
                "⏳Horizonte Temporal:\n" + time_analysis + "\n\n"
                "📈Análisis Fundamental:\n" + fundamental_analysis 
            )

            if config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID:
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
        
        elif choice == "3":  # Nueva opción de recomendaciones
            print("\n🔎 Analizando oportunidades de mercado...")
            recommendations = get_investment_recommendations()
            
            if not recommendations:
                print("\n⚠️ No se encontraron oportunidades fuertes para corto plazo")
                continue
                
            print(f"\n🚀 Top 5 Recomendaciones Corto Plazo ({datetime.now().strftime('%d/%m')}):")
            for i, asset in enumerate(recommendations, 1):
                print(f"\n{i}. {asset['ticker']}")
                print(f"   Precio Actual: {asset['price']}")
                print(f"   Precio Entrada Ideal: {asset['entry']}")
                print(f"   Objetivo Técnico: {asset['target']}")
                print("   Señales Técnicas:")
                for reason in asset['reasons']:
                    print(f"   - {reason}")
            
            # Enviar por Telegram
            if config.TELEGRAM_TOKEN and config.TELEGRAM_CHAT_ID:
                telegram_msg = "📈 *Recomendaciones Corto Plazo:*\n\n"
                for asset in recommendations:
                    telegram_msg += (
                        f"🏅 *{asset['ticker']}*\n"
                        f"- Precio: {asset['price']}\n"
                        f"- Entrada: {asset['entry']}\n"
                        f"- Objetivo: {asset['target']}\n"
                        f"- Señales:\n   • " + "\n   • ".join(asset['reasons']) + "\n\n"
                    )
                send_telegram_message(telegram_msg)

        elif choice == "4":  # Actualizado
            print("¡Hasta luego!")
            break

if __name__ == "__main__":
    main()