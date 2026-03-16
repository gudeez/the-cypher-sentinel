import os
from pathlib import Path

BASE_DIR = Path(__file__).parent

# Auto-load .env file if present
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# --- Ollama ---
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "qwen3.5:latest"

# --- Telegram (matches your other projects' env var names) ---
TG_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TG_CHANNEL_ID = os.environ.get("TG_CHANNEL_ID", "")  # e.g. "@your_channel" or "-100xxxxx"

# --- Domains ---
DOMAINS = {
    "cybersecurity": {
        "name": "Cypher & Sentinel",
        "prompt_context": "cybersecurity and digital privacy",
        "x_heading": "Intercepted Dispatches",
        "github_heading": "Arsenal & Armory",
        "rss_feeds": {
            "Krebs on Security": "https://krebsonsecurity.com/feed/",
            "The Hacker News": "https://feeds.feedburner.com/TheHackersNews",
            "Dark Reading": "https://www.darkreading.com/rss.xml",
            "Schneier on Security": "https://www.schneier.com/feed/atom/",
            "BleepingComputer": "https://www.bleepingcomputer.com/feed/",
            "EFF Deeplinks": "https://www.eff.org/rss/updates.xml",
        },
        "github_topics": ["security", "cybersecurity", "penetration-testing", "malware-analysis",
                          "privacy", "encryption", "vulnerability", "osint"],
        "github_keywords": ["security", "pentest", "exploit", "vulnerability", "malware",
                            "forensics", "encryption", "privacy", "osint", "reverse-engineering",
                            "ctf", "firewall", "ids", "honeypot", "scanner", "audit",
                            "infosec", "cyber", "threat", "phishing", "ransomware",
                            "cryptography", "zero-day", "backdoor", "sandbox", "siem"],
        "x_keyword_sets": {
            "Security": [
                "(cybersecurity OR infosec OR vulnerability OR CVE) (breach OR patch OR exploit OR zero-day) min_faves:50 -is:retweet lang:en",
            ],
            "Privacy": [
                "(privacy OR surveillance OR encryption) (law OR breach OR ruling OR ban) min_faves:50 -is:retweet lang:en",
            ],
            "Threats": [
                "(data breach OR ransomware OR malware) (attack OR leak OR exposed) min_faves:50 -is:retweet lang:en",
            ],
        },
        "x_accounts": {
            "Security": ["briankrebs", "SwiftOnSecurity", "troyhunt", "GossiTheDog", "thegrugq", "taviso"],
            "Privacy": ["EFF", "signalapp", "torproject", "ProtonMail", "evacide"],
            "Research": ["ProjectZeroBugs", "MalwareTechBlog", "hasherezade", "NCCGroupInfosec"],
        },
    },
    "ai": {
        "name": "Engines of Thought",
        "prompt_context": "artificial intelligence and technology",
        "x_heading": "Dispatches from the Wire",
        "github_heading": "The Workshop",
        "rss_feeds": {
            "TechCrunch AI": "https://techcrunch.com/category/artificial-intelligence/feed/",
            "The Verge AI": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
            "Hugging Face": "https://huggingface.co/blog/feed.xml",
            "Google AI": "https://blog.google/technology/ai/rss/",
            "arXiv cs.AI": "https://rss.arxiv.org/rss/cs.AI",
            "MIT Tech Review AI": "https://www.technologyreview.com/feed/",
        },
        "github_topics": ["llm", "artificial-intelligence", "machine-learning", "generative-ai"],
        "github_keywords": ["ai", "llm", "gpt", "model", "neural", "transformer",
                            "machine-learning", "deep-learning", "diffusion", "agent",
                            "inference", "embedding", "langchain", "rag", "fine-tun"],
        "x_keyword_sets": {
            "AI": [
                "(AI OR LLM OR GPT) (launch OR release OR announce OR breakthrough) min_faves:100 -is:retweet lang:en",
            ],
            "Tech": [
                "(Apple OR Microsoft OR Google OR NVIDIA) (announce OR launch OR release) min_faves:100 -is:retweet lang:en",
            ],
        },
        "x_accounts": {
            "AI": ["AnthropicAI", "OpenAI", "GoogleDeepMind", "karpathy", "sama", "ylecun", "DrJimFan", "huggingface", "MistralAI"],
        },
    },
    "blockchain": {
        "name": "Ledger & Chain",
        "prompt_context": "blockchain and cryptocurrency",
        "x_heading": "Market Dispatches",
        "github_heading": "The Forge",
        "rss_feeds": {
            "CoinDesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
            "Cointelegraph": "https://cointelegraph.com/rss",
            "The Block": "https://www.theblock.co/rss.xml",
            "Decrypt": "https://decrypt.co/feed",
            "Bitcoin Magazine": "https://bitcoinmagazine.com/feed",
            "Ethereum World News": "https://en.ethereumworldnews.com/feed/",
        },
        "github_topics": ["blockchain", "ethereum", "solidity", "web3", "defi",
                          "smart-contracts", "bitcoin", "cryptocurrency"],
        "github_keywords": ["blockchain", "ethereum", "solidity", "web3", "defi",
                            "smart-contract", "bitcoin", "crypto", "nft", "token",
                            "dao", "dapp", "layer-2", "rollup", "zk-proof", "wallet",
                            "evm", "solana", "polygon", "avalanche", "cosmos",
                            "hardhat", "foundry", "openzeppelin", "chainlink"],
        "x_keyword_sets": {
            "Blockchain": [
                "(blockchain OR bitcoin OR ethereum OR crypto) (launch OR release OR announce OR breakthrough) min_faves:100 -is:retweet lang:en",
            ],
            "Regulation": [
                "(SEC OR CFTC OR crypto regulation OR stablecoin) (ruling OR law OR ban OR approve) min_faves:50 -is:retweet lang:en",
            ],
            "Markets": [
                "(bitcoin OR BTC OR ETH) (price OR rally OR crash OR halving) min_faves:100 -is:retweet lang:en",
            ],
        },
        "x_accounts": {
            "Blockchain": ["VitalikButerin", "CoinDesk", "punk6529", "aantonop", "ErikVoorhees"],
            "Bitcoin": ["saylor", "DocumentingBTC", "BitcoinMagazine", "adam3us"],
            "DeFi": ["DefiLlama", "UniswapProtocol", "CurveFinance", "AaveAave"],
        },
    },
}

# Backward-compatible flat references for sources that import them
RSS_FEEDS = {}
GITHUB_TOPICS = []
for _d in DOMAINS.values():
    RSS_FEEDS.update(_d["rss_feeds"])
    GITHUB_TOPICS.extend(_d["github_topics"])
GITHUB_TOPICS = list(set(GITHUB_TOPICS))

# --- Output ---
EDITIONS_DIR = BASE_DIR / "editions"
DATA_DIR = BASE_DIR / "data"
SEEN_FILE = DATA_DIR / "seen.json"
MAX_STORIES_PER_DOMAIN = 16
SERVE_PORT = 8080
