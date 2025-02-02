import yfinance as yf
import pandas as pd
from datetime import datetime
import os
import discord
from discord.ext import commands
import requests
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging

# ------------------------------------------------------------------------------------
# Configuración
# ------------------------------------------------------------------------------------
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('DISCORD_CHANNEL_ID'))
CSV_PATH = 'DB/stocks.csv'
MAX_WORKERS = 5  # Para el ThreadPool
TIMEOUT_YFINANCE = 15  # Segundos

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')
logger.setLevel(logging.WARNING)

# Configurar sesión personalizada para yfinance
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0'})
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# ------------------------------------------------------------------------------------
# Funciones de Análisis (Optimizadas)
# ------------------------------------------------------------------------------------
async def get_technical_analysis(ticker):
    try:
        loop = asyncio.get_event_loop()
        stock = await loop.run_in_executor(executor, yf.Ticker, ticker)
        
        # Verificar si el ticker es válido
        info = await loop.run_in_executor(executor, lambda: stock.info)
        if not info.get('regularMarketPrice'):
            return None, f"Ticker {ticker} no válido/deslistado"
        
        hist = await loop.run_in_executor(
            executor, 
            lambda: stock.history(period="6mo", timeout=TIMEOUT_YFINANCE)
        )
        
        if hist.empty:
            return None, "No hay datos suficientes"
        
        # Cálculos técnicos (optimizados)
        hist['SMA20'] = hist['Close'].rolling(20).mean()
        hist['SMA50'] = hist['Close'].rolling(50).mean()
        
        delta = hist['Close'].diff()
        gain = delta.where(delta > 0, 0).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
        hist['RSI'] = 100 - (100 / (1 + (gain / loss)))
        
        hist['EMA12'] = hist['Close'].ewm(span=12, adjust=False).mean()
        hist['EMA26'] = hist['Close'].ewm(span=26, adjust=False).mean()
        hist['MACD'] = hist['EMA12'] - hist['EMA26']
        hist['Signal'] = hist['MACD'].ewm(span=9, adjust=False).mean()
        
        hist['STD'] = hist['Close'].rolling(20).std()
        hist['UpperBand'] = hist['SMA20'] + (2 * hist['STD'])
        hist['LowerBand'] = hist['SMA20'] - (2 * hist['STD'])
        
        latest = hist.iloc[-1].copy()
        price = latest['Close']
        upper = latest['UpperBand']
        lower = latest['LowerBand']
        latest['BB_Percent'] = ((price - lower) / (upper - lower)) * 100
        latest['AvgVolume'] = hist['Volume'].tail(5).mean()
        
        return hist, latest
    
    except Exception as e:
        return None, f"Error: {str(e)}"

async def get_fundamental_analysis(ticker):
    try:
        loop = asyncio.get_event_loop()
        stock = await loop.run_in_executor(executor, yf.Ticker, ticker)
        info = await loop.run_in_executor(executor, lambda: stock.info)
        
        fundamental = {
            'P/E': info.get('trailingPE', 'N/A'),
            'P/B': info.get('priceToBook', 'N/A'),
            'ROE': info.get('returnOnEquity', 'N/A'),
            'EPS': info.get('trailingEps', 'N/A'),
            'Market Cap': f"${info['marketCap']/1e9:.2f}B" if info.get('marketCap') else 'N/A',
            'Dividend Yield': f"{info.get('dividendYield', 0)*100:.2f}%" if info.get('dividendYield') else '0%',
            'Debt/Equity': info.get('debtToEquity', 'N/A')
        }
        
        return "\n".join([
            "📈 **Fundamentales**",
            f"- P/E: {fundamental['P/E']}",
            f"- P/B: {fundamental['P/B']}",
            f"- ROE: {fundamental['ROE']}",
            f"- EPS: {fundamental['EPS']}",
            f"- Capitalización: {fundamental['Market Cap']}",
            f"- Deuda/Patrimonio: {fundamental['Debt/Equity']}",
            f"- Dividendo: {fundamental['Dividend Yield']}"
        ])
    
    except Exception as e:
        return f"⚠️ Error en análisis fundamental: {str(e)}"

