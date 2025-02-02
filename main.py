import yfinance as yf
import pandas as pd
from datetime import datetime
import os

# Configuración inicial
CSV_PATH = "my_portfolio.csv"

# ------------------------------------------------------------------------------------
# Sección 1: Análisis Técnico para Recomendar Compra/Venta
# ------------------------------------------------------------------------------------

def get_technical_analysis(ticker):
    """
    Obtiene datos históricos y calcula indicadores técnicos para un ticker.
    """
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="6mo")  # Últimos 6 meses de datos
        
        if hist.empty:
            return None, "No hay datos suficientes para este ticker."
        
        # Calcular indicadores técnicos
        # 1. Media Móvil Simple (SMA) de 20 y 50 días
        hist['SMA20'] = hist['Close'].rolling(window=20).mean()
        hist['SMA50'] = hist['Close'].rolling(window=50).mean()
        
        # 2. RSI (Relative Strength Index)
        delta = hist['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        hist['RSI'] = 100 - (100 / (1 + rs))
        
        # 3. MACD
        hist['EMA12'] = hist['Close'].ewm(span=12, adjust=False).mean()
        hist['EMA26'] = hist['Close'].ewm(span=26, adjust=False).mean()
        hist['MACD'] = hist['EMA12'] - hist['EMA26']
        hist['Signal'] = hist['MACD'].ewm(span=9, adjust=False).mean()
        
        latest = hist.iloc[-1]
        return hist, latest
    
    except Exception as e:
        return None, f"Error: {str(e)}"

def generate_recommendation(latest_data):
    """
    Genera una recomendación basada en los indicadores técnicos.
    """
    reasons = []
    
    # Estrategia de ejemplo (personalizable):
    # - SMA20 > SMA50: Tendencia alcista
    # - RSI < 30: Sobreventa (oportunidad de compra)
    # - MACD cruza arriba de la línea de señal: Compra
    
    # 1. Comparar SMA20 y SMA50
    if latest_data['SMA20'] > latest_data['SMA50']:
        reasons.append("Tendencia alcista (SMA20 > SMA50)")
    else:
        reasons.append("Tendencia bajista (SMA20 < SMA50)")
    
    # 2. Evaluar RSI
    if latest_data['RSI'] < 30:
        reasons.append("RSI indica sobreventa (oportunidad de compra)")
    elif latest_data['RSI'] > 70:
        reasons.append("RSI indica sobrecompra (posible venta)")
    else:
        reasons.append("RSI en rango neutral")
    
    # 3. Evaluar MACD vs Signal
    if latest_data['MACD'] > latest_data['Signal']:
        reasons.append("MACD cruza arriba de la señal (compra)")
    else:
        reasons.append("MACD cruza abajo de la señal (venta)")
    
    # Decisión final (lógica simplificada)
    buy_signals = sum([1 for reason in reasons if "compra" in reason.lower()])
    sell_signals = sum([1 for reason in reasons if "venta" in reason.lower()])
    
    if buy_signals > sell_signals:
        return "COMPRAR", reasons
    else:
        return "NO COMPRAR", reasons

# ------------------------------------------------------------------------------------
# Sección 2: Gestión de Compras (CSV como base de datos)
# ------------------------------------------------------------------------------------

def load_portfolio():
    """Carga el CSV con las compras existentes."""
    if os.path.exists(CSV_PATH):
        return pd.read_csv(CSV_PATH)
    else:
        return pd.DataFrame(columns=["Ticker", "Fecha", "Precio", "Cantidad"])

def save_purchase(ticker, price, quantity):
    """Guarda una nueva compra en el CSV."""
    df = load_portfolio()
    new_row = {
        "Ticker": ticker,
        "Fecha": datetime.now().strftime("%Y-%m-%d"),
        "Precio": price,
        "Cantidad": quantity
    }
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    df.to_csv(CSV_PATH, index=False)

# ------------------------------------------------------------------------------------
# Interfaz de Usuario (CLI)
# ------------------------------------------------------------------------------------

def main():
    while True:
        print("\n=== BOT FINANCIERO ===")
        print("1. Analizar un ticker")
        print("2. Registrar una compra")
        print("3. Salir")
        
        choice = input("Selecciona una opción: ")
        
        if choice == "1":
            ticker = input("Ingresa el ticker (ej: AAPL): ").upper()
            data, latest = get_technical_analysis(ticker)
            
            if data is None:
                print(latest)  # Mensaje de error
                continue
            
            recommendation, reasons = generate_recommendation(latest)
            
            print(f"\nAnálisis para {ticker} (Precio actual: ${latest['Close']:.2f})")
            print(f"Recomendación: {recommendation}")
            print("\nRazones:")
            for reason in reasons:
                print(f"- {reason}")
                
        elif choice == "2":
            ticker = input("Ticker comprado (ej: TSLA): ").upper()
            price = float(input("Precio por acción: "))
            quantity = int(input("Cantidad: "))
            save_purchase(ticker, price, quantity)
            print("¡Compra registrada exitosamente!")
            
        elif choice == "3":
            print("¡Hasta luego!")
            break
            
        else:
            print("Opción no válida.")

if __name__ == "__main__":
    main()