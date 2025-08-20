import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from functools import lru_cache

# --- Configuration ---
YOUTUBE_SEARCH_URL   = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL    = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL  = "https://www.googleapis.com/youtube/v3/channels"

# Insert your API key here
API_KEY = "AIzaSyAeMNLtJxQwsIlk8Z99TyrC9Xvo6DRDbf8"

# --- App Title & Layout ---
st.set_page_config(page_title="Viral Topics Dashboard", layout="wide")
st.title("📈 YouTube Viral Topics Dashboard")

# --- Sidebar Controls ---
st.sidebar.header("Settings")
days      = st.sidebar.slider("Search Past Days", 1, 30, value=7)
min_views = st.sidebar.number_input("Min Views", min_value=0, value=1000, step=500)
min_subs  = st.sidebar.number_input("Max Subscribers", min_value=0, value=3000, step=500)
sort_by   = st.sidebar.selectbox("Sort By", ["Views", "Likes", "Comments", "PublishDate"])
ascending = st.sidebar.checkbox("Ascending Order", value=False)

# Dynamic keyword list
st.sidebar.header("Keywords")
keywords = st.sidebar.text_area(
    "Enter keywords (one per line)", 
    value="Affair Relationship Stories\nReddit Relationship Advice\nCheating Story Real"
).splitlines()

# --- Caching API Calls ---
@lru_cache(maxsize=128)
def fetch_json(url, params):
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

# --- Data Fetching Function ---
def get_results(keywords, api_key, days):
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat("T") + "Z"
    rows = []
    for kw in keywords:
        params = {
            "part": "snippet",
            "q": kw,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": cutoff,
            "maxResults": 10,
            "key": api_key,
        }
        data = fetch_json(YOUTUBE_SEARCH_URL, tuple(sorted(params.items())))
        for item in data.get("items", []):
            vid = item["id"].get("videoId")
            if not vid: continue

            # Video stats
            stats = fetch_json(YOUTUBE_VIDEO_URL, {"part": "statistics", "id": vid, "key": api_key})
            snip  = fetch_json(YOUTUBE_VIDEO_URL, {"part": "snippet",    "id": vid, "key": api_key})
            ch_id = snip["items"][0]["snippet"]["channelId"]
            ch_stats = fetch_json(YOUTUBE_CHANNEL_URL, {"part": "statistics", "id": ch_id, "key": api_key})

            # Collate
            vid_info   = snip["items"][0]["snippet"]
            vid_stats  = stats["items"][0]["statistics"]
            ch_info    = ch_stats["items"][0]["snippet"]
            ch_stats   = ch_stats["items"][0]["statistics"]

            rows.append({
                "Keyword":     kw,
                "Title":       vid_info["title"],
                "Channel":     ch_info["title"],
                "PublishDate": vid_info["publishedAt"],
                "Views":       int(vid_stats.get("viewCount", 0)),
                "Likes":       int(vid_stats.get("likeCount",  0)),
                "Comments":    int(vid_stats.get("commentCount", 0)),
                "Subscribers": int(ch_stats.get("subscriberCount", 0)),
                "URL":         f"https://youtu.be/{vid}"
            })
    return pd.DataFrame(rows)

# --- Fetch & Display ---
if st.button("Fetch & Analyze"):
    with st.spinner("Querying YouTube…"):
        df = get_results(keywords, API_KEY, days)

    if df.empty:
        st.warning("No videos matched your filters.")
    else:
        df = df[df.Subscribers <= min_subs]
        df = df[df.Views >= min_views]
        df = df.sort_values(by=sort_by, ascending=ascending)

        st.dataframe(df.drop(columns="URL"), height=400)
        st.download_button("Export CSV", df.to_csv(index=False), "viral_topics.csv")

        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X(sort_by, sort=alt.SortField(sort_by, order="descending")),
            y="Title",
            color="Keyword"
        ).properties(width=700, height=400)
        
        st.altair_chart(chart)
