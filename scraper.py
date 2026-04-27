import feedparser
import html
import re
import requests
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

MAX_ARTICLES = 3
SUMMARY_LENGTH = 160

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ── 工具函式 ───────────────────────────────────────────────────

def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def truncate(text: str, length: int) -> str:
    return text[:length].rsplit(" ", 1)[0] + "…" if len(text) > length else text


def translate(text: str) -> str:
    if not text:
        return text
    try:
        return GoogleTranslator(source="auto", target="zh-TW").translate(text)
    except Exception:
        return text


def parse_rss_date(entry) -> datetime:
    for attr in ("published", "updated"):
        raw = getattr(entry, attr, None)
        if raw:
            try:
                return parsedate_to_datetime(raw)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def make_article(title: str, url: str, summary: str, date: str, config: dict) -> dict:
    return {
        "title": title,
        "url": url or config["site_url"],
        "blog": config["name"],
        "site_url": config["site_url"],
        "accent": config["accent"],
        "category": config["category"],
        "summary": translate(summary) if summary else "",
        "date": date,
    }


# ── RSS 來源 ──────────────────────────────────────────────────

RSS_FEEDS = [
    # 官方更新
    {
        "name": "Ads Developers Blog",
        "url": "http://feeds.feedburner.com/GoogleAdsDeveloperBlog",
        "site_url": "https://ads-developers.googleblog.com",
        "accent": "#4285F4",
        "category": "官方更新",
    },
    {
        "name": "Google Ads & Commerce",
        "url": "https://blog.google/products/ads-commerce/rss/",
        "site_url": "https://blog.google/products/ads-commerce/",
        "accent": "#34A853",
        "category": "官方更新",
    },
    {
        "name": "BigQuery",
        "url": "https://docs.cloud.google.com/feeds/bigquery-release-notes.xml",
        "site_url": "https://cloud.google.com/bigquery/docs/release-notes",
        "accent": "#0F9D58",
        "category": "官方更新",
    },
    {
        "name": "Meta Developers",
        "url": "https://developers.facebook.com/blog/feed/",
        "site_url": "https://developers.facebook.com/blog/",
        "accent": "#1877F2",
        "category": "官方更新",
    },
    # 國外大神
    {
        "name": "Simo Ahava",
        "url": "https://www.simoahava.com/index.xml",
        "site_url": "https://www.simoahava.com",
        "accent": "#8b5cf6",
        "category": "國外大神",
    },
    {
        "name": "MeasureSchool",
        "url": "https://measureschool.com/feed/",
        "site_url": "https://measureschool.com",
        "accent": "#f59e0b",
        "category": "國外大神",
    },
]


def fetch_rss_articles(config: dict) -> list[dict]:
    try:
        feed = feedparser.parse(config["url"])
        articles = []
        for entry in feed.entries[:MAX_ARTICLES]:
            summary_raw = getattr(entry, "summary", "") or getattr(entry, "description", "")
            summary = truncate(strip_html(summary_raw), SUMMARY_LENGTH)
            articles.append(make_article(
                title=strip_html(entry.get("title", "Untitled")),
                url=entry.get("link", ""),
                summary=summary,
                date=parse_rss_date(entry).strftime("%Y-%m-%d"),
                config=config,
            ))
        return articles
    except Exception as e:
        print(f"  Warning: {config['name']} RSS failed — {e}")
        return []


# ── HTML 爬蟲：Google Support 頁面 ────────────────────────────
# 適用：support.google.com 的 release notes 頁面
# 結構：<h3> 或 <h2> 為日期，緊接的 <p>/<ul>/<h4> 為內容

def scrape_google_support(config: dict) -> list[dict]:
    date_re = re.compile(
        r'(January|February|March|April|May|June|July|August|September|October|November|December)'
        r'\s+\d+,\s+\d{4}', re.I
    )
    try:
        soup = get_soup(config["url"])
        articles = []
        for h in soup.find_all(["h2", "h3"]):
            if not date_re.search(h.get_text(strip=True)):
                continue
            date_text = h.get_text(strip=True)
            parts = []
            for sib in h.next_siblings:
                if getattr(sib, "name", None) in ["h2", "h3"]:
                    break
                t = strip_html(str(sib)).strip()
                if t:
                    parts.append(t)
                if len(parts) >= 2:
                    break
            articles.append(make_article(
                title=date_text,
                url=config["url"],
                summary=truncate(" ".join(parts), SUMMARY_LENGTH),
                date=date_text,
                config=config,
            ))
            if len(articles) >= MAX_ARTICLES:
                break
        return articles
    except Exception as e:
        print(f"  Warning: {config['name']} failed — {e}")
        return []


