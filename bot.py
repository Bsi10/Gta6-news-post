import os
import asyncio
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

# ====================
# === CONFIGURATION ===
# ====================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
RENDER_URL = os.environ.get("RENDER_URL")

# ====================
# === FLASK SETUP ===
# ====================
app = Flask(__name__)

# ====================
# === TELEGRAM SETUP ===
# ====================
application = Application.builder().token(BOT_TOKEN).build()

# ==========================================
# === SOURCE 1: NewsAPI (actualités web) ===
# ==========================================
def fetch_newsapi():
    url = "https://newsapi.org/v2/everything"
    
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    
    params = {
        "q": "GTA6 OR \"GTA 6\" OR \"Grand Theft Auto 6\"",
        "sortBy": "popularity",
        "language": "en",
        "pageSize": 1,
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
        
        article = articles[0]
        title = article.get("title", "Breaking News")
        description = article.get("description", "")
        content = article.get("content", "")
        link = article.get("url", "")
        source = article.get("source", {}).get("name", "Source inconnue")
        
        full_text = description if description else ""
        if content:
            full_text += "\n\n" + content.split("[+")[0]
        
        post = (
            f"🚗💨 *{title}*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{full_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Source :* {source}\n"
            f"🔗 *Lire l'article complet :*\n{link}\n\n"
            f"#GTA6 #GrandTheftAuto6 #Gaming #News #RockstarGames"
        )
        
        return post
    
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
        
        posts = data.get("data", {}).get("children", [])
        if not posts:
            return None
        
        best_post = None
        for post in posts:
            post_data = post.get("data", {})
            text = post_data.get("selftext", "")
            if text and len(text) > 100:
                best_post = post_data
                break
        
        if not best_post:
            best_post = posts[0].get("data", {})
        
        title = best_post.get("title", "Discussion GTA6")
        text = best_post.get("selftext", "")
        url = f"https://reddit.com{best_post.get('permalink', '')}"
        author = best_post.get("author", "Anonyme")
        ups = best_post.get("ups", 0)
        num_comments = best_post.get("num_comments", 0)
        
        if not text or len(text) < 50:
            text = f"Discussion populaire sur le subreddit GTA6. {title}"
        
        if len(text) > 1000:
            text = text[:1000] + "..."
        
        post = (
            f"🎮🔥 *{title}*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{text}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👍 {ups} upvotes | 💬 {num_comments} commentaires\n"
            f"👤 u/{author} | r/GTA6\n"
            f"🔗 *Voir la discussion :*\n{url}\n\n"
            f"#GTA6 #Reddit #Gaming #GTA6Community #Rockstar"
        )
        
        return post
    
    except Exception as e:
        return f"❌ Erreur Reddit: {str(e)[:100]}"

# ============================================
# === SOURCE 3: Google News RSS            ===
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
        root = ET.fromstring(response.text)
        
        items = root.findall(".//item")
        if not items:
            return None
        
        item = items[0]
        
        title = item.find("title").text if item.find("title") is not None else "Sans titre"
        title = " - ".join(title.split(" - ")[:-1]) if " - " in title else title
        
        link = item.find("link").text if item.find("link") is not None else ""
        source = item.find("source").text if item.find("source") is not None else "Google News"
        
        description = item.find("description")
        desc_text = description.text if description is not None else ""
        
        pub_date = item.find("pubDate")
        date_str = pub_date.text if pub_date is not None else ""
        
        post = (
            f"🌐📰 *{title[:150]}*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"{desc_text}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📌 *Source :* {source}\n"
            f"📅 {date_str}\n"
            f"🔗 *Lire l'article :*\n{link}\n\n"
            f"#GTA6 #GrandTheftAuto6 #GamingNews #GTA6News #Rockstar"
        )
        
        return post
    
    except Exception as e:
        return f"❌ Erreur Google News: {str(e)[:100]}"

# ====================
# === COMMANDES ===
# ====================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 *GTA6 News Bot*\n\n"
        "📋 *Commandes disponibles :*\n\n"
        "📰 /news - Article prêt à publier (NewsAPI)\n"
        "🔥 /reddit - Post Reddit prêt à publier (r/GTA6)\n"
        "🌐 /googlenews - Article Google News prêt à publier\n"
        "🔄 /all - Les 3 sources en une fois\n"
        "❓ /start - Ce message d'aide\n\n"
        "✅ Chaque commande te donne un post formaté avec emojis, hashtags et lien source.\n"
        "📋 *Copie-colle directement sur Facebook !*",
        parse_mode="Markdown"
    )

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Recherche sur les sites d'actualité...")
    await asyncio.sleep(0.5)
    await msg.edit_text("📡 Récupération de l'article...")
    
    post = fetch_newsapi()
    
    if post and not post.startswith("❌"):
        await msg.edit_text("✅ Article trouvé ! Envoi en cours...")
        await asyncio.sleep(0.3)
        await update.message.reply_text(
            "📋 *POST PRÊT À PUBLIER*\n\n" + post,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        await msg.delete()
    else:
        await msg.edit_text("❌ Aucun article trouvé. Réessaie plus tard.")

async def reddit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Recherche sur Reddit r/GTA6...")
    await asyncio.sleep(0.5)
    await msg.edit_text("📡 Récupération du post le plus populaire...")
    
    post = fetch_reddit()
    
    if post and not post.startswith("❌"):
        await msg.edit_text("✅ Post trouvé ! Envoi en cours...")
        await asyncio.sleep(0.3)
        await update.message.reply_text(
            "📋 *POST PRÊT À PUBLIER*\n\n" + post,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        await msg.delete()
    else:
        await msg.edit_text("❌ Aucun post trouvé. Réessaie plus tard.")

async def googlenews_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Recherche sur Google News...")
    await asyncio.sleep(0.5)
    await msg.edit_text("📡 Récupération de l'article le plus récent...")
    
    post = fetch_google_news()
    
    if post and not post.startswith("❌"):
        await msg.edit_text("✅ Article trouvé ! Envoi en cours...")
        await asyncio.sleep(0.3)
        await update.message.reply_text(
            "📋 *POST PRÊT À PUBLIER*\n\n" + post,
            parse_mode="Markdown",
            disable_web_page_preview=True
        )
        await msg.delete()
    else:
        await msg.edit_text("❌ Aucun article trouvé. Réessaie plus tard.")

async def all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔄 Recherche sur TOUTES les sources...")
    await asyncio.sleep(0.5)
    await msg.edit_text("📡 Récupération des articles...")
    
    sources = [
        ("📰 NewsAPI", fetch_newsapi()),
        ("🔥 Reddit", fetch_reddit()),
        ("🌐 Google News", fetch_google_news())
    ]
    
    await msg.edit_text("📋 Préparation des posts...")
    
    found_any = False
    for name, post in sources:
        if post and not post.startswith("❌"):
            found_any = True
            await update.message.reply_text(
                f"*{name}*\n\n{post}",
                parse_mode="Markdown",
                disable_web_page_preview=True
            )
            await asyncio.sleep(1)
    
    if found_any:
        await msg.delete()
    else:
        await msg.edit_text("❌ Aucune news trouvée sur aucune source. Réessaie plus tard.")

# ====================
# === HANDLERS ===
# ====================
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("news", news_command))
application.add_handler(CommandHandler("reddit", reddit_command))
application.add_handler(CommandHandler("googlenews", googlenews_command))
application.add_handler(CommandHandler("all", all_command))

# ====================
# === ROUTES FLASK ===
# ====================

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json(force=True)
    update = Update.de_json(data, application.bot)
    
    async def process():
        await application.process_update(update)
    
    asyncio.run(process())
    return 'OK'

@app.route('/health')
def health():
    return 'OK'

@app.route('/')
def home():
    return '✅ GTA6 News Bot is running!'

# ====================
# === INIT ===
# ====================

def set_webhook():
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook"
    webhook_url = f"{RENDER_URL}/webhook"
    response = requests.post(url, json={"url": webhook_url})
    print(f"Webhook: {response.json()}")

def init_bot():
    async def init():
        await application.initialize()
    asyncio.run(init())

# ====================
# === MAIN ===
# ====================

if __name__ == "__main__":
    init_bot()
    set_webhook()
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
