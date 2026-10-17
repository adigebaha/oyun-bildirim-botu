import os
import json
import requests
from datetime import datetime
import pytz

# GitHub Secrets üzerinden okunur
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DATABASE_FILE = "gonderilen_oyunlar.json"

# --- HAFIZA YÖNETİMİ ---
def load_sent_games():
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()

def save_sent_game(game_url, sent_games_set):
    sent_games_set.add(game_url)
    with open(DATABASE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent_games_set), f, ensure_ascii=False, indent=2)

def format_date_tr(utc_date_str):
    """UTC ISO tarihini Türkiye saatine (UTC+3) ve okunabilir Türkçe formata çevirir."""
    if not utc_date_str:
        return "Süreli / Belirtilmemiş"
    try:
        clean_str = utc_date_str.replace("Z", "+00:00")
        utc_dt = datetime.fromisoformat(clean_str)
        tr_tz = pytz.timezone("Europe/Istanbul")
        tr_dt = utc_dt.astimezone(tr_tz)
        
        aylar = {
            1: "Ocak", 2: "Şubat", 3: "Mart", 4: "Nisan", 
            5: "Mayıs", 6: "Haziran", 7: "Temmuz", 8: "Ağustos", 
            9: "Eylül", 10: "Ekim", 11: "Kasım", 12: "Aralık"
        }
        return f"{tr_dt.day} {aylar[tr_dt.month]} saat {tr_dt.strftime('%H:%M')}"
    except Exception:
        return "Belirtilmemiş"

# --- PLATFORM TARAYICILARI ---

# 1. EPIC GAMES
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
        title = game.get('title')
        promotions = game.get('promotions')
        price_info = game.get('price', {}).get('totalPrice', {})
        
        if promotions and promotions.get('promotionalOffers'):
            offers = promotions['promotionalOffers']
            if offers and len(offers[0]['promotionalOffers']) > 0:
                offer_detail = offers[0]['promotionalOffers'][0]
                current_price = price_info.get('discountPrice', 1)
                original_price = price_info.get('originalPrice', 0) / 100
                
                if current_price == 0:
                    end_date_tr = format_date_tr(offer_detail.get('endDate'))

                    categories = []
                    for cat in game.get('categories', []):
                        path = cat.get('path', '')
                        if 'games' not in path and path:
                            categories.append(path.split('/')[-1].capitalize())
                    genre_str = ", ".join(categories[:3]) if categories else "Aksiyon / Macera"

                    image_url = ""
                    for img in game.get('keyImages', []):
                        if img.get('type') in ['Thumbnail', 'DieselStoreFrontWide', 'OfferImageWide']:
                            image_url = img.get('url')
                            break

                    page_slug = game.get('productSlug') or game.get('urlSlug')
                    store_url = f"https://store.epicgames.com/tr/p/{page_slug}" if page_slug else "https://store.epicgames.com/tr/free-games"

                    free_games.append({
                        "platform": "EPIC GAMES",
                        "title": title,
                        "genre": genre_str,
                        "end_date": end_date_tr,
                        "original_price": f"{original_price:.2f} TL" if original_price > 0 else "Belirtilmemiş",
                        "image_url": image_url,
                        "url": store_url
                    })
    return free_games

# 2. STEAM
def get_steam_free_games():
    steam_free = []
    try:
        url = "https://store.steampowered.com/api/featuredcategories"
        res = requests.get(url, params={"l": "turkish", "cc": "tr"}, timeout=10).json()
        for item in res.get('specials', {}).get('items', []):
            if item.get('discount_percent') == 100 or item.get('final_price') == 0:
                app_id = item.get('id')
                orig_price = item.get('original_price', 0) / 100
                steam_free.append({
                    "platform": "STEAM",
                    "title": item.get('name'),
                    "genre": "PC Oyunu",
                    "end_date": "Sınırlı Süre (Stok/Kampanya Bitene Kadar)",
                    "original_price": f"${orig_price:.2f}" if orig_price > 0 else "Belirtilmemiş",
                    "image_url": item.get('header_image') or f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
                    "url": f"https://store.steampowered.com/app/{app_id}/"
                })
    except Exception:
        pass
    return steam_free

