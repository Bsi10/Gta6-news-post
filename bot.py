import os
import asyncio
import requests
import json
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime, timedelta

# === CONFIG ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
RENDER_URL = os.environ.get("RENDER_URL")

# === FLASK ===
app = Flask(__name__)

# === APPLICATION TELEGRAM ===
application = Application.builder().token(BOT_TOKEN).build()

# ==========================================
# === SOURCE 1: NewsAPI (actualités web) ===
# ==========================================
def fetch_newsapi():
    url = "https://newsapi.org/v2/everything"
    
    # Dernières 24h
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    params = {
        "q": "GTA6 OR \"GTA 6\" OR \"Grand Theft Auto 6\"",
        "sortBy": "popularity",
        "language": "en",
        "pageSize": 3,
        "from": yesterday,
        "apiKey": NEWS_API_KEY
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        data = response.json()
        
        if data.get("status") != "ok":
            return None
        
        articles = data.get("articles", [])
        if not articles:
            return None
        
        news_list = []
        for i, article in enumerate(articles[:3], 1):
            title = article.get("title", "Pas de titre")[:100]
            link = article.get("url", "")
            source = article.get("source", {}).get("name", "Inconnu")
            description = article.get("description", "")
            
            news_list.append(
                f"📰 *News #{i}* | {source}\n"
                f"*{title}*\n"
                f"_{description[:150]}..._\n"
                f"[Lire l'article]({link})"
            )
        
        return "\n\n" + "\n\n".join(news_list)
    
    except Exception as e:
        return f"❌ Erreur NewsAPI: {str(e)[:100]}"

# =====================================
# === SOURCE 2: Reddit r/GTA6       ===
# =====================================
def fetch_reddit():
    url = "https://www.reddit.com/r/GTA6/hot.json"
    headers = {
        "User-Agent": "GTA6NewsBot/1.0"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        posts = data.get("data", {}).get("children", [])[:5]
        if not posts:
            return None
        
        news_list = []
        for i, post in enumerate(posts[:3], 1):
            post_data = post.get("data", {})
            title = post_data.get("title", "Pas de titre")[:150]
            url = f"https://reddit.com{post_data.get('permalink', '')}"
            author = post_data.get("author", "Anonyme")
            ups = post_data.get("ups", 0)
            num_comments = post_data.get("num_comments", 0)
            text = post_data.get("selftext", "")[:200]
            
            news_list.append(
                f"🔸 *Post Reddit #{i}*\n"
                f"*{title}*\n"
                f"👍 {ups} upvotes | 💬 {num_comments} commentaires\n"
                f"👤 u/{author}\n"
                f"_{text}..._\n"
                f"[Voir sur Reddit]({url})"
            )
        
        return "\n\n" + "\n\n".join(news_list)
    
    except Exception as e:
        return f"❌ Erreur Reddit: {str(e)[:100]}"

# ============================================
# === SOURCE 3: Google News RSS (scraping) ===
# ============================================
def fetch_google_news():
    url = "https://news.google.com/rss/search"
    params = {
        "q": "GTA6 OR \"GTA 6\"",
        "hl": "en-US",
        "gl": "US",
        "ceid": "US:en"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        
        # Parser le RSS simplement
        import xml.etree.ElementTree as ET
        root = ET.fromstring(response.text)
        
        items = root.findall(".//item")[:3]
        if not items:
            return None
        
        news_list = []
        for i, item in enumerate(items, 1):
            title = item.find("title").text if item.find("title") is not None else "Pas de titre"
            title = title.split(" - ")[0][:100]  # Enlever la source à la fin
            
            link = item.find("link").text if item.find("link") is not None else ""
            source = item.find("source").text if item.find("source") is not None else "Inconnu"
            
            # Date
            pub_date = item.find("pubDate")
            date_str = pub_date.text if pub_date is not None else ""
            
            news_list.append(
                f"🌐 *News #{i}* | {source}\n"
                f"*{title}*\n"
                f"📅 {date_str[:25]}\n"
                f"[Lire l'article]({link})"
            )
        
        return "\n\n" + "\n\n".join(news_list)
    
    except Exception as e:
        return f"❌ Erreur Google News: {str(e)[:100]}"

# ===================
# === COMMANDES    ===
# ===================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 *GTA6 News Bot*\n\n"
        "Commandes disponibles :\n"
        "📰 /news - News des sites d'actualité (NewsAPI)\n"
        "🔸 /reddit - Posts populaires de r/GTA6\n"
        "🌐 /googlenews - Google News GTA6\n"
        "🔄 /all - Toutes les sources\n"
        "❓ /start - Ce message",
        parse_mode="Markdown"
    )

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Recherche sur les sites d'actualité...")
    
    news = fetch_newsapi()
    
    if news:
        await msg.edit_text("✅ News trouvées ! Envoi en cours...")
        await update.message.reply_text(news, parse_mode="Markdown", disable_web_page_preview=True)
        await msg.delete()
    else:
        await msg.edit_text("❌ Aucune news trouvée sur NewsAPI. Réessaie plus tard.")

async def reddit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Recherche sur Reddit r/GTA6...")
    
    news = fetch_reddit()
    
    if news:
        await msg.edit_text("✅ Posts Reddit trouvés ! Envoi en cours...")
        await update.message.reply_text(news, parse_mode="Markdown", disable_web_page_preview=True)
        await msg.delete()
    else:
        await msg.edit_text("❌ Aucun post trouvé sur Reddit. Réessaie plus tard.")

async def googlenews_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Recherche sur Google News...")
    
    news = fetch_google_news()
    
    if news:
        await msg.edit_text("✅ News Google trouvées ! Envoi en cours...")
        await update.message.reply_text(news, parse_mode="Markdown", disable_web_page_preview=True)
        await msg.delete()
    else:
        await msg.edit_text("❌ Aucune news trouvée sur Google News. Réessaie plus tard.")

async def all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔄 Recherche sur TOUTES les sources...")
    
    # Fetch tout en parallèle (synchrone ici mais ok)
    sources = [
        ("📰 NewsAPI", fetch_newsapi()),
        ("🔸 Reddit", fetch_reddit()),
        ("🌐 Google News", fetch_google_news())
    ]
    
    await msg.edit_text("📡 Connexion à toutes les sources...")
    
    results = []
    for name, data in sources:
        if data and not data.startswith("❌"):
            results.append(f"*{name}*\n{data}")
    
    if results:
        await msg.edit_text("✅ Résultats compilés ! Envoi en cours...")
        for result in results:
            await update.message.reply_text(result, parse_mode="Markdown", disable_web_page_preview=True)
            await asyncio.sleep(1)  # Éviter le flood
        await msg.delete()
    else:
        await msg.edit_text("❌ Aucune news trouvée sur aucune source. Réessaie plus tard.")

# === AJOUTER LES HANDLERS ===
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("news", news_command))
application.add_handler(CommandHandler("reddit", reddit_command))
application.add_handler(CommandHandler("googlenews", googlenews_command))
application.add_handler(CommandHandler("all", all_command))

# === WEBHOOK ROUTE ===
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    
    async def process():
        await application.process_update(update)
    
    asyncio.run(process())
    return 'OK'

# === HEALTH CHECK ===
@app.route('/health')
def health():
    return 'OK'

# === HOME ROUTE ===
@app.route('/')
def home():
    return 'Bot is running!'

# === SET WEBHOOK ===
def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    webhook_url = f"{RENDER_URL}/webhook"
    response = requests.post(url, json={"url": webhook_url})
    print(f"Webhook set: {response.json()}")

# === INITIALISER LE BOT ===
def init_bot():
    async def init():
        await application.initialize()
    asyncio.run(init())

# === MAIN ===
if __name__ == "__main__":
    init_bot()
    set_webhook()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
