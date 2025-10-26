import os
import time
import feedparser
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime
import json

# === CONFIG ===
FEEDS = [
    "https://thediplomat.com/feed/",
    "https://www.foreignaffairs.com/rss.xml",
    "https://foreignpolicy.com/feed/",
    "https://evilgodfahim.github.io/ps/combined.xml",
    "https://evilgodfahim.github.io/eco/combined.xml",
    "https://www.eiu.com/n/feed/",
]

MASTER_FILE = "feed_master.xml"
DAILY_FILE = "daily_feed.xml"
STATE_FILE = "last_seen.json"
MAX_ITEMS = 500

# Bangladesh time offset
BD_TIME = timezone(timedelta(hours=6))

# === HELPERS ===
def parse_date(entry):
    """Safely parse date from RSS entry."""
    for key in ("published", "pubDate", "updated"):
        if key in entry:
            try:
                return parsedate_to_datetime(entry[key])
            except Exception:
                pass
    return datetime.now(timezone.utc)

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"last_seen": None}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

def load_existing_master():
    """Load existing master feed items (if any)."""
    if not os.path.exists(MASTER_FILE):
        return []
    tree = ET.parse(MASTER_FILE)
    root = tree.getroot()
    items = []
    for item in root.findall("./channel/item"):
        pub_date = item.find("pubDate").text
        try:
            dt = parsedate_to_datetime(pub_date)
        except Exception:
            dt = datetime.now(timezone.utc)
        link = item.find("link").text
        title = item.find("title").text
        description = item.find("description").text
        items.append({
            "title": title,
            "link": link,
            "description": description,
            "pubDate": dt
        })
    return items

def write_rss(items, file_path, title="Aggregated Feed"):
    """Write valid RSS XML file."""
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "link").text = "https://evilgodfahim.github.io/"
    ET.SubElement(channel, "description").text = "Aggregated Inoreader feed"
    for it in items:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = it["title"]
        ET.SubElement(item, "link").text = it["link"]
        ET.SubElement(item, "description").text = it["description"]
        ET.SubElement(item, "pubDate").text = it["pubDate"].strftime("%a, %d %b %Y %H:%M:%S %z")
    tree = ET.ElementTree(rss)
    tree.write(file_path, encoding="utf-8", xml_declaration=True)

# === MASTER FEED UPDATE ===
def update_master():
    print("[Updating feed_master.xml]")
    existing = load_existing_master()
    existing_links = {x["link"] for x in existing}
    new_items = []

    for url in FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries:
                link = getattr(entry, "link", "")
                if link and link not in existing_links:
                    new_items.append({
                        "title": getattr(entry, "title", "No Title"),
                        "link": link,
                        "description": getattr(entry, "summary", ""),
                        "pubDate": parse_date(entry)
                    })
        except Exception as e:
            print(f"Error parsing {url}: {e}")

    all_items = existing + new_items
    all_items.sort(key=lambda x: x["pubDate"], reverse=True)
    all_items = all_items[:MAX_ITEMS]

    write_rss(all_items, MASTER_FILE, title="Master Feed (Updated every 30 mins)")
    print(f"✅ feed_master.xml updated with {len(all_items)} items")

# === DAILY FEED UPDATE ===
def update_daily():
    print("[Generating daily_feed.xml]")
    state = load_state()
    last_seen = state.get("last_seen")

    if not os.path.exists(MASTER_FILE):
        print("No master feed found. Skipping.")
        return

    master_items = load_existing_master()
    master_items.sort(key=lambda x: x["pubDate"], reverse=True)

    if last_seen:
        last_seen_dt = datetime.fromisoformat(last_seen)
        new_items = [i for i in master_items if i["pubDate"] > last_seen_dt]
    else:
        new_items = master_items[:50]  # First run fallback

    if new_items:
        latest_time = max(i["pubDate"] for i in new_items)
        state["last_seen"] = latest_time.isoformat()
        save_state(state)

    write_rss(new_items, DAILY_FILE, title="Daily Feed (Updated 9 AM BD)")
    print(f"✅ daily_feed.xml generated with {len(new_items)} new items")

# === MAIN EXECUTION ===
def main():
    now = datetime.now(timezone.utc).astimezone(BD_TIME)
    # Run master feed every 30 mins
    update_master()

    # Run daily feed only if 9:00 AM BD time (±5 min)
    if now.hour == 9 and now.minute < 5:
        update_daily()

if __name__ == "__main__":
    main()
