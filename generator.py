import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Central Daylight Time (UTC-5) — DST active in March
CDT = timezone(timedelta(hours=-5))
from jinja2 import Environment, FileSystemLoader
from config import DOMAINS, EDITIONS_DIR, DATA_DIR, SEEN_FILE, MAX_STORIES_PER_DOMAIN, BASE_DIR
from sources.rss import fetch_all_feeds
from sources.github import fetch_trending, fetch_notable_repos
from sources.x import fetch_x_posts
from processor import summarize, generate_headline, editorialize, generate_telegram_digest
from telegram_bot import send_edition_to_telegram


def _load_seen():
    if SEEN_FILE.exists():
        return json.loads(SEEN_FILE.read_text())
    return {}


def _save_seen(seen):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(seen, indent=2))


def _process_story(story, domain_context="technology"):
    """Run a story through the LLM for headline + summary."""
    print(f"  Processing: {story['title'][:60]}...".encode('ascii', 'replace').decode())
    headline = generate_headline(story)
    body = summarize(story, domain_context=domain_context)
    return {
        **story,
        "headline": headline,
        "body": body,
    }


def build_edition(send_telegram=True):
    """Run the full pipeline: fetch -> process -> render -> publish. Domains run in series."""
    now = datetime.now(CDT)
    date_str = now.strftime("%Y-%m-%d")
    date_fancy = now.strftime("%A, %B %d, %Y")

    # Calculate edition number (days since project start)
    start = datetime(2026, 3, 16, tzinfo=CDT)
    edition_number = max(1, (now - start).days + 1)

    print(f"\n{'='*60}")
    print(f"  THE CYPHER SENTINEL — Edition #{edition_number}")
    print(f"  {date_fancy}")
    print(f"{'='*60}\n")

    all_domain_data = {}
    all_stories_flat = []

    # Process each domain IN SERIES to avoid memory issues
    for domain_key, domain_cfg in DOMAINS.items():
        domain_name = domain_cfg["name"]
        context = domain_cfg["prompt_context"]

        print(f"\n{'─'*60}")
        print(f"  Domain: {domain_name}")
        print(f"{'─'*60}")

        # --- Fetch RSS ---
        print(f"  [RSS] Fetching feeds...")
        rss_stories = fetch_all_feeds(feeds=domain_cfg["rss_feeds"])
        print(f"  [RSS] Found {len(rss_stories)} stories")

        # --- Fetch X posts ---
        print(f"  [X] Fetching posts...")
        x_stories_raw = fetch_x_posts(
            keyword_sets=domain_cfg["x_keyword_sets"],
            accounts=domain_cfg["x_accounts"],
        )
        print(f"  [X] Found {len(x_stories_raw)} posts")

        # --- Fetch GitHub repos ---
        print(f"  [GH] Fetching repos...")
        gh_trending = fetch_trending(filter_keywords=domain_cfg["github_keywords"])
        gh_notable = fetch_notable_repos(topics=domain_cfg["github_topics"])
        gh_stories_raw = gh_trending + gh_notable
        seen_urls = set()
        gh_deduped = []
        for s in gh_stories_raw:
            if s["url"] not in seen_urls:
                seen_urls.add(s["url"])
                gh_deduped.append(s)
        print(f"  [GH] Found {len(gh_deduped)} repos")

        # --- Cap per domain for variety ---
        MAX_PER_SOURCE = 5
        source_counts = {}
        balanced_news = []
        for s in rss_stories:
            src = s["source"]
            source_counts[src] = source_counts.get(src, 0) + 1
            if source_counts[src] <= MAX_PER_SOURCE:
                balanced_news.append(s)
        news_to_process = balanced_news[:MAX_STORIES_PER_DOMAIN]
        x_to_process = x_stories_raw[:9]
        gh_to_process = gh_deduped[:8]

        total = len(news_to_process) + len(x_to_process) + len(gh_to_process)
        if total == 0:
            print(f"  No stories found for {domain_name}, skipping.")
            all_domain_data[domain_key] = {
                "config": domain_cfg,
                "news": [],
                "x": [],
                "github": [],
            }
            continue

        # --- Process through LLM (serial) ---
        print(f"\n  Processing {total} stories through Qwen 3.5...")

        print(f"\n  --- {domain_name}: News ---")
        news_processed = [_process_story(s, context) for s in news_to_process]

        print(f"\n  --- {domain_name}: X Dispatches ---")
        x_processed = [_process_story(s, context) for s in x_to_process]

        print(f"\n  --- {domain_name}: GitHub ---")
        gh_processed = [_process_story(s, context) for s in gh_to_process]

        all_domain_data[domain_key] = {
            "config": domain_cfg,
            "news": news_processed,
            "x": x_processed,
            "github": gh_processed,
        }
        all_stories_flat.extend(news_processed + x_processed + gh_processed)

    if not all_stories_flat:
        print("\nNo new stories found across any domain. Skipping edition.")
        return None

    # --- Single editorial across all domains ---
    print("\n  Writing editor's column...")
    editorial = editorialize(all_stories_flat)

    # --- Render HTML ---
    print("\n  Rendering newspaper...")
    env = Environment(loader=FileSystemLoader(BASE_DIR / "templates"))
    template = env.get_template("newspaper.html")

    html = template.render(
        date=date_str,
        date_fancy=date_fancy,
        edition_number=edition_number,
        year=now.year,
        editorial=editorial,
        domains=all_domain_data,
    )

    # Write edition files
    EDITIONS_DIR.mkdir(parents=True, exist_ok=True)
    edition_path = EDITIONS_DIR / f"{date_str}.html"
    latest_path = EDITIONS_DIR / "latest.html"

    edition_path.write_text(html, encoding="utf-8")
    latest_path.write_text(html, encoding="utf-8")
    print(f"  Saved: {edition_path}")
    print(f"  Saved: {latest_path}")

    # --- Update edition index for pagination ---
    import re
    edition_dates = sorted(
        re.match(r"(\d{4}-\d{2}-\d{2})\.html", f.name).group(1)
        for f in EDITIONS_DIR.glob("????-??-??.html")
        if re.match(r"\d{4}-\d{2}-\d{2}\.html", f.name)
    )
    index_path = EDITIONS_DIR / "index.json"
    index_path.write_text(json.dumps(edition_dates), encoding="utf-8")
    print(f"  Saved: {index_path} ({len(edition_dates)} editions)")

    # --- Update seen list ---
    seen = _load_seen()
    for s in all_stories_flat:
        seen[s["url"]] = {"title": s["title"], "date": date_str}
    _save_seen(seen)

    # --- Telegram ---
    if send_telegram:
        print("\n  Sending Telegram digest...")
        digest = generate_telegram_digest(all_stories_flat, editorial)
        send_edition_to_telegram(digest, date_fancy)

    print(f"\n{'='*60}")
    print(f"  Edition #{edition_number} complete!")
    print(f"  Open: file://{edition_path}")
    print(f"{'='*60}\n")

    return str(edition_path)
