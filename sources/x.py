"""
X/Twitter source using search scraping + engagement velocity scoring.

Strategy:
1. Scrape X's explore/trending page for current trends
2. Poll keyword searches for cybersecurity/privacy content
3. Score posts by engagement velocity (engagement / age^1.5)
4. Cluster similar posts via Jaccard similarity
5. Surface the top post per cluster

Uses a single persistent browser session for all requests.
"""
import json
import os
import re
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote
from config import SEEN_FILE
from scrapling.engines._browsers._stealth import StealthySession

# Ensure writable tmp dir for Playwright on read-only filesystems (e.g. Railway)
_tmp = Path("/app/tmp")
if not os.environ.get("TMPDIR") and _tmp.parent.exists():
    _tmp.mkdir(exist_ok=True)
    os.environ["TMPDIR"] = str(_tmp)


# High-signal keyword queries for each vertical
KEYWORD_SETS = {
    "Security": [
        "(cybersecurity OR infosec OR vulnerability OR CVE) (breach OR patch OR exploit OR zero-day) min_faves:50 -is:retweet lang:en",
    ],
    "Privacy": [
        "(privacy OR surveillance OR encryption) (law OR breach OR ruling OR ban) min_faves:50 -is:retweet lang:en",
    ],
    "Threats": [
        "(data breach OR ransomware OR malware) (attack OR leak OR exposed) min_faves:50 -is:retweet lang:en",
    ],
}

# Minimum engagement to filter out noise (low threshold since scraping undercounts)
MIN_ENGAGEMENT = 5

# Spam indicators — posts containing these get filtered out
SPAM_KEYWORDS = [
    "airdrop", "claim now", "fill out this form", "giveaway", "free tokens",
    "whitelist", "presale", "join now", "limited spots", "act fast",
    "dm me", "send me", "drop your wallet", "100x", "1000x",
    "sign up link", "register now", "don't miss out", "last chance",
]


def _load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {}


def _parse_count(text):
    """Parse engagement counts like '1.2K', '45', '3.1M'."""
    if not text:
        return 0
    text = text.strip().upper().replace(",", "")
    try:
        if "K" in text:
            return int(float(text.replace("K", "")) * 1000)
        elif "M" in text:
            return int(float(text.replace("M", "")) * 1000000)
        else:
            return int(re.sub(r'[^\d]', '', text) or 0)
    except (ValueError, TypeError):
        return 0


def _extract_posts_from_page(page):
    """Extract post data from a scrapled X page."""
    posts = []
    tweets = page.css('[data-testid="tweet"]')
    if not tweets:
        tweets = page.css('article')

    for tweet in tweets[:15]:
        # Text
        text_el = tweet.css('[data-testid="tweetText"]')
        text = ""
        if text_el:
            spans = text_el[0].css('span')
            text = " ".join(s.text for s in spans if s.text)
        if not text or len(text) < 20:
            continue

        # Author
        author = "unknown"
        author_els = tweet.css('[data-testid="User-Name"] a')
        if author_els:
            href = author_els[0].attrib.get("href", "")
            if href:
                author = href.strip("/").split("/")[0]

        # URL + timestamp
        time_el = tweet.css('time')
        tweet_url = ""
        published = ""
        if time_el:
            published = time_el[0].attrib.get("datetime", "")
            parent = time_el[0].parent
            if parent is not None and parent.tag == 'a':
                href = parent.attrib.get("href", "")
                if "/status/" in href:
                    tweet_url = f"https://x.com{href}"

        if not tweet_url:
            continue

        # Engagement metrics
        likes = 0
        retweets = 0
        replies = 0
        for testid, metric_name in [("like", "likes"), ("retweet", "retweets"), ("reply", "replies")]:
            els = tweet.css(f'[data-testid="{testid}"]')
            for el in els:
                for s in el.css('span'):
                    if s.text and s.text.strip():
                        val = _parse_count(s.text.strip())
                        if testid == "like":
                            likes = max(likes, val)
                        elif testid == "retweet":
                            retweets = max(retweets, val)
                        elif testid == "reply":
                            replies = max(replies, val)

        # Calculate velocity score
        velocity = 0
        hours_old = 1  # default
        if published:
            try:
                post_time = datetime.fromisoformat(published.replace("Z", "+00:00"))
                age = datetime.now(timezone.utc) - post_time
                hours_old = max(age.total_seconds() / 3600, 0.5)

                # Skip posts older than 30 days (velocity handles recency ranking)
                if hours_old > 720:
                    continue
            except Exception:
                pass

        raw_engagement = likes + (2 * retweets) + (3 * replies)
        velocity = raw_engagement / (hours_old ** 1.5)

        # Filter: minimum engagement
        if raw_engagement < MIN_ENGAGEMENT:
            continue

        # Filter: spam detection
        text_lower = text.lower()
        if any(spam in text_lower for spam in SPAM_KEYWORDS):
            continue

        posts.append({
            "title": f"@{author}: {text[:80]}...",
            "url": tweet_url,
            "source": f"X (@{author})",
            "summary": text,
            "published": published,
            "engagement": raw_engagement,
            "velocity": velocity,
            "hours_old": round(hours_old, 1),
            "author": author,
            "type": "x_post",
            "likes": likes,
            "retweets": retweets,
            "replies": replies,
        })

    return posts


