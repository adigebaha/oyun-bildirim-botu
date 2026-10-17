import os
import json
import requests
from datetime import datetime
import pytz
from bs4 import BeautifulSoup
from urllib.parse import quote

# ================= AYARLAR & ORTAM DEĞİŞKENLERİ =================
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
AMAZON_AFFILIATE_TAG = os.environ.get("AMAZON_AFFILIATE_TAG", "oyunfirsat-21")
DATABASE_FILE = "gonderilen_oyunlar.json"

# Telegram kanalının tıklanabilir davet linki
TELEGRAM_CHANNEL_LINK = f"https://t.me/{TELEGRAM_CHAT_ID.replace('@', '')}" if TELEGRAM_CHAT_ID else ""

# ================= HAFIZA YÖNETİMİ =================
def load_sent_games():
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_sent_game(item_key, sent_games_set):
    sent_games_set.add(item_key)
    with open(DATABASE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent_games_set), f, ensure_ascii=False, indent=2)

def format_date_tr(utc_date_str):
    if not utc_date_str:
        return "Süreli / Belirtilmemiş"
    try:
        clean_str = utc_date_str.replace("Z", "+00:00")
        utc_dt = datetime.fromisoformat(clean_str)
        tr_tz = pytz.timezone("Europe/Istanbul")
        tr_dt = utc_dt.astimezone(tr_tz)
        aylar = {1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos", 9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"}
        return f"{tr_dt.day} {aylar[tr_dt.month]} saat {tr_dt.strftime('%H:%M')}"
    except Exception:
        return "Belirtilmemiş"

# ================= PLATFORM TARAYICILARI =================
def get_epic_free_games():
    url = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
    params = {"locale": "tr-TR", "country": "TR", "allowCountries": "TR"}
    try:
        res = requests.get(url, params=params, timeout=10).json()
        games = res['data']['Catalog']['searchStore']['elements']
    except Exception:
        return []

    free_games = []
    for game in games:
        promotions = game.get('promotions')
        if promotions and promotions.get('promotionalOffers'):
            offers = promotions['promotionalOffers']
            if offers and len(offers[0]['promotionalOffers']) > 0:
                price_info = game.get('price', {}).get('totalPrice', {})
                if price_info.get('discountPrice', 1) == 0:
                    title = game.get('title')
                    end_date_tr = format_date_tr(offers[0]['promotionalOffers'][0].get('endDate'))
                    original_price = price_info.get('originalPrice', 0) / 100
                    
                    categories = [cat.get('path', '').split('/')[-1].capitalize() for cat in game.get('categories', []) if 'games' not in cat.get('path', '') and cat.get('path', '')]
                    genre_str = ", ".join(categories[:3]) if categories else "Aksiyon / Macera"
                    
                    image_url = next((img.get('url') for img in game.get('keyImages', []) if img.get('type') in ['Thumbnail', 'DieselStoreFrontWide', 'OfferImageWide']), "")
                    page_slug = game.get('productSlug') or game.get('urlSlug')
                    store_url = f"https://store.epicgames.com/tr/p/{page_slug}" if page_slug else "https://store.epicgames.com/tr/free-games"

                    free_games.append({"platform": "EPIC GAMES", "title": title, "genre": genre_str, "end_date": end_date_tr, "original_price": f"{original_price:.2f} TL" if original_price > 0 else "Belirtilmemiş", "image_url": image_url, "url": store_url})
    return free_games

def get_steam_free_games():
    steam_free = []
    try:
        res = requests.get("https://store.steampowered.com/api/featuredcategories", params={"l": "turkish", "cc": "tr"}, timeout=10).json()
        for item in res.get('specials', {}).get('items', []):
            if item.get('discount_percent') == 100 or item.get('final_price') == 0:
                app_id = item.get('id')
                orig_price = item.get('original_price', 0) / 100
                steam_free.append({"platform": "STEAM", "title": item.get('name'), "genre": "PC Oyunu", "end_date": "Sınırlı Süre", "original_price": f"${orig_price:.2f}" if orig_price > 0 else "Belirtilmemiş", "image_url": item.get('header_image') or f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg", "url": f"https://store.steampowered.com/app/{app_id}/"})
    except Exception:
        pass
    return steam_free

def get_prime_gaming_free_games():
    prime_games = []
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "tr-TR,tr;q=0.9"}
    try:
        res = requests.get("https://gaming.amazon.com/api/offers", headers=headers, timeout=10)
        if res.status_code == 200:
            for item in res.json().get("offers", []) or res.json().get("items", []):
                item_type = item.get("category", "") or item.get("type", "")
                if "game" in item_type.lower() or item.get("isFullGame", False):
                    prime_games.append({"platform": "PRIME GAMING", "title": item.get("title") or item.get("name"), "genre": "Prime Hediyesi", "end_date": format_date_tr(item.get("endTime") or item.get("expiresAt")), "original_price": "Prime İle Ücretsiz", "image_url": item.get("media", {}).get("featuredImage") or item.get("imageUrl", ""), "url": "https://gaming.amazon.com/home"})
    except Exception:
        pass
    return prime_games

def get_amazon_gaming_deals():
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "tr-TR"}
    try:
        res = requests.get("https://www.amazon.com.tr/s?k=oyuncu+kulakl%C4%B1k+mouse&rh=p_n_deal_type%3A26901166031", headers=headers, timeout=15)
        soup = BeautifulSoup(res.text, "html.parser")
        products = []
        for card in soup.select("div[data-asin]"):
            asin = card.get("data-asin", "").strip()
            title_el = card.select_one("h2 span")
            price_whole = card.select_one(".a-price-whole")
            if asin and title_el and price_whole:
                price_fraction = card.select_one(".a-price-fraction")
                strike_price = card.select_one("span.a-price.a-text-price span.a-offscreen")
                img_el = card.select_one("img.s-image")
                products.append({"platform": "AMAZON FIRSATI", "title": title_el.text.strip()[:75] + "...", "original_price": strike_price.text.strip() if strike_price else "İndirimde", "current_price": f"{price_whole.text.strip()},{price_fraction.text.strip() if price_fraction else '00'} TL", "image_url": img_el.get("src", "") if img_el else "", "url": f"https://www.amazon.com.tr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"})
        return products
    except Exception:
        return []

