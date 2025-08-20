import streamlit as st
import requests
import pandas as pd
import re
from datetime import datetime
from functools import lru_cache

# YouTube API endpoints
YT_CHANNEL_URL = "https://www.googleapis.com/youtube/v3/channels"
YT_SEARCH_URL  = "https://www.googleapis.com/youtube/v3/search"
YT_VIDEOS_URL  = "https://www.googleapis.com/youtube/v3/videos"

# Your API key
API_KEY = "AIzaSyAeMNLtJxQwsIlk8Z99TyrC9Xvo6DRDbf8"

# Streamlit page setup
st.set_page_config(page_title="Channel Analyzer", layout="wide")
st.title("🔍 YouTube Channel Analyzer")

# Input
channel_url = st.text_input("Enter YouTube Channel URL", "")

# Cache wrapper for requests
@lru_cache(maxsize=32)
def fetch_json(url: str, params: tuple):
    resp = requests.get(url, params=dict(params))
    resp.raise_for_status()
    return resp.json()

def extract_channel_id(url: str) -> str:
    """
    Supports URLs like:
    - https://www.youtube.com/channel/UCabcd...
    - https://www.youtube.com/@CustomName (resolved via search)
    """
    # 1) Direct /channel/ ID
    m = re.search(r"channel/([A-Za-z0-9_-]+)", url)
    if m:
        return m.group(1)
    # 2) @CustomName or /c/CustomName → resolve via search
    m = re.search(r"(?:@|/c/)([A-Za-z0-9_-]+)", url)
    if m:
        username = m.group(1)
        data = fetch_json(
            YT_CHANNEL_URL,
            (("part", "snippet"), ("forUsername", username), ("key", API_KEY))
        )
        items = data.get("items", [])
        if items:
            return items[0]["id"]
    return None

def analyze_channel(channel_id: str):
    # 1) Channel overview
    chan = fetch_json(
        YT_CHANNEL_URL,
        (("part", "snippet,statistics"), ("id", channel_id), ("key", API_KEY))
    )["items"][0]
    snip = chan["snippet"]
    stats = chan["statistics"]

    title       = snip["title"]
    created_at  = snip["publishedAt"][:10]
    description = snip.get("description", "")[:200] + "…"
    subs        = int(stats.get("subscriberCount", 0))
    total_views = int(stats.get("viewCount", 0))
    vid_count   = int(stats.get("videoCount", 0))

    # 2) Monetization eligibility (public proxy)
    eligible = subs >= 1000  # real watch hours not publicly available

    # 3) Top 5 videos by viewCount
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

    top_videos = []
    all_tags = []
    for item in search:
        vid_id = item["id"]["videoId"]
        vid_snip = fetch_json(
            YT_VIDEOS_URL,
            (("part", "snippet,statistics"), ("id", vid_id), ("key", API_KEY))
        )["items"][0]
        v_snip = vid_snip["snippet"]
        v_stat = vid_snip["statistics"]

        views = int(v_stat.get("viewCount", 0))
        tags  = v_snip.get("tags", [])
        all_tags += tags

        top_videos.append({
            "Title": v_snip["title"],
            "Views": views,
            "URL":   f"https://youtu.be/{vid_id}",
            "Tags":  ", ".join(tags[:5])  # show first 5 tags
        })

    # 4) Common keywords across top videos
    tag_counts = pd.Series(all_tags).value_counts().head(10).index.tolist()

    return {
        "title": title,
        "created_at": created_at,
        "description": description,
        "subs": subs,
        "total_views": total_views,
        "vid_count": vid_count,
        "eligible": eligible,
        "top_videos": pd.DataFrame(top_videos),
        "keywords": tag_counts
    }

if st.button("Analyze Channel"):
    channel_id = extract_channel_id(channel_url.strip())
    if not channel_id:
        st.error("Could not parse or resolve channel ID. Ensure the URL is valid.")
    else:
        data = analyze_channel(channel_id)

        # Display overview
        st.subheader("📋 Channel Overview")
        st.markdown(f"""
        **Title:** {data['title']}  
        **Created On:** {data['created_at']}  
        **Subscribers:** {data['subs']:,}  
        **Total Views:** {data['total_views']:,}  
        **Total Videos:** {data['vid_count']}  
        **Approx. Monetization Eligible?** {'✅ Yes' if data['eligible'] else '❌ No'}  
        **Description:** {data['description']}
        """)

        # Top videos
        st.subheader("🏆 Top 5 Most-Viewed Videos")
        st.table(data["top_videos"])

        # Common keywords
        st.subheader("🔑 Common Keywords / Tags")
        st.write(", ".join(data["keywords"]))

        # Step-by-step guide
        st.subheader("🚀 How to Build a Channel Like This")
        steps = [
            "1. Define a clear niche that resonates with your passion and audience.",
            "2. Research top competitors and map out content gaps.",
            "3. Create a compelling channel banner, logo, and description.",
            "4. Plan your first 10 videos—focus on quality, storytelling, and SEO-rich titles.",
            "5. Invest in good equipment (camera, mic, lighting) and learn basic editing.",
            "6. Publish consistently (e.g., 1–2 videos/week) with eye-catching thumbnails.",
            "7. Engage your viewers: ask questions, reply to comments, and build community.",
            "8. Promote on social media, collaborate with peers, and cross-post teasers.",
            "9. Monitor YouTube Analytics weekly: watch time, retention, traffic sources.",
            "10. Apply for the YouTube Partner Program once you hit 1,000 subs & 4,000 watch-hours."
        ]
        for s in steps:
            st.write(s)
