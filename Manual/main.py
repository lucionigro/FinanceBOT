import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import requests
import config
import concurrent.futures

# ------------------------------------------------------------------------------------
# Sección 1: Análisis Técnico Mejorado
# ------------------------------------------------------------------------------------

def get_technical_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo", timeout=10)  # Timeout de 10 segundos
        
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
        
        # Bollinger Bands
        hist['STD'] = hist['Close'].rolling(window=20).std()
        hist['UpperBand'] = hist['SMA20'] + (2 * hist['STD'])
        hist['LowerBand'] = hist['SMA20'] - (2 * hist['STD'])
        latest = hist.iloc[-1].copy()

        # Porcentaje respecto a Bollinger Bands
        price = latest['Close']
        upper = latest['UpperBand']
        lower = latest['LowerBand']
        latest['BB_Percent'] = ((price - lower) / (upper - lower)) * 100
        
        # Volumen promedio
        latest['AvgVolume'] = hist['Volume'].tail(5).mean()
        
        return hist, latest
    
    except Exception as e:
        return None, f"Error: {str(e)}"

def get_fundamental_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Calcular PEG Ratio
        pe_ratio = info.get('trailingPE', None)
        growth_rate = info.get('earningsGrowth', None)
        peg_ratio = pe_ratio / growth_rate if (pe_ratio and growth_rate) else 'N/A'
        
        fundamental = {
            'P/E Ratio': info.get('trailingPE', 'N/A'),
            'P/B Ratio': info.get('priceToBook', 'N/A'),
            'ROE': info.get('returnOnEquity', 'N/A'),
            'EPS': info.get('trailingEps', 'N/A'),
            'Market Cap': info.get('marketCap', 'N/A'),
            'Dividend Yield': info.get('dividendYield', 'N/A'),
            'Debt/Equity': info.get('debtToEquity', 'N/A'),
            'Free Cash Flow': info.get('freeCashflow', 'N/A'),
            'Operating Margin': info.get('operatingMargins', 'N/A'),
            'Revenue Growth': info.get('revenueGrowth', 'N/A'),
            'PEG Ratio': peg_ratio,
            'EBITDA': info.get('ebitda', 'N/A'),
            'Current Ratio': info.get('currentRatio', 'N/A')
        }
        
        # Formatear valores
        formatadores = {
            'Market Cap': lambda x: f"${x/1e9:.2f}B" if isinstance(x, (int, float)) else x,
            'Free Cash Flow': lambda x: f"${x/1e6:.2f}M" if isinstance(x, (int, float)) else x,
            'Operating Margin': lambda x: f"{x*100:.2f}%" if isinstance(x, float) else x,
            'Revenue Growth': lambda x: f"{x*100:.2f}%" if isinstance(x, float) else x,
            'PEG Ratio': lambda x: f"{x:.2f}" if isinstance(x, float) else x,
            'EBITDA': lambda x: f"${x/1e9:.2f}B" if isinstance(x, (int, float)) else x,
            'Current Ratio': lambda x: f"{x:.2f}" if isinstance(x, float) else x,
            'Dividend Yield': lambda x: f"{x*100:.2f}%" if isinstance(x, float) else x
        }
        
        for key, formatter in formatadores.items():
            fundamental[key] = formatter(fundamental[key])
            
        analysis = [
            "📊 Análisis Fundamental:",
            f"- 📈 Ratio P/E: {fundamental['P/E Ratio']}",
            f"- 📉 Ratio P/B: {fundamental['P/B Ratio']}",
            f"- 💹 ROE: {fundamental['ROE']}",
            f"- 💵 EPS: {fundamental['EPS']}",
            f"- 🏦 Capitalización: {fundamental['Market Cap']}",
            f"- 📊 Deuda/Patrimonio: {fundamental['Debt/Equity']}",
            f"- 💰 Dividendo: {fundamental['Dividend Yield'] or '0%'}",
            f"- 💵 Flujo Caja Libre: {fundamental['Free Cash Flow']}",
            f"- 📈 Margen Operativo: {fundamental['Operating Margin']}",
            f"- 🚀 Crecimiento Ingresos: {fundamental['Revenue Growth']}",
            f"- 🎯 Ratio PEG: {fundamental['PEG Ratio']}",
            f"- 📉 EBITDA: {fundamental['EBITDA']}",
            f"- ⚖️ Ratio Corriente: {fundamental['Current Ratio']}"
        ]
        
        return "\n".join(analysis)
    
    except Exception as e:
        return f"Error en análisis fundamental: {str(e)}"

