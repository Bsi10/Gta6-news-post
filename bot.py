import os
import asyncio
import requests
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# === CONFIG ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
RENDER_URL = os.environ.get("RENDER_URL")

# === FLASK ===
app = Flask(__name__)

# === APPLICATION TELEGRAM ===
application = Application.builder().token(BOT_TOKEN).build()

# === FONCTION NEWS ===
def fetch_gta6_news():
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "GTA6 OR \"GTA 6\" OR \"Grand Theft Auto 6\"",
        "sortBy": "popularity",
        "language": "en",
        "pageSize": 3,
        "apiKey": NEWS_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        data = response.json()
        
        if data.get("status") != "ok":
            return None
        
        articles = data.get("articles", [])
        if not articles:
            return None
        
        news_list = []
        for i, article in enumerate(articles[:3], 1):
            title = article.get("title", "Pas de titre")
            link = article.get("url", "")
            source = article.get("source", {}).get("name", "Inconnu")
            
            news_list.append(
                f"📰 *News #{i}*\n"
                f"*{title}*\n"
                f"_{source}_\n"
                f"[Lire l'article]({link})"
            )
        
        return "\n\n".join(news_list)
    
    except Exception as e:
        return f"❌ Erreur: {e}"

# === COMMANDES ===
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Recherche des dernières news GTA6...")
    news = fetch_gta6_news()
    
    if news:
        await update.message.reply_text(news, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text("❌ Aucune news trouvée. Réessaie plus tard.")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 *GTA6 News Bot*\n\n"
        "/news - Dernières news GTA6\n"
        "/start - Ce message",
        parse_mode="Markdown"
    )

# === AJOUTER LES HANDLERS ===
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("news", news_command))

# === WEBHOOK ROUTE (SYNCHRONE) ===
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    
    # Exécuter la mise à jour async de façon synchrone
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
