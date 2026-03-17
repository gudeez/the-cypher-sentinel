import requests
import time
from config import OLLAMA_URL, OLLAMA_MODEL


def _generate(prompt, max_tokens=300):
    """Call Ollama generate endpoint."""
    for attempt in range(3):
        try:
            resp = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "think": False,
                    "options": {
                        "num_ctx": 4096,
                        "num_predict": max_tokens,
                        "temperature": 0.7,
                    },
                },
                timeout=120,
            )
            data = resp.json()
            return data.get("response", "").strip()
        except Exception as e:
            print(f"[Ollama] Attempt {attempt + 1} failed: {e}")
            if attempt < 2:
                time.sleep(3)
    return ""


def summarize(story, domain_context="cybersecurity and digital privacy"):
    """Summarize a story in plain English."""
    source_note = ""
    if story.get("type") == "x_post":
        source_note = f"This is a post from X/Twitter by {story.get('source', 'unknown')}."
    elif story.get("type") == "github":
        source_note = f"This is a GitHub repository. Stars: {story.get('stars', 'N/A')}. Language: {story.get('language', 'N/A')}."

    prompt = f"""Write a concise 2-3 sentence description of this {domain_context} news item. Be clear, informative, and factual. No jargon-heavy language — write for a general tech audience.

Title: {story['title']}
Summary: {story.get('summary', 'No details available.')}
Source: {story.get('source', 'Unknown')}
{source_note}

Write ONLY the description, no preamble:"""

    return _generate(prompt, max_tokens=200)


def generate_headline(story):
    """Generate a dramatic 1880s-style headline."""
    prompt = f"""You MUST rewrite this headline completely in the dramatic style of an 1880s newspaper. Do NOT repeat the original headline. Make it sensational, Victorian, and punchy. Use title case. Keep it under 15 words.

Original: {story['title']}
Context: {story.get('summary', '')[:200]}

Example rewrites:
- "Major data breach at hospital" -> "Nefarious Scoundrels Plunder Hospital Ledgers in Audacious Digital Burglary"
- "New encryption standard released" -> "Impenetrable Cypher Engine Unveiled to Thunderous Acclaim"
- "Ransomware gang arrested" -> "Scotland Yard of the Ether Nets Notorious Band of Digital Highwaymen"

Your dramatic Victorian rewrite:"""

    result = _generate(prompt, max_tokens=50)
    result = result.strip('"\'').strip()
    if not result or result.lower() == story["title"].lower():
        return f"Most Alarming: {story['title']}"
    return result


def editorialize(stories, domain_context="cybersecurity, artificial intelligence, and blockchain"):
    """Write an editor's column summarizing the day's themes."""
    briefs = []
    for i, s in enumerate(stories[:12], 1):
        briefs.append(f"{i}. {s['title']}: {s.get('summary', '')[:150]}")
    stories_text = "\n".join(briefs)

    prompt = f"""You are the editor-in-chief of "The Cypher Sentinel," an 1880s newspaper covering {domain_context}. Write a short Editor's Column (3-4 sentences) identifying the overarching themes in today's stories. Write in a Victorian editorial voice — authoritative, slightly pompous, but genuinely concerned about the state of the digital dominion.

Today's stories:
{stories_text}

Write ONLY the editorial column, no title or preamble:"""

    return _generate(prompt, max_tokens=300)


def generate_telegram_digest(stories, editorial):
    """Generate a concise Telegram-friendly digest."""
    briefs = []
    for s in stories[:10]:
        briefs.append(f"- {s['title']}: {s.get('summary', '')[:100]}")
    stories_text = "\n".join(briefs)

    prompt = f"""Write a very brief Telegram notification for "The Cypher Sentinel" newsletter. Say the new issue is out, then list the 4-5 most important headlines as short bullet points (one line each). Keep the entire message under 500 characters. No links.

Stories:
{stories_text}

Write the notification:"""

    return _generate(prompt, max_tokens=150)