def generate_recommendation(hist, latest_data):
    reasons = []
    price = latest_data['Close']
    
    # 1. Medias móviles
    sma20 = latest_data['SMA20']
    sma50 = latest_data['SMA50']
    trend = "alcista📈" if sma20 > sma50 else "bajista📉"
    reasons.append(f"SMA20 (${sma20:.2f}) vs SMA50 (${sma50:.2f}) → Tendencia {trend}")
    
    # 2. RSI
    rsi = latest_data['RSI']
    if rsi < 30:
        reasons.append(f"RSI: {rsi:.2f} (Sobreventa)")
    elif rsi > 70:
        reasons.append(f"RSI: {rsi:.2f} (Sobrecompra)")
    else:
        reasons.append(f"RSI: {rsi:.2f} (Neutral)")
    
    # 3. MACD (Corregido emojis)
    macd = latest_data['MACD']
    signal = latest_data['Signal']
    if macd > signal:
        reasons.append(f"MACD ({macd:.2f}) > Señal ({signal:.2f}) → Momentum alcista📈")
    else:
        reasons.append(f"MACD ({macd:.2f}) < Señal ({signal:.2f}) → Momentum bajista📉")
    
    # 4. Bollinger Bands
    bb_percent = latest_data['BB_Percent']
    if bb_percent > 80:
        reasons.append(f"Bollinger: {bb_percent:.2f}% (Zona superior)")
    elif bb_percent < 20:
        reasons.append(f"Bollinger: {bb_percent:.2f}% (Zona inferior)")
    else:
        reasons.append(f"Bollinger: {bb_percent:.2f}% (Zona media)")
    
    # 5. Volumen
    avg_volume = latest_data['AvgVolume']
    latest_volume = latest_data['Volume']
    if latest_volume > avg_volume * 1.5:
        reasons.append(f"Volumen +150%: {latest_volume:.0f} vs {avg_volume:.0f}")
    
    # Puntuación
    buy_score = sum([
        1 if "alcista" in reason else 
        -1 if "bajista" in reason else 
        0 for reason in reasons
    ])
    
    # Horizonte temporal
    time_horizon = []
    time_reasons = []
    
    # Corto plazo
    if (macd > signal) and (30 < rsi < 70) and (price > sma20):
        time_horizon.append("corto plazo")
        time_reasons.append("Momentum positivo reciente")
    
    # Mediano plazo
    if (sma20 > sma50) and (hist['SMA20'].iloc[-10] < sma20):
        time_horizon.append("mediano plazo") 
        time_reasons.append("Tendencia intermedia positiva")
    
    # Largo plazo
    if (sma50 > hist['SMA50'].iloc[-60]) and (price > sma50):
        time_horizon.append("largo plazo")
        time_reasons.append("Tendencia secular alcista")
    
    # Recomendación final
    if buy_score > 1:
        recommendation = "COMPRAR🚀"
    elif buy_score < -1:
        recommendation = "NO COMPRAR⛔"
    else:
        recommendation = "NEUTRAL⚖️"
    
    # Formatear horizonte
    time_str = "\n".join(time_reasons) if time_reasons else "Sin horizonte claro"
    
    return recommendation, reasons, time_str

# ------------------------------------------------------------------------------------
# Sección 2: Notificaciones por Telegram
# ------------------------------------------------------------------------------------

def send_telegram_message(message):
    if not all([config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID]):
        return False
    
    url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": config.TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    try:
        response = requests.post(url, json=payload)
        return response.ok
    except:
        return False

