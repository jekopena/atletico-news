import json
import os
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import feedparser
import requests
from bs4 import BeautifulSoup


STATE_FILE = "last_run.json"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

SOURCES = [
    {
        "name": "Mundo Deportivo",
        "type": "rss",
        "url": "https://www.mundodeportivo.com/rss/futbol/atletico-madrid",
    },
    {
        "name": "Marca",
        "type": "rss",
        "url": "https://www.marca.com/rss/portada.xml",
        "filter": "/futbol/atletico/",
    },
    {
        "name": "AS",
        "type": "html",
        "url": "https://as.com/noticias/atletico-madrid/",
    },
]


def load_last_run():
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
            return datetime.fromisoformat(data["last_run"])
    except (FileNotFoundError, KeyError, ValueError):
        return datetime.now(timezone.utc) - timedelta(hours=24)


def save_last_run(dt):
    with open(STATE_FILE, "w") as f:
        json.dump({"last_run": dt.isoformat()}, f, indent=2)


def parse_pub_date(date_str):
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except (TypeError, ValueError):
        pass
    for fmt in ("%d/%m/%Y %H:%M", "%d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(date_str, fmt)
        except (TypeError, ValueError):
            continue
    return None


def fetch_rss(source, last_run):
    feed = feedparser.parse(source["url"])
    articles = []
    url_filter = source.get("filter")
    for entry in feed.entries:
        link = getattr(entry, "link", "")
        if url_filter and url_filter not in link:
            continue
        pub_date = parse_pub_date(getattr(entry, "published", ""))
        if pub_date and pub_date <= last_run:
            continue
        title = getattr(entry, "title", "Sin título")
        title = BeautifulSoup(title, "html.parser").get_text(strip=True)
        articles.append({"title": title, "url": link, "date": pub_date})
    return articles


def fetch_html(source, last_run):
    resp = requests.get(source["url"], headers=BROWSER_HEADERS, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    articles = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if "/futbol/atletico" not in href and "/atletico-madrid" not in href:
            continue
        title = a.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        if not href.startswith("http"):
            href = f"https://as.com{href}"
        articles.append({"title": title, "url": href, "date": None})
    seen = set()
    unique = []
    for art in articles:
        if art["url"] not in seen:
            seen.add(art["url"])
            unique.append(art)
    return unique[:20]


def fetch_news(source, last_run):
    if source["type"] == "rss":
        return fetch_rss(source, last_run)
    elif source["type"] == "html":
        return fetch_html(source, last_run)
    return []


def format_message(results, has_errors):
    today = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    lines = [f"⚽ Noticias del Atlético - {today}", ""]
    any_news = False
    for source_name, (articles, error) in results.items():
        lines.append(f"📰 {source_name}")
        if error:
            lines.append(f"⚠️ No se pudieron obtener noticias: {error}")
        elif not articles:
            lines.append("Sin noticias nuevas")
        else:
            any_news = True
            for art in articles:
                title = art["title"]
                url = art["url"]
                lines.append(f"• {title}")
                lines.append(f"  {url}")
        lines.append("")
    if not any_news and not has_errors:
        return None
    return "\n".join(lines)


def send_telegram(message):
    token = os.environ.get("BOT_TOKEN", "")
    chat_id = os.environ.get("CHAT_ID", "")
    if not token or not chat_id:
        print("ERROR: BOT_TOKEN or CHAT_ID not set", file=sys.stderr)
        sys.exit(1)
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "disable_web_page_preview": True}
    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    print(f"Telegram message sent ({len(message)} chars)")


def main():
    last_run = load_last_run()
    print(f"Last run: {last_run.isoformat()}")

    results = {}
    has_errors = False
    for source in SOURCES:
        name = source["name"]
        try:
            articles = fetch_news(source, last_run)
            results[name] = (articles, None)
            print(f"  {name}: {len(articles)} new articles")
        except Exception as e:
            results[name] = ([], str(e))
            has_errors = True
            print(f"  {name}: ERROR - {e}")

    message = format_message(results, has_errors)
    if message:
        send_telegram(message)
    else:
        print("No new news, skipping Telegram message")

    now = datetime.now(timezone.utc)
    save_last_run(now)
    print(f"Saved last_run: {now.isoformat()}")


if __name__ == "__main__":
    main()