# 3. AMAZON PRIME GAMING
def get_prime_gaming_free_games():
    """Prime Gaming açık katalog beslemesini tarayarak ücretsiz 'Free with Prime' oyunlarını çeker."""
    prime_games = []
    # Prime Gaming web istemcisinin katalog verisini sunduğu açık CDN endpoint'i
    url = "https://gaming.amazon.com/api/offers"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8"
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            data = res.json()
            offers = data.get("offers", []) or data.get("items", [])
            for item in offers:
                # Sadece oyun içi eşya (DLC) değil, tam oyun (FGWP - Free Games with Prime) olanlar
                item_type = item.get("category", "") or item.get("type", "")
                is_game = "game" in item_type.lower() or item.get("isFullGame", False)
                
                if is_game:
                    title = item.get("title") or item.get("name")
                    end_raw = item.get("endTime") or item.get("expiresAt")
                    
                    prime_games.append({
                        "platform": "PRIME GAMING",
                        "title": title,
                        "genre": "Prime Hediyesi (Tam Oyun)",
                        "end_date": format_date_tr(end_raw),
                        "original_price": "Prime İle Ücretsiz",
                        "image_url": item.get("media", {}).get("featuredImage") or item.get("imageUrl", ""),
                        "url": f"https://gaming.amazon.com/home"
                    })
    except Exception:
        # Alternatif: GamerPower Prime API beslemesi üzerinden doğrudan çekme
        try:
            alt_url = "https://www.gamerpower.com/api/giveaways?platform=amazon"
            alt_res = requests.get(alt_url, timeout=10).json()
            for g in alt_res:
                if g.get("status") == "Active":
                    prime_games.append({
                        "platform": "PRIME GAMING",
                        "title": g.get("title"),
                        "genre": "Tam Oyun (Prime)",
                        "end_date": g.get("end_date", "Bu Ayın Sonuna Kadar"),
                        "original_price": g.get("worth", "Prime Dahil"),
                        "image_url": g.get("image", ""),
                        "url": g.get("open_giveaway_url") or "https://gaming.amazon.com/home"
                    })
        except Exception:
            pass

    return prime_games

# --- TELEGRAM GÖNDERİCİ ---
def send_telegram_alert(game):
    genre_clean = game['genre'].split('/')[0].strip().replace(" ", "").replace("-", "") if game.get('genre') else "Oyun"
    genre_tag = f"#{genre_clean}"
    
    if "EPIC" in game['platform']:
        platform_tag = "#EpicGames"
    elif "STEAM" in game['platform']:
        platform_tag = "#Steam"
    else:
        platform_tag = "#PrimeGaming #AmazonPrime"
    
    caption = (
        f"🎮 *{game['platform']} ÜCRETSİZ OLDU!*\n\n"
        f"📌 *Oyun:* {game['title']}\n"
        f"🏷 *Tür:* {game['genre']}\n"
        f"💰 *Eski Fiyat:* ~{game['original_price']}~\n"
        f"🎁 *Şu Anki Fiyat:* ÜCRETSİZ\n"
        f"⏳ *Son Geçerlilik:* {game['end_date']}\n\n"
        f"🔗 [Kütüphanene Ekle / Talep Et]({game['url']})\n\n"
        f"{platform_tag} #UcretsizOyun #BedavaOyun #Gamer {genre_tag}"
    )
    
    endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/" + ("sendPhoto" if game['image_url'] else "sendMessage")
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption" if game['image_url'] else "text": caption,
        "parse_mode": "Markdown"
    }
    if game['image_url']:
        payload["photo"] = game['image_url']
        
    res = requests.post(endpoint, json=payload)
    return res.status_code == 200

# --- ANA DÖNGÜ ---
sent_games = load_sent_games()
all_games = get_epic_free_games() + get_steam_free_games() + get_prime_gaming_free_games()

for game in all_games:
    # URL veya oyun başlığı kontrolü (Prime linkleri genel olduğu için başlıkla birleştirilir)
    unique_key = game['title'] + "_" + game['url']
    if unique_key not in sent_games:
        if send_telegram_alert(game):
            save_sent_game(unique_key, sent_games)
            print(f"Paylaşıldı: [{game['platform']}] {game['title']}")