def load_sp500_tickers():
    try:
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        df = pd.read_html(url)[0]  # Lee la primera tabla
        tickers = df['Symbol'].tolist()  # Extrae la primera columna con los tickers
        tickers = [ticker.replace('.', '-') for ticker in tickers]  # Limpieza básica
        return tickers
    except Exception as e:
        print(f"Error al cargar tickers: {e}")
        return ['NVDA', 'TSLA', 'AAPL', 'AMD', 'META', 'AMZN', 'GOOG', 'MSFT']

# Función que procesa un solo ticker
def process_ticker(ticker):
    try:
        data, latest = get_technical_analysis(ticker)
        if data is None or latest is None:
            return None
        
        
        recommendation, reasons, time_analysis = generate_recommendation(data, latest)
        
        if recommendation == "COMPRAR🚀" and "corto plazo" in time_analysis:
            entry_price = latest['LowerBand'] if latest['BB_Percent'] < 30 else latest['SMA20']
            return {
                'ticker': ticker,
                'price': latest['Close'],
                'entry': entry_price,
                'target': latest['UpperBand'],
                'reasons': reasons[:3]
            }
    except Exception as e:
         print(f"Error procesando {ticker}: {e}")  # Opcional: descomentar para debug
    return None

def get_investment_recommendations():
    tickers = load_sp500_tickers()
    recommendations = []
    batch_size = 50  # Procesar 50 tickers a la vez
    max_recommendations = 5  # Límite de recomendaciones a retornar

    # Dividir la lista de tickers en batches
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]  # Obtener el siguiente batch de tickers
        print(f"Procesando batch {i//batch_size + 1}: {len(batch)} tickers")

        # Procesar el batch actual con concurrencia
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(process_ticker, ticker): ticker for ticker in batch}

            try:
                for future in concurrent.futures.as_completed(futures):
                    try:
                        result = future.result(timeout=15)  # Timeout por futuro
                        if result:
                            recommendations.append(result)
                            if len(recommendations) >= max_recommendations:
                                break
                    except (concurrent.futures.TimeoutError, Exception) as e:
                        continue

            finally:
                # Cancelar todas las tareas pendientes en este batch
                for f in futures:
                    f.cancel()
                executor.shutdown(wait=False)

        # Detener el procesamiento si ya se alcanzó el límite de recomendaciones
        if len(recommendations) >= max_recommendations:
            break

    return recommendations[:max_recommendations]

def get_intraday_analysis(ticker):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d", interval="5m")  # Datos intradía cada 5 minutos
        
        if hist.empty:
            return None, "No hay datos intradía para este ticker."
        
        # Calcular cambios porcentuales y volumen promedio
        hist['PctChange'] = hist['Close'].pct_change() * 100
        avg_volume = hist['Volume'].mean()
        
        # Último dato
        latest = hist.iloc[-1].copy()
        latest['AvgVolume'] = avg_volume
        
        return hist, latest
    
    except Exception as e:
        return None, f"Error: {str(e)}"
    
    

