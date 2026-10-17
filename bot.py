import os
import json
import requests

# GitHub Secrets üzerinden okunur
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DATABASE_FILE = "gonderilen_oyunlar.json"

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
                current_price = price_info.get('discountPrice', 1)
                original_price = price_info.get('originalPrice', 0) / 100
                
                if current_price == 0:
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
                        "original_price": f"{original_price:.2f} TL" if original_price > 0 else "Belirtilmemiş",
                        "image_url": image_url,
                        "url": store_url
                    })
    return free_games

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
                    "original_price": f"${orig_price:.2f}" if orig_price > 0 else "Belirtilmemiş",
                    "image_url": item.get('header_image') or f"https://cdn.akamai.steamstatic.com/steam/apps/{app_id}/header.jpg",
                    "url": f"https://store.steampowered.com/app/{app_id}/"
                })
    except Exception:
        pass
    return steam_free

def send_telegram_alert(game):
    caption = (
        f"🎮 *{game['platform']} ÜCRETSİZ OLDU!*\n\n"
        f"📌 *Oyun:* {game['title']}\n"
        f"💰 *Eski Fiyat:* ~{game['original_price']}~\n"
        f"🎁 *Şu Anki Fiyat:* ÜCRETSİZ (0 TL / $0)\n\n"
        f"🔗 [Kütüphanene Ekle]({game['url']})"
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

# Ana akış
sent_games = load_sent_games()
all_games = get_epic_free_games() + get_steam_free_games()

for game in all_games:
    if game['url'] not in sent_games:
        if send_telegram_alert(game):
            save_sent_game(game['url'], sent_games)
