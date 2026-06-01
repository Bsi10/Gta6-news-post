import os
import asyncio
import requests
import json
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime, timedelta
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup

# === CONFIG ===
BOT_TOKEN = os.environ.get("BOT_TOKEN")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
RENDER_URL = os.environ.get("RENDER_URL")

# === FLASK ===
app = Flask(__name__)

# === APPLICATION TELEGRAM ===
application = Application.builder().token(BOT_TOKEN).build()

# ===================================
# === FONCTION POUR SCAPER UN URL ===
# ===================================
def scrape_article(url, max_chars=1000):
    """Scrape le contenu d'un article depuis son URL"""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Enlever scripts et styles
        for script in soup(["script", "style", "nav", "header", "footer", "aside"]):
            script.decompose()
        
        # Essayer de trouver le contenu principal
        article_selectors = [
            'article', '.article-content', '.post-content', '.entry-content',
            '.story-body', '.article-body', '[itemprop="articleBody"]',
            '.article__body', '.content-body', '#article-body'
        ]
        
        text = ""
        for selector in article_selectors:
            content = soup.select(selector)
            if content:
                text = ' '.join([p.get_text() for p in content[0].find_all('p')])
                break
        
        # Si rien trouvé, prendre tous les paragraphes
        if not text:
            paragraphs = soup.find_all('p')
            text = ' '.join([p.get_text() for p in paragraphs])
        
        # Nettoyer
        text = ' '.join(text.split())
        
        # Limiter
        if len(text) > max_chars:
            text = text[:max_chars] + "..."
        
        return text if text else None
    
    except Exception as e:
        return None