def find_intraday_opportunities():
    tickers = load_sp500_tickers()
    opportunities = []
    batch_size = 50  # Procesar 50 tickers por lote
    max_opportunities = 5  # Máximo de oportunidades a retornar
    
    # Función para procesar un ticker individual
    def process_intraday_ticker(ticker):
        try:
            data, latest = get_intraday_analysis(ticker)
            if data is None or latest is None:
                return None
            
            pct_change = latest.get('PctChange', 0)
            avg_volume = latest.get('AvgVolume', 1)  # Evitar división por cero
            volume_ratio = latest['Volume'] / avg_volume if avg_volume != 0 else 0
            
            if pct_change > 2 and volume_ratio > 2:
                return {
                    'ticker': ticker,
                    'price': latest['Close'],
                    'pct_change': pct_change,
                    'volume_ratio': volume_ratio,
                    'timestamp': latest.name.strftime("%H:%M")  # Hora del último dato
                }
            return None
            
        except Exception as e:
            # print(f"Error en {ticker}: {str(e)}")  # Descomentar para debug
            return None

    # Procesamiento por batches
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        print(f"Procesando batch intradía {i//batch_size + 1}: {len(batch)} tickers")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:  # Más workers para velocidad
            futures = {executor.submit(process_intraday_ticker, ticker): ticker for ticker in batch}
            
            try:
                for future in concurrent.futures.as_completed(futures):
                    result = future.result(timeout=10)  # Timeout más ajustado
                    if result:
                        opportunities.append(result)
                        if len(opportunities) >= max_opportunities:
                            break
            except concurrent.futures.TimeoutError:
                continue
            finally:
                # Limpieza de recursos
                for f in futures:
                    f.cancel()
                executor.shutdown(wait=False)
        
        if len(opportunities) >= max_opportunities:
            break
    
    # Ordenar por mejor oportunidad
    return sorted(
        opportunities[:max_opportunities], 
        key=lambda x: (x['pct_change'], x['volume_ratio']), 
        reverse=True
    )

def show_glossary():
    print("\n📚 Glosario de Conceptos de Trading")
    print("\n=== Análisis Técnico ===")
    print("""
- SMA (Media Móvil Simple): Promedio del precio de cierre durante un período específico. 
  Ej: SMA20 = tendencia corto plazo, SMA50 = mediano plazo.

- RSI (Índice de Fuerza Relativa): Indicador de momentum (0-100). 
  >70 = sobrecompra, <30 = sobreventa.

- MACD: Relación entre dos medias móviles exponenciales (12 y 26 días). 
  Cruce arriba de la línea de señal = momentum alcista.

- Bandas de Bollinger: SMA20 + 2 desviaciones estándar (superior), 
  SMA20 - 2 desviaciones estándar (inferior). Precio cerca de la banda 
  inferior = posible rebote, cerca de superior = posible corrección.

- Volumen Promedio: Cantidad promedio de acciones negociadas. 
  Volumen alto confirma fuerza en la tendencia.
    """)
    
    print("\n=== Análisis Fundamental ===")
    print("""
- Ratio P/E (Precio/Beneficio): Precio por acción dividido por ganancias 
  por acción. Alto = posible sobrevaloración.

- Ratio P/B (Precio/Valor Contable): Compara valor de mercado con valor 
  contable. Útil para empresas con muchos activos tangibles.

- ROE (Retorno sobre Patrimonio): Beneficios netos / patrimonio de accionistas. 
  Mide eficiencia en uso de capital.

- EPS (Ganancias por Acción): Beneficio neto dividido por acciones en circulación. 
  Indica rentabilidad por acción.

- Capitalización de Mercado: Precio acción × acciones en circulación. 
  Clasifica empresas por tamaño (pequeña, mediana, gran capitalización).

- Dividend Yield: Dividendo anual / precio acción. Muestra rendimiento por dividendos.

- Deuda/Patrimonio: Deuda total / patrimonio accionistas. Alto ratio = mayor riesgo.

- Flujo de Caja Libre: Efectivo disponible después de operaciones e inversiones. 
  Alto = capacidad para pagar deudas/dividendos.

- Margen Operativo: (Beneficio operativo / ingresos) × 100. 
  Eficiencia en operaciones principales.

- Crecimiento de Ingresos: % de aumento anual en ventas. 
  Crecimiento consistente = negocio saludable.

- Ratio PEG: P/E ÷ tasa crecimiento ganancias. <1 = acción posiblemente subvalorada.

- EBITDA: Beneficios antes de intereses, impuestos, depreciación y amortización. 
  Mide rentabilidad operativa bruta.

- Ratio Corriente: Activos corrientes / pasivos corrientes. 
  >1 = buena capacidad para pagar obligaciones a corto plazo.
    """)

# ------------------------------------------------------------------------------------
# Interfaz de Usuario
# ------------------------------------------------------------------------------------