# ── HTML 爬蟲：Firebase Release Notes ────────────────────────
# 結構：<h2> 為日期，下方 <h3> 為功能名稱，<ul>/<p> 為說明

def scrape_firebase(config: dict) -> list[dict]:
    try:
        soup = get_soup(config["url"])
        articles = []
        for h2 in soup.find_all("h2")[:MAX_ARTICLES]:
            date_text = h2.get_text(strip=True)
            parts = []
            for sib in h2.next_siblings:
                if getattr(sib, "name", None) == "h2":
                    break
                t = strip_html(str(sib)).strip()
                if t:
                    parts.append(t)
                if len(parts) >= 3:
                    break
            articles.append(make_article(
                title=date_text,
                url=config["url"],
                summary=truncate(" ".join(parts), SUMMARY_LENGTH),
                date=date_text,
                config=config,
            ))
        return articles
    except Exception as e:
        print(f"  Warning: {config['name']} failed — {e}")
        return []


# ── HTML 爬蟲：LINE Developers News ──────────────────────────
# 結構：<article> > <h2><a> (標題+連結) + <time> (日期) + <a> (標籤)

def scrape_line_news(config: dict) -> list[dict]:
    try:
        soup = get_soup(config["url"])
        articles = []
        for item in soup.find_all("article"):
            h2 = item.find("h2")
            if not h2:
                continue
            a = h2.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            href = a.get("href", "")
            if href.startswith("/"):
                href = "https://developers.line.biz" + href
            time_tag = item.find("time")
            date_text = time_tag.get_text(strip=True) if time_tag else ""
            # 用標籤名作為摘要
            tag_texts = [t.get_text(strip=True) for t in item.find_all("a")[1:4]]
            summary = "、".join(tag_texts) if tag_texts else ""
            articles.append(make_article(
                title=title,
                url=href,
                summary=summary,
                date=date_text,
                config=config,
            ))
            if len(articles) >= MAX_ARTICLES:
                break
        return articles
    except Exception as e:
        print(f"  Warning: {config['name']} failed — {e}")
        return []


# ── HTML 爬蟲：VWO Product Updates ───────────────────────────
# VWO 列表頁為 JS 渲染，改用 post-sitemap.xml 取得 URL + 日期，
# 再逐篇抓 <h1> 和 meta description。

