import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import discord
from discord.ext import commands
import requests

# ------------------------------------------------------------------------------------
# Configuración de Entorno (GitHub Secrets)
# ------------------------------------------------------------------------------------
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
CSV_PATH = 'DB/stocks.csv'  # Asegúrate de subir este archivo al repositorio

# ------------------------------------------------------------------------------------
# Funciones de Análisis (Mantienen la misma lógica original)
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
        
        fundamental = {
            'P/E Ratio': info.get('trailingPE', 'N/A'),
            'P/B Ratio': info.get('priceToBook', 'N/A'),
            'ROE': info.get('returnOnEquity', 'N/A'),
            'EPS': info.get('trailingEps', 'N/A'),
            'Market Cap': info.get('marketCap', 'N/A'),
            'Dividend Yield': info.get('dividendYield', 'N/A'),
            'Debt/Equity': info.get('debtToEquity', 'N/A')
        }
        
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
    
    sma20 = latest_data['SMA20']
    sma50 = latest_data['SMA50']
    trend = "alcista" if sma20 > sma50 else "bajista"
    reasons.append(f"SMA20 (${sma20:.2f}) < SMA50 (${sma50:.2f}) → Tendencia {trend}")
    
    rsi = latest_data['RSI']
    if rsi < 30:
        reasons.append(f"RSI: {rsi:.2f} (Sobreventa, <30)")
    elif rsi > 70:
        reasons.append(f"RSI: {rsi:.2f} (Sobrecompra, >70)")
    else:
        reasons.append(f"RSI: {rsi:.2f} (Neutral)")
    
    macd = latest_data['MACD']
    signal = latest_data['Signal']
    if macd > signal:
        reasons.append(f"MACD ({macd:.2f}) > Señal ({signal:.2f}) → Momentum alcista")
    else:
        reasons.append(f"MACD ({macd:.2f}) < Señal ({signal:.2f}) → Momentum bajista")
    
    bb_percent = latest_data['BB_Percent']
    if bb_percent > 80:
        reasons.append(f"Bollinger Bands: Precio cerca de banda superior ({bb_percent:.2f}%)")
    elif bb_percent < 20:
        reasons.append(f"Bollinger Bands: Precio cerca de banda inferior ({bb_percent:.2f}%)")
    else:
        reasons.append(f"Bollinger Bands: Precio en zona media ({bb_percent:.2f}%)")
    
    avg_volume = latest_data['AvgVolume']
    latest_volume = latest_data['Volume']
    if latest_volume > avg_volume * 1.5:
        reasons.append(f"Volumen actual ({latest_volume:.0f}) > Promedio ({avg_volume:.0f}) → Alta actividad")
    
    buy_score = sum([
        1 if "alcista" in reason else 
        -1 if "bajista" in reason else 
        0 for reason in reasons
    ])
    
    time_horizon = []
    time_reasons = []
    
    if (macd > signal) and (30 < rsi < 70) and (price > sma20):
        time_horizon.append("corto plazo")
        time_reasons.append("Momentum positivo con indicadores técnicos favorables")
    
    if (sma20 > sma50) and (hist['SMA20'].iloc[-10] < sma20) and (hist['SMA50'].iloc[-20] < sma50):
        time_horizon.append("mediano plazo") 
        time_reasons.append("Tendencia intermedia positiva")
    
    if (sma50 > hist['SMA50'].iloc[-60]) and (price > sma50):
        time_horizon.append("largo plazo")
        time_reasons.append("Tendencia secular alcista")
    
    if buy_score > 1:
        recommendation = "COMPRAR"
    elif buy_score < -1:
        recommendation = "NO COMPRAR"
    else:
        recommendation = "NEUTRAL"
    
    time_str = f"Recomendado para: {', '.join(time_horizon)}\n" + "\n".join(time_reasons) if time_horizon else "No se recomienda para ningún horizonte específico"
    
    return recommendation, reasons, time_str

def load_sp500_tickers(csv_path=CSV_PATH):
    try:
        df = pd.read_csv(csv_path)
        return df['Symbol'].tolist() if 'Symbol' in df.columns else []
    except Exception as e:
        print(f"Error al cargar CSV: {e}")
        return []

def get_investment_recommendations():
    tickers = load_sp500_tickers() or ['NVDA', 'TSLA', 'AAPL', 'AMD', 'META', 'AMZN', 'GOOG', 'MSFT']
    recommendations = []
    
    for ticker in tickers:
        try:
            data, latest = get_technical_analysis(ticker)
            if not data:
                continue
                
            recommendation, reasons, time_analysis = generate_recommendation(data, latest)
            
            if recommendation == "COMPRAR" and "corto plazo" in time_analysis:
                price = latest['Close']
                entry_price = latest['LowerBand'] if latest['BB_Percent'] < 30 else latest['SMA20']
                
                reasons_filtered = [
                    r for r in reasons 
                    if any(keyword in r for keyword in ['SMA20', 'RSI', 'MACD', 'Bollinger', 'Volumen'])
                ][:3]
                
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
# Configuración del Bot de Discord
# ------------------------------------------------------------------------------------
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    await enviar_recomendaciones_diarias()

async def enviar_recomendaciones_diarias():
    try:
        channel = bot.get_channel(CHANNEL_ID)
        recomendaciones = get_investment_recommendations()
        
        embed = discord.Embed(
            title=f"📈 Recomendaciones Diarias ({datetime.now().strftime('%d/%m/%Y')})",
            color=0x00ff00
        )
        
        if not recomendaciones:
            embed.description = "⚠️ No hay recomendaciones fuertes hoy."
            await channel.send(embed=embed)
            return
            
        for asset in recomendaciones:
            embed.add_field(
                name=f"🏅 {asset['ticker']}",
                value=(
                    f"**Precio:** {asset['price']}\n"
                    f"**Entrada:** {asset['entry']}\n"
                    f"**Objetivo:** {asset['target']}\n"
                    "**Señales:**\n" + "\n".join([f"- {r}" for r in asset['reasons']])
                ),
                inline=False
            )
        
        embed.set_footer(text="⚠️ No es asesoría financiera")
        await channel.send(embed=embed)
        
    except Exception as e:
        error_msg = f"🚨 Error: {str(e)}"
        await channel.send(error_msg)
    finally:
        await bot.close()

@bot.command()
async def analizar(ctx, ticker: str):
    try:
        data, latest = get_technical_analysis(ticker.upper())
        
        if not data:
            await ctx.send(f"❌ Error: {latest}")
            return
            
        recommendation, reasons, time_analysis = generate_recommendation(data, latest)
        fundamental = get_fundamental_analysis(ticker)
        
        embed = discord.Embed(
            title=f"📊 {ticker.upper()} - ${latest['Close']:.2f}",
            description=f"**Recomendación:** {recommendation}",
            color=0x7289da
        )
        
        embed.add_field(name="🔍 Señales Técnicas", value="\n".join([f"- {r}" for r in reasons]), inline=False)
        embed.add_field(name="📈 Fundamentos", value=fundamental, inline=False)
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"❌ Error: {str(e)}")

if __name__ == "__main__":
    if not all([DISCORD_TOKEN, CHANNEL_ID]):
        raise ValueError("Faltan variables de entorno: DISCORD_TOKEN o DISCORD_CHANNEL_ID")
    bot.run(DISCORD_TOKEN)