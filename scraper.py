import feedparser
import html
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

FEEDS = [
    {
        "name": "Tako Analytics",
        "url": "https://tako-analytics.com/rss/",
        "site_url": "https://tako-analytics.com",
        "accent": "#0ea5e9",
    },
    {
        "name": "Simo Ahava",
        "url": "https://www.simoahava.com/index.xml",
        "site_url": "https://www.simoahava.com",
        "accent": "#8b5cf6",
    },
]

MAX_ARTICLES = 5
SUMMARY_LENGTH = 160


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, length: int) -> str:
    return text[:length].rsplit(" ", 1)[0] + "…" if len(text) > length else text


def parse_date(entry) -> datetime:
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def fetch_articles(feed_config: dict) -> list[dict]:
    feed = feedparser.parse(feed_config["url"])
    articles = []
    for entry in feed.entries[:MAX_ARTICLES]:
        summary_raw = getattr(entry, "summary", "") or getattr(entry, "description", "")
        summary = truncate(strip_html(summary_raw), SUMMARY_LENGTH)
        link = entry.get("link", "")
        articles.append(
            {
                "title": strip_html(entry.get("title", "Untitled")),
                "url": link,
                "blog": feed_config["name"],
                "site_url": feed_config["site_url"],
                "accent": feed_config["accent"],
                "summary": summary,
                "date": parse_date(entry).strftime("%Y-%m-%d"),
            }
        )
    return articles


def card_html(article: dict) -> str:
    accent = article["accent"]
    return f"""
    <article class="bg-white rounded-2xl shadow-sm border border-gray-100 flex flex-col overflow-hidden hover:shadow-md transition-shadow duration-200">
      <div class="h-1 w-full" style="background-color:{accent}"></div>
      <div class="p-6 flex flex-col flex-1 gap-3">
        <div class="flex items-center justify-between gap-2">
          <a href="{article['site_url']}" target="_blank" rel="noopener"
             class="text-xs font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full"
             style="color:{accent};background-color:{accent}1a">{article['blog']}</a>
          <time class="text-xs text-gray-400">{article['date']}</time>
        </div>
        <h2 class="text-base font-bold text-gray-900 leading-snug">
          <a href="{article['url']}" target="_blank" rel="noopener"
             class="hover:underline decoration-2 underline-offset-2"
             style="text-decoration-color:{accent}">{article['title']}</a>
        </h2>
        <p class="text-sm text-gray-500 leading-relaxed flex-1">{article['summary']}</p>
        <a href="{article['url']}" target="_blank" rel="noopener"
           class="mt-auto text-sm font-medium inline-flex items-center gap-1 hover:gap-2 transition-all"
           style="color:{accent}">
          閱讀全文
          <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7"/>
          </svg>
        </a>
      </div>
    </article>"""


def build_html(all_articles: list[dict]) -> str:
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    cards = "\n".join(card_html(a) for a in all_articles)
    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Analytics Blog Digest</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <meta name="description" content="最新 Analytics 技術文章精選" />
</head>
<body class="bg-gray-50 min-h-screen font-sans antialiased">
  <header class="bg-white border-b border-gray-100 sticky top-0 z-10 backdrop-blur">
    <div class="max-w-5xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-900">Analytics Blog Digest</h1>
        <p class="text-xs text-gray-400 mt-0.5">Tako Analytics &amp; Simo Ahava 最新文章</p>
      </div>
      <span class="text-xs text-gray-400">更新時間：{updated}</span>
    </div>
  </header>

  <main class="max-w-5xl mx-auto px-4 sm:px-6 py-10">
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
      {cards}
    </div>
  </main>

  <footer class="text-center text-xs text-gray-400 py-8">
    由 GitHub Actions 自動更新 · 資料來源：
    <a href="https://tako-analytics.com" class="underline hover:text-gray-600">Tako Analytics</a> &amp;
    <a href="https://www.simoahava.com" class="underline hover:text-gray-600">Simo Ahava</a>
  </footer>
</body>
</html>
"""


def main():
    all_articles = []
    for feed_config in FEEDS:
        print(f"Fetching {feed_config['name']}...")
        articles = fetch_articles(feed_config)
        print(f"  Got {len(articles)} articles")
        all_articles.extend(articles)

    html_content = build_html(all_articles)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Generated index.html with {len(all_articles)} articles")


if __name__ == "__main__":
    main()