# ==========================================
# === SOURCE 1: NewsAPI + scraping complet ===
# ==========================================
def fetch_newsapi():
    url = "https://newsapi.org/v2/everything"
    yesterday = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    
    params = {
        "q": "GTA6 OR \"GTA 6\" OR \"Grand Theft Auto 6\"",
        "sortBy": "publishedAt",
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
            title = article.get("title", "Pas de titre")
            link = article.get("url", "")
            source = article.get("source", {}).get("name", "Inconnu")
            description = article.get("description", "")
            content = article.get("content", "")
            
            # Combiner description + contenu disponible
            full_text = f"{description}\n\n{content}" if content else description
            
            # Si pas assez de contenu, scraper l'article
            if len(full_text) < 300 and link:
                scraped = scrape_article(link, 800)
                if scraped:
                    full_text = scraped
            
            # Tronquer pour éviter messages trop longs
            if len(full_text) > 1000:
                full_text = full_text[:1000] + "..."
            
            news_list.append(
                f"📰 *News #{i}* | {source}\n"
                f"*{title}*\n"
                f"_{full_text}_\n"
                f"[Lire l'article complet]({link})"
            )
        
        return "\n\n".join(news_list)
    
    except Exception as e:
        return f"❌ Erreur: {str(e)[:100]}"

# =====================================
# === SOURCE 2: Reddit (texte complet) ===
# =====================================
def fetch_reddit():
    url = "https://www.reddit.com/r/GTA6/hot.json"
    headers = {"User-Agent": "GTA6NewsBot/1.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        data = response.json()
        
        posts = data.get("data", {}).get("children", [])[:5]
        if not posts:
            return None
        
        news_list = []
        for i, post in enumerate(posts[:3], 1):
            post_data = post.get("data", {})
            title = post_data.get("title", "Pas de titre")
            permalink = f"https://reddit.com{post_data.get('permalink', '')}"
            author = post_data.get("author", "Anonyme")
            ups = post_data.get("ups", 0)
            num_comments = post_data.get("num_comments", 0)
            selftext = post_data.get("selftext", "")
            url = post_data.get("url", "")
            
            # Texte complet du post Reddit
            if selftext:
                full_text = selftext[:1200]
            elif url and not url.startswith("https://reddit.com"):
                # C'est un lien externe, scraper le contenu
                full_text = f"🔗 Article externe: {url}\n\n"
                scraped = scrape_article(url, 600)
                if scraped:
                    full_text += scraped
            else:
                full_text = "[Cliquez pour voir le contenu]"
            
            if len(full_text) > 1000:
                full_text = full_text[:1000] + "..."
            
            news_list.append(
                f"🔸 *Post Reddit #{i}*\n"
                f"*{title}*\n"
                f"👍 {ups} | 💬 {num_comments} | 👤 u/{author}\n\n"
                f"{full_text}\n"
                f"[Voir sur Reddit]({permalink})"
            )
        
        return "\n\n".join(news_list)
    
    except Exception as e:
        return f"❌ Erreur: {str(e)[:100]}"

# ========================================
# === SOURCE 3: Gaming sites RSS direct ===
# ========================================
def fetch_gaming_rss():
    """RSS de sites gaming avec scraping du contenu"""
    
    rss_feeds = [
        {
            "name": "IGN",
            "url": "https://feeds.feedburner.com/ign/all",
            "filter": ["gta", "grand theft auto"]
        },
        {
            "name": "Eurogamer",
            "url": "https://www.eurogamer.net/feed",
            "filter": ["gta", "grand theft auto"]
        },
        {
            "name": "Kotaku",
            "url": "https://kotaku.com/rss",
            "filter": ["gta", "grand theft auto"]
        },
        {
            "name": "PC Gamer",
            "url": "https://www.pcgamer.com/rss/",
            "filter": ["gta", "grand theft auto"]
        },
        {
            "name": "GamesRadar",
            "url": "https://www.gamesradar.com/feeds/all/",
            "filter": ["gta", "grand theft auto"]
        }
    ]
    
    all_news = []
    
    for feed in rss_feeds:
        try:
            response = requests.get(feed["url"], headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            root = ET.fromstring(response.text)
            
            items = root.findall(".//item")
            for item in items[:5]:  # Vérifier les 5 derniers de chaque site
                title = item.find("title").text if item.find("title") is not None else ""
                link = item.find("link").text if item.find("link") is not None else ""
                description = item.find("description").text if item.find("description") is not None else ""
                
                # Filtrer par mots-clés GTA
                if any(keyword.lower() in title.lower() or keyword.lower() in description.lower() 
                       for keyword in feed["filter"]):
                    
                    # Nettoyer description HTML
                    soup = BeautifulSoup(description, 'html.parser')
                    clean_desc = soup.get_text()[:500]
                    
                    # Scraper plus de contenu si nécessaire
                    if len(clean_desc) < 200:
                        scraped = scrape_article(link, 600)
                        if scraped:
                            clean_desc = scraped
                    
                    all_news.append({
                        "source": feed["name"],
                        "title": title[:150],
                        "description": clean_desc[:800],
                        "link": link
                    })
                    
                    if len(all_news) >= 5:  # Max 5 news au total
                        break
            
            if len(all_news) >= 5:
                break
                
        except:
            continue
    
    if not all_news:
        return None
    
    # Formater
    news_list = []
    for i, news in enumerate(all_news[:3], 1):
        news_list.append(
            f"🎮 *News Gaming #{i}* | {news['source']}\n"
            f"*{news['title']}*\n"
            f"_{news['description']}_\n"
            f"[Lire l'article complet]({news['link']})"
        )
    
    return "\n\n".join(news_list)

# ========================================
# === SOURCE 4: Google News + scraping  ===
# ========================================
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
        
        items = root.findall(".//item")[:5]
        if not items:
            return None
        
        news_list = []
        for i, item in enumerate(items[:3], 1):
            title = item.find("title").text if item.find("title") is not None else "Pas de titre"
            title = title.split(" - ")[0][:150]
            
            link = item.find("link").text if item.find("link") is not None else ""
            source = item.find("source").text if item.find("source") is not None else "Inconnu"
            
            # Scraper le contenu de l'article
            description = ""
            if link:
                scraped = scrape_article(link, 600)
                if scraped:
                    description = scraped
                else:
                    description = "Cliquez sur le lien pour lire l'article complet."
            
            news_list.append(
                f"🌐 *News #{i}* | {source}\n"
                f"*{title}*\n"
                f"_{description}_\n"
                f"[Lire l'article]({link})"
            )
        
        return "\n\n".join(news_list)
    
    except Exception as e:
        return f"❌ Erreur: {str(e)[:100]}"

# ===================
# === COMMANDES    ===
# ===================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎮 *GTA6 News Bot - Articles Complets*\n\n"
        "📰 /news - Sites d'actualité (NewsAPI)\n"
        "🔸 /reddit - r/GTA6 (posts complets)\n"
        "🎮 /gaming - Sites gaming (IGN, Eurogamer, etc.)\n"
        "🌐 /google - Google News\n"
        "🔄 /all - Toutes les sources\n"
        "❓ /start - Ce message\n\n"
        "💡 Chaque résultat inclut le contenu complet !",
        parse_mode="Markdown"
    )

async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Recherche articles complets sur NewsAPI...")
    await asyncio.sleep(1)
    await msg.edit_text("📡 Téléchargement des articles...")
    
    news = fetch_newsapi()
    
    if news and not news.startswith("❌"):
        await msg.edit_text("✅ Articles trouvés ! Envoi en cours...")
        await update.message.reply_text(news, parse_mode="Markdown", disable_web_page_preview=True)
        await msg.delete()
    else:
        await msg.edit_text(f"❌ {news if news else 'Aucun article trouvé.'}")

async def reddit_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Recherche posts Reddit complets...")
    await asyncio.sleep(1)
    await msg.edit_text("📡 Analyse de r/GTA6...")
    
    news = fetch_reddit()
    
    if news and not news.startswith("❌"):
        await msg.edit_text("✅ Posts trouvés ! Envoi en cours...")
        await update.message.reply_text(news, parse_mode="Markdown", disable_web_page_preview=True)
        await msg.delete()
    else:
        await msg.edit_text(f"❌ {news if news else 'Aucun post trouvé.'}")

async def gaming_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🎮 Recherche sur sites gaming (IGN, Eurogamer, Kotaku, PC Gamer, GamesRadar)...")
    await asyncio.sleep(1)
    await msg.edit_text("📡 Scan des flux RSS gaming...")
    
    news = fetch_gaming_rss()
    
    if news and not news.startswith("❌"):
        await msg.edit_text("✅ Articles gaming trouvés ! Envoi en cours...")
        await update.message.reply_text(news, parse_mode="Markdown", disable_web_page_preview=True)
        await msg.delete()
    else:
        await msg.edit_text("❌ Aucun article gaming trouvé.")

async def google_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔍 Recherche Google News...")
    await asyncio.sleep(1)
    await msg.edit_text("📡 Scan et téléchargement des articles...")
    
    news = fetch_google_news()
    
    if news and not news.startswith("❌"):
        await msg.edit_text("✅ Articles Google trouvés ! Envoi en cours...")
        await update.message.reply_text(news, parse_mode="Markdown", disable_web_page_preview=True)
        await msg.delete()
    else:
        await msg.edit_text("❌ Aucun article trouvé sur Google News.")

async def all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await update.message.reply_text("🔄 Lancement de la recherche complète...")
    
    sources = []
    
    # NewsAPI
    await msg.edit_text("📡 [1/4] NewsAPI...")
    newsapi = fetch_newsapi()
    if newsapi and not newsapi.startswith("❌"):
        sources.append(("📰 NewsAPI", newsapi))
    
    # Reddit
    await msg.edit_text("📡 [2/4] Reddit...")
    reddit = fetch_reddit()
    if reddit and not reddit.startswith("❌"):
        sources.append(("🔸 Reddit r/GTA6", reddit))
    
    # Gaming
    await msg.edit_text("📡 [3/4] Sites gaming...")
    gaming = fetch_gaming_rss()
    if gaming and not gaming.startswith("❌"):
        sources.append(("🎮 Gaming", gaming))
    
    # Google
    await msg.edit_text("📡 [4/4] Google News...")
    google = fetch_google_news()
    if google and not google.startswith("❌"):
        sources.append(("🌐 Google News", google))
    
    if sources:
        await msg.edit_text("✅ Recherche terminée ! Envoi des résultats...")
        for name, data in sources:
            await update.message.reply_text(f"*{name}*\n{data}", parse_mode="Markdown", disable_web_page_preview=True)
            await asyncio.sleep(1)
        await msg.delete()
    else:
        await msg.edit_text("❌ Aucun résultat trouvé sur aucune source.")

# === AJOUTER LES HANDLERS ===
application.add_handler(CommandHandler("start", start_command))
application.add_handler(CommandHandler("news", news_command))
application.add_handler(CommandHandler("reddit", reddit_command))
application.add_handler(CommandHandler("gaming", gaming_command))
application.add_handler(CommandHandler("google", google_command))
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