def scrape_vwo(config: dict) -> list[dict]:
    SITEMAP = "https://vwo.com/product-updates/post-sitemap.xml"
    NS = "http://www.sitemaps.org/schemas/sitemap/0.9"
    try:
        resp = requests.get(SITEMAP, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        root = ET.fromstring(resp.text)

        entries = []
        for url_el in root.findall(f"{{{NS}}}url"):
            loc = url_el.findtext(f"{{{NS}}}loc", "")
            lastmod = url_el.findtext(f"{{{NS}}}lastmod", "")
            if loc and lastmod:
                entries.append((lastmod, loc))

        entries.sort(reverse=True)  # 最新在前

        articles = []
        for lastmod, loc in entries[:MAX_ARTICLES]:
            try:
                soup = get_soup(loc)
                h1 = soup.find("h1")
                title = h1.get_text(strip=True) if h1 else loc.rstrip("/").split("/")[-1].replace("-", " ").title()
                meta = soup.find("meta", attrs={"name": "description"})
                if meta and meta.get("content"):
                    summary = truncate(meta["content"].strip(), SUMMARY_LENGTH)
                else:
                    first_p = soup.find("p")
                    summary = truncate(first_p.get_text(strip=True), SUMMARY_LENGTH) if first_p else ""
                articles.append(make_article(
                    title=title,
                    url=loc,
                    summary=summary,
                    date=lastmod[:10],
                    config=config,
                ))
            except Exception as e:
                print(f"    Skipping {loc}: {e}")
        return articles
    except Exception as e:
        print(f"  Warning: {config['name']} failed — {e}")
        return []


# ── HTML 來源清單 ──────────────────────────────────────────────

HTML_SOURCES = [
    {
        "name": "Google Analytics 4",
        "url": "https://support.google.com/analytics/answer/9164320?hl=en",
        "site_url": "https://support.google.com/analytics/",
        "accent": "#E37400",
        "category": "官方更新",
        "scraper": scrape_google_support,
    },
    {
        "name": "GTM Release Notes",
        "url": "https://support.google.com/tagmanager/answer/4620708",
        "site_url": "https://support.google.com/tagmanager/",
        "accent": "#4285F4",
        "category": "官方更新",
        "scraper": scrape_google_support,
    },
    {
        "name": "Google Ads 公告",
        "url": "https://support.google.com/google-ads/announcements/9048695",
        "site_url": "https://support.google.com/google-ads/",
        "accent": "#4285F4",
        "category": "官方更新",
        "scraper": scrape_google_support,
    },
    {
        "name": "Firebase",
        "url": "https://firebase.google.com/support/releases",
        "site_url": "https://firebase.google.com/support/releases",
        "accent": "#FF6F00",
        "category": "官方更新",
        "scraper": scrape_firebase,
    },
    {
        "name": "LINE Developers",
        "url": "https://developers.line.biz/en/news/1/",
        "site_url": "https://developers.line.biz/en/news/",
        "accent": "#06C755",
        "category": "官方更新",
        "scraper": scrape_line_news,
    },
    {
        "name": "VWO Product Updates",
        "url": "https://vwo.com/product-updates/",
        "site_url": "https://vwo.com/product-updates/",
        "accent": "#6941C6",
        "category": "官方更新",
        "scraper": scrape_vwo,
    },
]


# ── HTML 生成 ──────────────────────────────────────────────────

CATEGORY_STYLE = {
    "官方更新": ("bg-blue-50 text-blue-600", "官方更新"),
    "國外大神": ("bg-violet-50 text-violet-600", "國外大神"),
}


def card_html(article: dict) -> str:
    accent = article["accent"]
    cat_class, cat_label = CATEGORY_STYLE.get(article["category"], ("bg-gray-100 text-gray-500", article["category"]))
    return f"""
    <article class="bg-white rounded-2xl shadow-sm border border-gray-100 flex flex-col overflow-hidden hover:shadow-md transition-shadow duration-200">
      <div class="h-1 w-full" style="background-color:{accent}"></div>
      <div class="p-6 flex flex-col flex-1 gap-3">
        <div class="flex items-center justify-between gap-2 flex-wrap">
          <div class="flex items-center gap-2">
            <span class="text-xs font-semibold px-2 py-0.5 rounded-full {cat_class}">{cat_label}</span>
            <a href="{article['site_url']}" target="_blank" rel="noopener"
               class="text-xs font-medium px-2 py-0.5 rounded-full"
               style="color:{accent};background-color:{accent}1a">{article['blog']}</a>
          </div>
          <time class="text-xs text-gray-400 shrink-0">{article['date']}</time>
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
    official = [a for a in all_articles if a["category"] == "官方更新"]
    expert = [a for a in all_articles if a["category"] == "國外大神"]

    def section(title: str, articles: list[dict]) -> str:
        if not articles:
            return ""
        cards = "\n".join(card_html(a) for a in articles)
        return f"""
    <section class="mb-12">
      <h2 class="text-lg font-bold text-gray-700 mb-5 flex items-center gap-2">
        <span class="w-1 h-5 rounded-full inline-block" style="background:#6366f1"></span>
        {title}
      </h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
        {cards}
      </div>
    </section>"""

    return f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>Analytics 情報週報</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <meta name="description" content="Analytics / GTM / GA4 最新消息彙整" />
</head>
<body class="bg-gray-50 min-h-screen font-sans antialiased">

  <header class="bg-white border-b border-gray-100 sticky top-0 z-10">
    <div class="max-w-6xl mx-auto px-4 sm:px-6 py-4 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-bold text-gray-900">Analytics 情報週報</h1>
        <p class="text-xs text-gray-400 mt-0.5">GA4・GTM・BigQuery・Firebase 等最新更新自動彙整</p>
      </div>
      <span class="text-xs text-gray-400 hidden sm:block">更新時間：{updated}</span>
    </div>
  </header>

  <main class="max-w-6xl mx-auto px-4 sm:px-6 py-10">
    {section("官方更新", official)}
    {section("國外大神", expert)}
  </main>

  <footer class="text-center text-xs text-gray-400 py-8 border-t border-gray-100">
    由 GitHub Actions 每日自動更新 ·
    共 {len(all_articles)} 篇文章來自 {len(set(a['blog'] for a in all_articles))} 個來源
  </footer>

</body>
</html>
"""


# ── 主程式 ────────────────────────────────────────────────────

def main():
    all_articles: list[dict] = []

    print("── RSS 來源 ──")
    for config in RSS_FEEDS:
        print(f"  Fetching {config['name']}...")
        articles = fetch_rss_articles(config)
        print(f"    → {len(articles)} 篇")
        all_articles.extend(articles)

    print("── HTML 來源 ──")
    for config in HTML_SOURCES:
        print(f"  Scraping {config['name']}...")
        articles = config["scraper"](config)
        print(f"    → {len(articles)} 篇")
        all_articles.extend(articles)

    html_content = build_html(all_articles)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"\n✓ 產生 index.html：共 {len(all_articles)} 篇文章")


if __name__ == "__main__":
    main()
