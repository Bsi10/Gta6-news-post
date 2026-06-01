import os
import requests
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# === CONFIG ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")  # Gratuit sur newsapi.org

# === FLASK pour garder Render éveillé ===
app = Flask(__name__)

@app.route('/health')
def health():
    return 'OK'

# === FONCTION QUI FETCH LES NEWS ===
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
            url = article.get("url", "")
            source = article.get("source", {}).get("name", "Inconnu")
            description = article.get("description", "Pas de description")
            
            news_list.append(
                f"📰 *News #{i}*\n"
                f"*{title}*\n"
                f"_{source}_\n\n"
                f"{description[:200]}...\n"
                f"[Lire l'article]({url})"
            )
        
        return "\n\n".join(news_list)
    
    except Exception as e:
        return f"❌ Erreur: {e}"

# === COMMANDE /news ===
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Recherche des dernières news GTA6...")
    
    news = fetch_gta6_news()
    
    if news:
        await update.message.reply_text(news, parse_mode="Markdown", disable_web_page_preview=True)
    else:
        await update.message.reply_text("❌ Aucune news trouvée ou problème API.")

# === COMMANDE /start ===
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 *GTA6 News Bot*\n\n"
        "Commandes:\n"
        "/news - Dernières news GTA6\n"
        "/start - Ce message",
        parse_mode="Markdown"
    )

# === MAIN ===
def main():
    app_telegram = Application.builder().token(BOT_TOKEN).build()
    
    app_telegram.add_handler(CommandHandler("start", start_command))
    app_telegram.add_handler(CommandHandler("news", news_command))
    
    # Lancer Flask dans un thread
    Thread(target=lambda: app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))).start()
    
    # Lancer le bot
    app_telegram.run_polling()

if __name__ == "__main__":
    main()
