import streamlit as st
import requests
import pandas as pd
import altair as alt
from datetime import datetime, timedelta
from functools import lru_cache

# --- YouTube API endpoints ---
YOUTUBE_SEARCH_URL   = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_VIDEO_URL    = "https://www.googleapis.com/youtube/v3/videos"
YOUTUBE_CHANNEL_URL  = "https://www.googleapis.com/youtube/v3/channels"

# --- Your API Key ---
API_KEY = "AIzaSyAeMNLtJxQwsIlk8Z99TyrC9Xvo6DRDbf8"

# --- Streamlit setup ---
st.set_page_config(page_title="Viral Topics Dashboard", layout="wide")
st.title("📈 YouTube Viral Topics Dashboard")

# --- Sidebar: filters & keywords ---
st.sidebar.header("Search & Filter Settings")
days       = st.sidebar.slider("Search Past Days", 1, 30, value=7)
min_views  = st.sidebar.number_input("Min Views", min_value=0, value=1000, step=500)
max_subs   = st.sidebar.number_input("Max Subscribers", min_value=0, value=3000, step=500)
sort_by    = st.sidebar.selectbox("Sort By", ["Views", "Likes", "Comments", "PublishDate"])
ascending  = st.sidebar.checkbox("Ascending Order", value=False)

st.sidebar.header("Keywords (one per line)")
keywords = st.sidebar.text_area(
    "Enter keywords",
    value="Affair Relationship Stories\nReddit Relationship Advice\nCheating Story Real"
).splitlines()

# --- Hashable cache wrapper ---
@lru_cache(maxsize=128)
def fetch_json(url: str, params_tuple: tuple):
    """Convert params_tuple back to dict, then GET and return JSON."""
    params = dict(params_tuple)
    resp = requests.get(url, params=params)
    resp.raise_for_status()
    return resp.json()

# --- Core data-fetching function ---
def get_results(keywords: list, api_key: str, days: int) -> pd.DataFrame:
    cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat("T") + "Z"
    rows = []

    for kw in keywords:
        # 1) Search videos
        search_params = {
            "part": "snippet",
            "q": kw,
            "type": "video",
            "order": "viewCount",
            "publishedAfter": cutoff,
            "maxResults": 10,
            "key": api_key
        }
        search_data = fetch_json(
            YOUTUBE_SEARCH_URL,
            tuple(sorted(search_params.items()))
        )

        for item in search_data.get("items", []):
            vid_id = item["id"].get("videoId")
            if not vid_id:
                continue

            # 2) Video statistics
            stats_params = {
                "part": "statistics",
                "id": vid_id,
                "key": api_key
            }
            stats_data = fetch_json(
                YOUTUBE_VIDEO_URL,
                tuple(sorted(stats_params.items()))
            )

            # 3) Video snippet (for publish date, channelId)
            snippet_params = {
                "part": "snippet",
                "id": vid_id,
                "key": api_key
            }
            snippet_data = fetch_json(
                YOUTUBE_VIDEO_URL,
                tuple(sorted(snippet_params.items()))
            )

            channel_id = snippet_data["items"][0]["snippet"]["channelId"]

            # 4) Channel stats & info
            channel_params = {
                "part": "statistics,snippet",
                "id": channel_id,
                "key": api_key
            }
            channel_data = fetch_json(
                YOUTUBE_CHANNEL_URL,
                tuple(sorted(channel_params.items()))
            )

            # Extract fields
            sni    = snippet_data["items"][0]["snippet"]
            vstat  = stats_data["items"][0]["statistics"]
            cinfo  = channel_data["items"][0]["snippet"]
            cstat  = channel_data["items"][0]["statistics"]

            rows.append({
                "Keyword":     kw,
                "Title":       sni["title"],
                "Channel":     cinfo["title"],
                "PublishDate": sni["publishedAt"],
                "Views":       int(vstat.get("viewCount", 0)),
                "Likes":       int(vstat.get("likeCount", 0)),
                "Comments":    int(vstat.get("commentCount", 0)),
                "Subscribers": int(cstat.get("subscriberCount", 0)),
                "URL":         f"https://youtu.be/{vid_id}"
            })

    return pd.DataFrame(rows)

# --- Streamlit UI flow ---
if st.button("Fetch & Analyze"):
    with st.spinner("Fetching data from YouTube..."):
        df = get_results(keywords, API_KEY, days)

    if df.empty:
        st.warning("No videos found matching your criteria.")
    else:
        # Apply view/subscriber filters
        df = df[df.Views >= min_views]
        df = df[df.Subscribers <= max_subs]

        # Sort and display
        df = df.sort_values(by=sort_by, ascending=ascending)
        st.dataframe(df.drop(columns=["URL"]), height=400)

        # Export CSV
        st.download_button("Download CSV", df.to_csv(index=False), "viral_topics.csv", "text/csv")

        # Altair bar chart
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X(sort_by, sort=alt.SortField(sort_by, order="descending")),
                y=alt.Y("Title", sort="-x"),
                color="Keyword"
            )
            .properties(width=700, height=400)
        )
        st.altair_chart(chart)