def _get_cookies():
    """Load X session cookies from cookies.json if available."""
    cookie_file = SEEN_FILE.parent / "x_cookies.json"
    if cookie_file.exists():
        try:
            return json.loads(cookie_file.read_text())
        except Exception:
            pass
    return None


def _tokenize(text):
    """Simple tokenization for similarity comparison."""
    return set(re.findall(r'\w+', text.lower()))


def _jaccard(a, b):
    """Jaccard similarity between two token sets."""
    if not a or not b:
        return 0
    return len(a & b) / len(a | b)


def _cluster_posts(posts, threshold=0.4):
    """Cluster similar posts, keep highest-velocity post per cluster."""
    if not posts:
        return []

    # Tokenize all posts
    tokenized = [_tokenize(p["summary"]) for p in posts]

    clusters = []  # list of lists of indices
    assigned = set()

    # Sort by velocity first so cluster representatives are the best ones
    order = sorted(range(len(posts)), key=lambda i: posts[i].get("velocity", 0), reverse=True)

    for i in order:
        if i in assigned:
            continue

        cluster = [i]
        assigned.add(i)

        for j in order:
            if j in assigned:
                continue

            # Check URL-based dedup first
            if posts[i].get("url") == posts[j].get("url"):
                cluster.append(j)
                assigned.add(j)
                continue

            # Jaccard similarity on text
            sim = _jaccard(tokenized[i], tokenized[j])
            if sim >= threshold:
                cluster.append(j)
                assigned.add(j)

        clusters.append(cluster)

    # Return the top post from each cluster (already sorted by velocity)
    return [posts[c[0]] for c in clusters]


# Default accounts — used as fallback when search requires login
ACCOUNTS = {
    "Security": ["briankrebs", "SwiftOnSecurity", "troyhunt"],
    "Privacy": ["EFF", "signalapp", "torproject"],
    "Research": ["ProjectZeroBugs", "MalwareTechBlog", "hasherezade"],
}


def fetch_x_posts(keyword_sets=None, accounts=None):
    """Full pipeline using a single browser session: trending + search + profiles + velocity + clustering."""
    if keyword_sets is None:
        keyword_sets = KEYWORD_SETS
    if accounts is None:
        accounts = ACCOUNTS
    seen = _load_seen()
    all_posts = []
    cookies = _get_cookies()

    # Build session config
    session_kwargs = {"headless": True}
    if cookies:
        session_kwargs["cookies"] = cookies

    print("  [X] Starting browser session...")
    session = StealthySession(**session_kwargs)
    try:
        session.start()

        # Step 1: Trending topics
        print("  [X] Scraping trending topics...")
        try:
            page = session.fetch("https://x.com/explore/tabs/trending", network_idle=True)
            trend_items = page.css('[data-testid="trend"]')
            trends = []
            for item in trend_items[:20]:
                spans = item.css('span')
                trend_text = " ".join(s.text for s in spans if s.text).strip()
                if trend_text and len(trend_text) > 2:
                    trends.append(trend_text)
            print(f"  [X] Found {len(trends)} trending topics")
        except Exception as e:
            print(f"  [X] Failed to scrape trending: {e}")

        # Step 2: Keyword searches
        search_worked = False
        for vertical, queries in keyword_sets.items():
            for query in queries[:1]:
                print(f"  [X] Searching: {query[:40]}...")
                try:
                    encoded = quote(query)
                    page = session.fetch(
                        f"https://x.com/search?q={encoded}&src=typed_query&f=top",
                        network_idle=True,
                    )
                    current_url = ""
                    try:
                        current_url = page.url if hasattr(page, 'url') else ""
                    except Exception:
                        pass

                    if "login" in str(current_url).lower():
                        print(f"      No results (may require login)")
                        continue

                    posts = _extract_posts_from_page(page)
                    if posts:
                        search_worked = True
                        all_posts.extend(posts)
                        print(f"      Found {len(posts)} posts")
                    else:
                        print(f"      No results (may require login)")
                except Exception as e:
                    print(f"  [X] Search failed for '{query[:30]}': {e}")

        # Step 3: If search didn't work, scrape account profiles
        if not search_worked:
            print("  [X] Search requires login, scraping accounts by vertical...")
            for vertical, accts in accounts.items():
                print(f"  [X] --- {vertical} ---")
                for account in accts:
                    print(f"  [X] Scraping @{account}...")
                    try:
                        page = session.fetch(f"https://x.com/{account}", network_idle=True)
                        posts = _extract_posts_from_page(page)
                        all_posts.extend(posts)
                    except Exception as e:
                        print(f"  [X] Failed to scrape @{account}: {e}")

    finally:
        print("  [X] Closing browser session...")
        session.close()

    # Step 4: Deduplicate against seen
    unique = []
    seen_urls = set()
    for p in all_posts:
        if p["url"] not in seen_urls and p["url"] not in seen:
            seen_urls.add(p["url"])
            unique.append(p)

    print(f"  [X] {len(unique)} unique posts before clustering")

    # Step 5: Cluster similar posts
    clustered = _cluster_posts(unique)
    print(f"  [X] {len(clustered)} posts after clustering")

    # Step 6: Sort by velocity score
    clustered.sort(key=lambda p: p.get("velocity", 0), reverse=True)

    # Log top posts
    for p in clustered[:5]:
        print(f"      [{p['velocity']:.0f}v] @{p['author']}: {p['summary'][:60]}...".encode('ascii', 'replace').decode())

    return clustered[:30]
