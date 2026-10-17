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

# ================= HAFIZA YÖNETİMİ =================
def load_sent_games():
    """Daha önce gönderilmiş içeriklerin anahtarlarını yükler."""
    if os.path.exists(DATABASE_FILE):
        try:
            with open(DATABASE_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            print(f"Hafıza dosyası okunamadı: {e}")
            return set()
    return set()

def save_sent_game(item_key, sent_games_set):
    """Yeni paylaşılan içeriğin anahtarını hafıza dosyasına işler."""
    sent_games_set.add(item_key)
    with open(DATABASE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(sent_games_set), f, ensure_ascii=False, indent=2)

def format_date_tr(utc_date_str):
    """UTC zaman damgasını Türkiye saatine (UTC+3) ve Türkçe formata çevirir."""
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

# ================= PLATFORM TARAYICILARI =================

# 1. EPIC GAMES
def get_epic_free_games():
    url = "https://store-site-backend-static-ipv4.ak.epicgames.com/freeGamesPromotions"
    params = {"locale": "tr-TR", "country": "TR", "allowCountries": "TR"}
    try:
        res = requests.get(url, params=params, timeout=10).json()
        games = res['data']['Catalog']['searchStore']['elements']
    except Exception as e:
        print(f"Epic Games verisi çekilemedi: {e}")
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
                    "end_date": "Sınırlı Süre (Kampanya Bitene Kadar)",
                    "original_price": f"${orig_price:.2f}" if orig_price > 0 else "Belirtilmemiş",
                    "image_url": item.get('header_image') or f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
                    "url": f"https://store.steampowered.com/app/{app_id}/"
                })
    except Exception as e:
        print(f"Steam featured verisi çekilemedi: {e}")

    try:
        search_url = "https://store.steampowered.com/search/results/"
        search_params = {
            "query": "",
            "start": 0,
            "count": 25,
            "maxprice": "free",
            "specials": 1,
            "json": 1,
            "l": "turkish",
            "cc": "tr"
        }
        search_res = requests.get(search_url, params=search_params, timeout=10).json()
        items = search_res.get('items', [])
        
        for it in items:
            app_id = it.get('id')
            url = f"https://store.steampowered.com/app/{app_id}/"
            if not any(g['url'] == url for g in steam_free):
                steam_free.append({
                    "platform": "STEAM",
                    "title": it.get('name'),
                    "genre": "PC Oyunu",
                    "end_date": "Sınırlı Süre (Kampanya Bitene Kadar)",
                    "original_price": "İndirimde",
                    "image_url": it.get('tiny_image', '').replace("capsule_sm_120", "header"),
                    "url": url
                })
    except Exception as e:
        print(f"Steam arama verisi çekilemedi: {e}")

    return steam_free

# 3. AMAZON PRIME GAMING
def get_prime_gaming_free_games():
    prime_games = []
    
    # 1. Hat: Resmi CDN endpoint'i
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
                item_type = item.get("category", "") or item.get("type", "")
                if "game" in item_type.lower() or item.get("isFullGame", False):
                    prime_games.append({
                        "platform": "PRIME GAMING",
                        "title": item.get("title") or item.get("name"),
                        "genre": "Prime Hediyesi (Tam Oyun)",
                        "end_date": format_date_tr(item.get("endTime") or item.get("expiresAt")),
                        "original_price": "Prime İle Ücretsiz",
                        "image_url": item.get("media", {}).get("featuredImage") or item.get("imageUrl", ""),
                        "url": "https://gaming.amazon.com/home"
                    })
    except Exception:
        pass

    # 2. Hat: GamerPower Prime API (Yedek hat)
    if not prime_games:
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

# 4. AMAZON TR OYUNCU EKİPMANLARI AFFILIATE TARAYICISI
def get_amazon_gaming_deals():
    url = "https://www.amazon.com.tr/s?k=oyuncu+kulakl%C4%B1k+mouse&rh=p_n_deal_type%3A26901166031"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8"
    }

    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            return []
    except Exception as e:
        print(f"Amazon fırsatları çekilemedi: {e}")
        return []

    soup = BeautifulSoup(res.text, "html.parser")
    products = []

    cards = soup.select("div[data-asin]")
    for card in cards:
        asin = card.get("data-asin", "").strip()
        if not asin:
            continue

        title_el = card.select_one("h2 span")
        if not title_el:
            continue
        title = title_el.text.strip()

        price_whole = card.select_one(".a-price-whole")
        price_fraction = card.select_one(".a-price-fraction")
        if not price_whole:
            continue
        
        current_price = f"{price_whole.text.strip()},{price_fraction.text.strip() if price_fraction else '00'} TL"
        
        strike_price = card.select_one("span.a-price.a-text-price span.a-offscreen")
        original_price = strike_price.text.strip() if strike_price else "İndirimde"

        img_el = card.select_one("img.s-image")
        image_url = img_el.get("src", "") if img_el else ""

        clean_url = f"https://www.amazon.com.tr/dp/{asin}/?tag={AMAZON_AFFILIATE_TAG}"

        products.append({
            "platform": "AMAZON TR FIRSATI",
            "title": title[:75] + ("..." if len(title) > 75 else ""),
            "original_price": original_price,
            "current_price": current_price,
            "image_url": image_url,
            "url": clean_url
        })

    return products

