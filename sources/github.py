import requests
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from config import GITHUB_TOPICS, SEEN_FILE
import json

MIN_STARS = 100


def _load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {}


def fetch_trending(filter_keywords=None):
    """Scrape GitHub trending page, filtered by keywords."""
    seen = _load_seen()
    stories = []

    try:
        resp = requests.get(
            "https://github.com/trending",
            timeout=15,
            headers={"User-Agent": "TheCypherSentinel/1.0"},
        )
        soup = BeautifulSoup(resp.text, "html.parser")

        for article in soup.select("article.Box-row"):
            h2 = article.select_one("h2 a")
            if not h2:
                continue

            repo_path = h2.get("href", "").strip("/")
            url = f"https://github.com/{repo_path}"

            if url in seen:
                continue

            desc_p = article.select_one("p")
            description = desc_p.get_text(strip=True) if desc_p else ""

            # Check if relevant to domain keywords
            if filter_keywords:
                text_lower = (repo_path + " " + description).lower()
                if not any(kw in text_lower for kw in filter_keywords):
                    continue

            stars_el = article.select_one("[href$='/stargazers']")
            stars_text = stars_el.get_text(strip=True).replace(",", "") if stars_el else "0"
            stars = int(stars_text) if stars_text.isdigit() else 0

            if stars < MIN_STARS:
                continue

            lang_el = article.select_one("[itemprop='programmingLanguage']")
            language = lang_el.get_text(strip=True) if lang_el else ""

            stories.append({
                "title": repo_path,
                "url": url,
                "source": "GitHub Trending",
                "summary": description,
                "stars": str(stars),
                "language": language,
                "type": "github",
            })
    except Exception as e:
        print(f"[GitHub] Failed to fetch trending: {e}")

    return stories


def fetch_notable_repos(topics=None):
    """Find popular repos via GitHub search API."""
    if topics is None:
        topics = GITHUB_TOPICS
    seen = _load_seen()
    stories = []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=14)).strftime("%Y-%m-%d")

    for topic in topics:
        try:
            resp = requests.get(
                "https://api.github.com/search/repositories",
                params={
                    "q": f"{topic} stars:>={MIN_STARS} pushed:>{cutoff}",
                    "sort": "stars",
                    "order": "desc",
                    "per_page": 30,
                },
                timeout=15,
                headers={"User-Agent": "TheCypherSentinel/1.0"},
            )
            data = resp.json()

            for repo in data.get("items", []):
                url = repo["html_url"]
                if url in seen:
                    continue
                if repo["stargazers_count"] < MIN_STARS:
                    continue

                stories.append({
                    "title": repo["full_name"],
                    "url": url,
                    "source": "GitHub Notable",
                    "summary": repo.get("description", "") or "",
                    "stars": str(repo["stargazers_count"]),
                    "language": repo.get("language", "") or "",
                    "type": "github",
                })
        except Exception as e:
            print(f"[GitHub] Failed search for '{topic}': {e}")

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for s in stories:
        if s["url"] not in seen_urls:
            seen_urls.add(s["url"])
            unique.append(s)

    unique.sort(key=lambda s: int(s.get("stars", "0")), reverse=True)
    return unique[:30]
