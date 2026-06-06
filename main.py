import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from html import escape

import feedparser
import requests
from bs4 import BeautifulSoup


STATE_FILE = "last_run.json"
TEMPLATE_DIR = "templates"
DOCS_DIR = "docs"
MADRID_TZ = timezone(timedelta(hours=2))

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9",
}

SOURCES = [
    {
        "name": "AS",
        "type": "rss",
        "url": "https://feeds.as.com/mrss-s/list/as/site/as.com/tag/atletico_madrid_a",
    },
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
]

SOURCE_KEY_MAP = {
    "Mundo Deportivo": "mundodeportivo",
    "Marca": "marca",
    "AS": "as",
}


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


def extract_image(entry, source_key):
    if source_key == "mundodeportivo":
        if entry.get("media_content"):
            return entry.media_content[0]["url"]
        if entry.get("enclosures"):
            for enc in entry.enclosures:
                if enc.get("type", "").startswith("image/"):
                    return enc["url"]

    elif source_key == "marca":
        if entry.get("media_content"):
            for mc in entry.media_content:
                if mc.get("url"):
                    return mc["url"]

    elif source_key == "as":
        if entry.get("media_content"):
            for mc in entry.media_content:
                url = mc.get("url", "")
                if url and "img.asmedia.epimg.net" in url:
                    return url
        content = entry.get("content", [{}])[0].get("value", "")
        match = re.search(r'<img\s+src="([^"]+)"', content)
        if match:
            return match.group(1)

    return None


def fetch_rss(source, last_run):
    feed = feedparser.parse(source["url"])
    articles = []
    url_filter = source.get("filter")
    source_key = SOURCE_KEY_MAP.get(source["name"], "")
    for entry in feed.entries:
        link = getattr(entry, "link", "")
        if url_filter and url_filter not in link:
            continue
        pub_date = parse_pub_date(getattr(entry, "published", ""))
        if pub_date and pub_date <= last_run:
            continue
        title = getattr(entry, "title", "Sin título")
        title = BeautifulSoup(title, "html.parser").get_text(strip=True)
        image_url = extract_image(entry, source_key)
        articles.append({
            "title": title,
            "url": link,
            "date": pub_date,
            "image_url": image_url,
        })
    return articles


def fetch_news(source, last_run):
    if source["type"] == "rss":
        return fetch_rss(source, last_run)
    return []


def generate_html(results, date_str):
    os.makedirs(DOCS_DIR, exist_ok=True)

    with open(os.path.join(TEMPLATE_DIR, "page.html")) as f:
        template = f.read()

    sections = []
    for source_name, (articles, error) in results.items():
        escaped_name = escape(source_name)
        if error:
            sections.append(
                f'<div class="source-section">'
                f'<h2 class="source-title">📰 {escaped_name}</h2>'
                f'<div class="error-box">⚠️ No se pudieron obtener noticias: {escape(str(error))}</div>'
                f'</div>'
            )
        elif not articles:
            sections.append(
                f'<div class="source-section">'
                f'<h2 class="source-title">📰 {escaped_name}</h2>'
                f'<p>Sin noticias nuevas</p>'
                f'</div>'
            )
        else:
            cards = []
            for art in articles:
                title = escape(art["title"])
                url = escape(art["url"])
                img_url = art.get("image_url")
                if img_url:
                    img_html = f'<img src="{escape(img_url)}" alt="{title}" loading="lazy">'
                else:
                    img_html = '<div class="no-image">⚽</div>'
                cards.append(
                    f'<div class="news-card">'
                    f'<a href="{url}" target="_blank" rel="noopener">'
                    f'{img_html}'
                    f'<div class="content">'
                    f'<h3>{title}</h3>'
                    f'<span class="source-badge">{escaped_name}</span>'
                    f'</div></a></div>'
                )
            sections.append(
                f'<div class="source-section">'
                f'<h2 class="source-title">📰 {escaped_name}</h2>'
                f'<div class="news-grid">{"".join(cards)}</div>'
                f'</div>'
            )

    content = "\n".join(sections)
    html = template.replace("{date}", date_str).replace("{content}", content)

    filepath = os.path.join(DOCS_DIR, f"{date_str}.html")
    with open(filepath, "w") as f:
        f.write(html)
    print(f"Generated {filepath}")
    return filepath


def generate_index():
    with open(os.path.join(TEMPLATE_DIR, "index.html")) as f:
        template = f.read()

    pages = sorted(glob.glob(os.path.join(DOCS_DIR, "*.html")), reverse=True)
    pages = [p for p in pages if not p.endswith("index.html")]

    if pages:
        items = []
        for page in pages:
            filename = os.path.basename(page)
            page_id = filename.replace(".html", "")
            try:
                dt = datetime.strptime(page_id, "%Y-%m-%d_%H%M")
                label = dt.strftime("%d/%m/%Y %H:%M")
            except ValueError:
                label = page_id
            items.append(
                f'<li><a href="{filename}">📅 {label} <span class="arrow">→</span></a></li>'
            )
        content = f'<ul class="archive-list">{"".join(items)}</ul>'
    else:
        content = '<div class="empty">No hay páginas generadas aún.</div>'

    html = template.replace("{content}", content)

    filepath = os.path.join(DOCS_DIR, "index.html")
    with open(filepath, "w") as f:
        f.write(html)
    print(f"Generated {filepath}")


def format_message(results, has_errors, date_str):
    lines = [f"⚽ Noticias del Atlético - {date_str}", ""]
    for source_name, (articles, error) in results.items():
        if error:
            lines.append(f"📰 {source_name}: ⚠️ Error")
        elif articles:
            lines.append(f"📰 {source_name}: {len(articles)} noticias")
        else:
            lines.append(f"📰 {source_name}: Sin noticias")
    lines.append("")
    lines.append("🔗 Ver noticias: https://jekopena.github.io/atletico-news/")
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

    now = datetime.now(MADRID_TZ)
    today = now.strftime("%Y-%m-%d")
    page_id = now.strftime("%Y-%m-%d_%H%M")
    generate_html(results, page_id)
    generate_index()

    message = format_message(results, has_errors, today)
    send_telegram(message)

    now = datetime.now(MADRID_TZ)
    save_last_run(now)
    print(f"Saved last_run: {now.isoformat()}")


if __name__ == "__main__":
    main()