# ================= TELEGRAM GÖNDERİCİLERİ =================

def build_share_url(title):
    """Telegram'ın yerel paylaşım arayüzünü açan bağlantıyı üretir."""
    channel_clean = (TELEGRAM_CHAT_ID or "").lstrip("@")
    channel_target = f"https://t.me/{channel_clean}" if channel_clean else "https://t.me"
    share_msg = f"🔥 {title} fırsatını gördün mü? Kaçırma derim:"
    return f"https://t.me/share/url?url={quote(channel_target)}&text={quote(share_msg)}"

def send_telegram_alert(game):
    genre_clean = game['genre'].split('/')[0].strip().replace(" ", "").replace("-", "") if game.get('genre') else "Oyun"
    genre_tag = f"#{genre_clean}"
    
    if "EPIC" in game['platform']:
        platform_tag = "#EpicGames"
        btn_text = "🎮 Epic Games'ten Ücretsiz Al"
    elif "STEAM" in game['platform']:
        platform_tag = "#Steam"
        btn_text = "🎮 Steam Kütüphanene Ekle"
    else:
        platform_tag = "#PrimeGaming #AmazonPrime"
        btn_text = "🎁 Prime Gaming'den Talep Et"
    
    caption = (
        f"🎮 *{game['platform']} ÜCRETSİZ OLDU!*\n\n"
        f"📌 *Oyun:* {game['title']}\n"
        f"🏷 *Tür:* {game['genre']}\n"
        f"💰 *Eski Fiyat:* ~{game['original_price']}~\n"
        f"🎁 *Şu Anki Fiyat:* ÜCRETSİZ\n"
        f"⏳ *Son Geçerlilik:* {game['end_date']}\n\n"
        f"{platform_tag} #UcretsizOyun #BedavaOyun #Gamer {genre_tag}"
    )

    share_url = build_share_url(game['title'])

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": btn_text, "url": game['url']}
            ],
            [
                {"text": "👥 Arkadaşınla Paylaş", "url": share_url}
            ]
        ]
    }
    
    endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/" + ("sendPhoto" if game['image_url'] else "sendMessage")
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption" if game['image_url'] else "text": caption,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    }
    if game['image_url']:
        payload["photo"] = game['image_url']
        
    res = requests.post(endpoint, json=payload)
    return res.status_code == 200

def send_deal_alert(deal):
    caption = (
        f"🔥 *GÜNÜN OYUNCU EKİPMANI İNDİRİMİ!*\n\n"
        f"🎧 *Ürün:* {deal['title']}\n"
        f"💰 *Eski Fiyat:* ~{deal['original_price']}~\n"
        f"🏷 *İndirimli Fiyat:* {deal['current_price']}\n\n"
        f"#AmazonFırsatları #OyuncuEkipmanları #İndirim #GamingSetup"
    )

    share_url = build_share_url(deal['title'])

    reply_markup = {
        "inline_keyboard": [
            [
                {"text": "🛒 Amazon'da İncele & Satın Al", "url": deal['url']}
            ],
            [
                {"text": "👥 Arkadaşınla Paylaş", "url": share_url}
            ]
        ]
    }

    endpoint = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/" + ("sendPhoto" if deal['image_url'] else "sendMessage")
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "caption" if deal['image_url'] else "text": caption,
        "parse_mode": "Markdown",
        "reply_markup": reply_markup
    }
    if deal['image_url']:
        payload["photo"] = deal['image_url']

    res = requests.post(endpoint, json=payload)
    return res.status_code == 200

# ================= ANA YÜRÜTME DÖNGÜSÜ =================
if __name__ == "__main__":
    sent_games = load_sent_games()
    print(f"Hafızada kayıtlı içerik sayısı: {len(sent_games)}")

    # 1. Ücretsiz Oyunları Tara ve Gönder
    all_games = get_epic_free_games() + get_steam_free_games() + get_prime_gaming_free_games()
    print(f"Toplam bulunan ücretsiz oyun adedi: {len(all_games)}")
    
    for game in all_games:
        unique_key = game['title'] + "_" + game['url']
        if unique_key not in sent_games:
            if send_telegram_alert(game):
                save_sent_game(unique_key, sent_games)
                print(f"Paylaşıldı: [{game['platform']}] {game['title']}")

    # 2. İndirimli Ekipman Fırsatını Tara ve Gönder (Her çalıştırmada maksimum 1 adet)
    deals = get_amazon_gaming_deals()
    print(f"Toplam bulunan indirimli donanım adedi: {len(deals)}")
    
    for deal in deals:
        deal_key = "DEAL_" + deal['url']
        if deal_key not in sent_games:
            if send_deal_alert(deal):
                save_sent_game(deal_key, sent_games)
                print(f"Paylaşıldı: [{deal['platform']}] {deal['title']}")
                break