def print_header():
    print("\n" + "="*40)
    print(f"=== TradingBot v1.0 - {datetime.now().strftime('%d/%m/%Y %H:%M')} ===")
    print("="*40)

def main_menu():
    print_header()
    print("\n1. Analizar activo individual")
    print("2. Obtener recomendaciones del día")
    print("3. Buscar oportunidades intradía")
    print("4. Glosario (Explicación de conceptos)")
    print("5. Salir")
    return input("\nSeleccione una opción: ")

def show_intraday_opportunities():
    print("\n🔎 Buscando oportunidades intradía...")
    opportunities = find_intraday_opportunities()
    
    if not opportunities:
        print("\n⚠️ No se encontraron oportunidades intradía fuertes")
        return
    
    print(f"\n🔥 Top {len(opportunities)} oportunidades intradía:")
    for idx, opp in enumerate(opportunities, 1):
        print(f"""{idx}. {opp['ticker']}
                Precio actual: ${opp['price']:.2f}
                Cambio (%): {opp['pct_change']:.2f}%
                Volumen: {opp['volume_ratio']:.1f}x promedio
                Hora detección: {opp['timestamp']}""")
                

def analyze_single_ticker():
    ticker = input("\nIngrese el símbolo del activo (ej: BTC-USD): ").upper()
    data, latest = get_technical_analysis(ticker)
    
    if data is None:
        print(f"\n❌ Error: {latest}")
        return
    
    recommendation, reasons, time_analysis = generate_recommendation(data, latest)
    price = latest['Close']
    
    print(f"\n📈 Análisis de {ticker} - ${price:.2f}")
    print(f"\n🔥 Recomendación: {recommendation}")
    
    if recommendation == "COMPRAR🚀":
        entry = latest['LowerBand'] if latest['BB_Percent'] < 30 else latest['SMA20']
        print(f"\n🎯 Entrada: ${entry:.2f}")
        print(f"🎯 Objetivo: ${latest['UpperBand']:.2f}")
    
    print("\n🔍 Señales técnicas:")
    for reason in reasons:
        print(f" - {reason}")
    
    print("\n📅 Horizonte temporal:")
    print(time_analysis)
    
    print("\n" + get_fundamental_analysis(ticker))
    
    #if input("\n¿Enviar a Telegram? (s/n): ").lower() == 's':
     #   telegram_msg = (
      #      f"*{ticker} - ${price:.2f}*\n"
      #      f"Recomendación: {recommendation}\n"
       #     f"Señales:\n- " + "\n- ".join(reasons) + 
       #     f"\n\nFundamentales:\n{get_fundamental_analysis(ticker)}"
       # )
      #  if send_telegram_message(telegram_msg):
       #     print("✅ Mensaje enviado")
      #  else:
       #     print("❌ Error en el envío")

def show_daily_recommendations():
    print("\n🔎 Buscando oportunidades...")
    recommendations = get_investment_recommendations()
    
    if not recommendations:
        print("\n⚠️ No se encontraron oportunidades fuertes")
        return
    
    print("\n🔥 Top oportunidades detectadas:")
    for idx, asset in enumerate(recommendations, 1):
        print(f"\n{idx}. {asset['ticker']}")
        print(f"   Precio actual: ${asset['price']:.2f}")
        print(f"   Entrada ideal: ${asset['entry']:.2f}")
        print(f"   Objetivo: ${asset['target']:.2f}")
        print("   Señales destacadas:")
        for reason in asset['reasons'][:2]:
            print(f"    - {reason}")

def main():
    while True:
        choice = main_menu()
        
        if choice == '1':
            analyze_single_ticker()
        elif choice == '2':
            show_daily_recommendations()
        elif choice == '3':
            show_intraday_opportunities()
        elif choice == '4':  # Nueva opción de glosario
            show_glossary()
        elif choice == '5':  # Opción Salir movida a 5
            print("\n✅ Sesión finalizada")
            break
        else:
            print("\n❌ Opción inválida")
        
        input("\nPresione Enter para continuar...")

if __name__ == "__main__":
    main()