# ================= TELEGRAM GÖNDERİCİLERİ =================
def build_share_url(title):
    return f"https://t.me/share/url?url={quote(TELEGRAM_CHANNEL_LINK)}&text={quote(f'🔥 {title} bedava oldu! Telegram kanalında yakaladım:')}"

def send_telegram_alert(game):
    platform_tag = "#EpicGames" if "EPIC" in game['platform'] else "#Steam" if "STEAM" in game['platform'] else "#PrimeGaming"
    btn_text = "🎮 Epic'ten Al" if "EPIC" in game['platform'] else "🎮 Steam'e Ekle" if "STEAM" in game['platform'] else "🎁 Prime'dan Talep Et"
    
    caption = f"🎮 *{game['platform']} ÜCRETSİZ OLDU!*\n\n📌 *Oyun:* {game['title']}\n🏷 *Tür:* {game['genre']}\n💰 *Eski Fiyat:* ~{game['original_price']}~\n🎁 *Şu Anki Fiyat:* ÜCRETSİZ\n⏳ *Son Geçerlilik:* {game['end_date']}\n\n{platform_tag} #UcretsizOyun"
    reply_markup = {"inline_keyboard": [[{"text": btn_text, "url": game['url']}], [{"text": "👥 Arkadaşınla Paylaş", "url": build_share_url(game['title'])}]]}
    
    endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/" + ("sendPhoto" if game['image_url'] else "sendMessage")
    payload = {"chat_id": TELEGRAM_CHAT_ID, "caption" if game['image_url'] else "text": caption, "parse_mode": "Markdown", "reply_markup": reply_markup}
    if game['image_url']: payload["photo"] = game['image_url']
    
    return requests.post(endpoint, json=payload).status_code == 200

def send_deal_alert(deal):
    caption = f"🔥 *GÜNÜN OYUNCU EKİPMANI İNDİRİMİ!*\n\n🎧 *Ürün:* {deal['title']}\n💰 *Eski Fiyat:* ~{deal['original_price']}~\n🏷 *İndirimli Fiyat:* {deal['current_price']}\n\n#AmazonFırsatları"
    reply_markup = {"inline_keyboard": [[{"text": "🛒 Amazon'da Satın Al", "url": deal['url']}], [{"text": "👥 Arkadaşınla Paylaş", "url": build_share_url(deal['title'])}]]}
    
    endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/" + ("sendPhoto" if deal['image_url'] else "sendMessage")
    payload = {"chat_id": TELEGRAM_CHAT_ID, "caption" if deal['image_url'] else "text": caption, "parse_mode": "Markdown", "reply_markup": reply_markup}
    if deal['image_url']: payload["photo"] = deal['image_url']
    
    return requests.post(endpoint, json=payload).status_code == 200

# ================= ANA YÜRÜTME =================
if __name__ == "__main__":
    sent_games = load_sent_games()

    all_games = get_epic_free_games() + get_steam_free_games() + get_prime_gaming_free_games()
    for game in all_games:
        unique_key = game['title'] + "_" + game['url']
        if unique_key not in sent_games:
            if send_telegram_alert(game):
                save_sent_game(unique_key, sent_games)
                print(f"Telegram: [{game['platform']}] {game['title']}")

    deals = get_amazon_gaming_deals()
    for deal in deals:
        deal_key = "DEAL_" + deal['url']
        if deal_key not in sent_games:
            if send_deal_alert(deal):
                save_sent_game(deal_key, sent_games)
                print(f"Telegram Fırsat: {deal['title']}")
                break
