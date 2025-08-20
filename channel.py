import streamlit as st
import requests
import pandas as pd
import re
from functools import lru_cache

# ─── YOUR YOUTUBE DATA API KEY ────────────────────────────────────────────────
API_KEY = "AIzaSyAeMNLtJxQwsIlk8Z99TyrC9Xvo6DRDbf8"

# ─── YOUTUBE API ENDPOINTS ─────────────────────────────────────────────────────
YT_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"
YT_SEARCH_URL  = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS_URL  = "https://www.googleapis.com/youtube/v3/videos"

# ─── STREAMLIT SETUP ───────────────────────────────────────────────────────────
st.set_page_config(page_title="YouTube Channel Analyzer", layout="wide")
st.title("🔍 YouTube Channel Analyzer")

channel_url = st.text_input("Enter YouTube Channel URL")

@lru_cache(maxsize=32)
def fetch_json(url: str, params: tuple):
    resp = requests.get(url, params=dict(params))
    resp.raise_for_status()
    return resp.json()

def extract_channel_id(url: str) -> str:
    url = url.strip()

    # 1) /channel/UC...
    m = re.search(r"/channel/([A-Za-z0-9_-]{24,})", url)
    if m:
        return m.group(1)

    # 2) /user/ or /c/
    m = re.search(r"/(?:user|c)/([A-Za-z0-9_-]+)", url)
    if m:
        username = m.group(1)
        data = fetch_json(
            YT_CHANNEL_URL,
            (("part", "snippet"), ("forUsername", username), ("key", API_KEY))
        )
        items = data.get("items", [])
        if items:
            return items[0]["id"]

    # 3) @Handle
    m = re.search(r"@([A-Za-z0-9_-]+)", url)
    if m:
        handle = m.group(1)
        search = fetch_json(
            YT_SEARCH_URL,
            (
                ("part", "snippet"),
                ("q", handle),
                ("type", "channel"),
                ("maxResults", "1"),
                ("key", API_KEY),
            )
        )
        items = search.get("items", [])
        if items:
            return items[0]["snippet"]["channelId"]

    # 4) Fallback: scrape HTML
    try:
        html = requests.get(url).text
        m = re.search(r'"channelId"\s*:\s*"([^"]+)"', html)
        if m:
            return m.group(1)
    except Exception:
        pass

    return None

def analyze_channel(channel_id: str):
    chan = fetch_json(
        YT_CHANNEL_URL,
        (("part", "snippet,statistics"), ("id", channel_id), ("key", API_KEY))
    )["items"][0]

    snip, stats = chan["snippet"], chan["statistics"]
    title       = snip["title"]
    created_at  = snip["publishedAt"][:10]
    subs        = int(stats.get("subscriberCount", 0))
    total_views = int(stats.get("viewCount", 0))
    vid_count   = int(stats.get("videoCount", 0))
    monetized   = subs >= 1000

    search = fetch_json(
        YT_SEARCH_URL,
        (
            ("part", "snippet"),
            ("channelId", channel_id),
            ("order", "viewCount"),
            ("maxResults", "5"),
            ("type", "video"),
            ("key", API_KEY),
        )
    )["items"]

    top_videos, all_tags = [], []
    for item in search:
        vid_id = item["id"]["videoId"]
        vid = fetch_json(
            YT_VIDEOS_URL,
            (("part", "snippet,statistics"), ("id", vid_id), ("key", API_KEY))
        )["items"][0]

        s, stt = vid["snippet"], vid["statistics"]
        tags = s.get("tags", [])
        all_tags += tags

        top_videos.append({
            "Title": s["title"],
            "Views": int(stt.get("viewCount", 0)),
            "URL":   f"https://youtu.be/{vid_id}",
            "Tags":  ", ".join(tags[:5])
        })

    common_kw = pd.Series(all_tags).value_counts().head(10).index.tolist()

    return {
        "title": title,
        "created_at": created_at,
        "subs": subs,
        "total_views": total_views,
        "vid_count": vid_count,
        "monetized": monetized,
        "top_videos": pd.DataFrame(top_videos),
        "keywords": common_kw
    }

if st.button("Analyze Channel"):
    channel_id = extract_channel_id(channel_url)
    if not channel_id:
        st.error("Could not parse or resolve channel ID. Ensure the URL is valid.")
    else:
        data = analyze_channel(channel_id)

        st.subheader("📋 Channel Overview")
        st.markdown(f"""
**Title:** {data['title']}  
**Created On:** {data['created_at']}  
**Subscribers:** {data['subs']:,}  
**Total Views:** {data['total_views']:,}  
**Total Videos:** {data['vid_count']}  
**Monetization Eligible?** {'✅ Yes' if data['monetized'] else '❌ No'}  
""")

        st.subheader("🏆 Top 5 Most-Viewed Videos")
        st.table(data["top_videos"])

        st.subheader("🔑 Common Keywords/Tags")
        st.write(", ".join(data["keywords"]))

        st.subheader("🚀 Steps to Build a Channel Like This")
        for step in [
            "1. Pick a clear niche and study the audience.",
            "2. Analyze competitors’ top videos for format & style.",
            "3. Craft SEO-rich titles, thumbnails, and descriptions.",
            "4. Invest in basic equipment and learn editing.",
            "5. Upload consistently and engage in comments.",
            "6. Promote across social platforms and community forums.",
            "7. Monitor Analytics: watch time, retention, traffic sources.",
            "8. Iterate content based on what works best.",
            "9. Aim for ≥1,000 subscribers and 4,000 watch-hours to monetize.",
            "10. Apply for YouTube Partner Program once thresholds are met."
        ]:
            st.write(step)