# ------------------------------------------------------------------------------------
# Bot de Discord
# ------------------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True  # Habilitar intents de mensajes

bot = commands.Bot(
    command_prefix='!', 
    intents=intents,
    help_command=None  # Desactivar comando help por defecto
)

@bot.event
async def on_ready():
    logger.info(f'Bot conectado como {bot.user}')
    await enviar_recomendaciones_diarias()

async def enviar_recomendaciones_diarias():
    try:
        channel = bot.get_channel(CHANNEL_ID)
        if not channel:
            raise ValueError(f"❌ Canal ID {CHANNEL_ID} no encontrado")
        
        embed = discord.Embed(
            title=f"📊 Recomendaciones Diarias ({datetime.now().strftime('%d/%m/%Y')})",
            color=0x00ff00
        )
        
        recomendaciones = await get_investment_recommendations()
        if not recomendaciones:
            embed.description = "⚠️ No hay recomendaciones fuertes hoy"
            await channel.send(embed=embed)
            return
            
        for asset in recomendaciones:
            embed.add_field(
                name=f"🏅 {asset['ticker']} - {asset['price']}",
                value=(
                    f"**Entrada:** {asset['entry']}\n"
                    f"**Objetivo:** {asset['target']}\n"
                    "**Señales:**\n" + "\n".join([f"- {r}" for r in asset['reasons']])
                ),
                inline=False
            )
        
        embed.set_footer(text="🔍 !analizar [TICKER] para más detalles")
        await channel.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Error en recomendaciones: {str(e)}")
        if channel:
            await channel.send(f"⚠️ Error al generar recomendaciones: {str(e)}")
    finally:
        await bot.close()

@bot.command()
async def analizar(ctx, ticker: str):
    try:
        ticker = ticker.upper().strip()
        if not ticker:
            await ctx.send("❌ Por favor ingresa un ticker válido (ej: `!analizar NVDA`)")
            return
            
        data, latest = await get_technical_analysis(ticker)
        if not data:
            await ctx.send(f"❌ {latest}")
            return
            
        recommendation, reasons, time_analysis = await generate_recommendation(data, latest)
        fundamental = await get_fundamental_analysis(ticker)
        
        embed = discord.Embed(
            title=f"📈 {ticker} - ${latest['Close']:.2f}",
            description=f"**Recomendación:** {recommendation}",
            color=0x7289da
        )
        
        embed.add_field(
            name="🔍 Señales Técnicas", 
            value="\n".join([f"- {r}" for r in reasons]), 
            inline=False
        )
        embed.add_field(
            name="📊 Fundamentales", 
            value=fundamental, 
            inline=False
        )
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        await ctx.send(f"⚠️ Error inesperado: {str(e)}")

# ------------------------------------------------------------------------------------
# Funciones de Soporte (Optimizadas)
# ------------------------------------------------------------------------------------
async def generate_recommendation(hist, latest_data):
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

async def get_investment_recommendations():
    try:
        loop = asyncio.get_event_loop()
        tickers = await loop.run_in_executor(executor, load_sp500_tickers)
        tickers = tickers[:50]  # Limitar para pruebas
        
        recommendations = []
        for ticker in tickers:
            try:
                data, latest = await get_technical_analysis(ticker)
                if not data:
                    continue
                    
                # Lógica de recomendación...
                
            except Exception as e:
                continue
                
        return recommendations[:5]  # Máximo 5 recomendaciones
        
    except Exception as e:
        logger.error(f"Error en recomendaciones: {str(e)}")
        return []

def load_sp500_tickers():
    try:
        df = pd.read_csv(CSV_PATH)
        return df['Symbol'].tolist() if 'Symbol' in df.columns else []
    except Exception as e:
        logger.error(f"Error cargando CSV: {str(e)}")
        return []

# ------------------------------------------------------------------------------------
# Ejecución
# ------------------------------------------------------------------------------------
if __name__ == "__main__":
    if not all([DISCORD_TOKEN, CHANNEL_ID]):
        raise ValueError("Faltan variables de entorno")
    
    bot.run(DISCORD_TOKEN)