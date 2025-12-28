# src/twitter_lib.py
import asyncio
from datetime import datetime, timezone
from twscrape import API, gather
from src.config import settings
from src.models.db_models import SocialPost, TweetMetrics

api = API(settings.TWITTER_DB_PATH)

async def init_twitter_session():
    # ... (Same login logic as before) ...
    pass

async def fetch_profile_tweets(username: str, limit: int) -> list[SocialPost]:
    print(f"[TWITTER] 🔎 Scraping @{username} (Limit: {limit})...")
    try:
        user = await api.user_by_login(username)
        if not user:
            return []

        tweets = await gather(api.user_tweets(user.id, limit=limit))
        results = []

        for t in tweets:
            # Clean Images
            images = []
            if t.media and hasattr(t.media, 'photos'):
                images = [p.url for p in t.media.photos]

            # Create Pydantic Model
            post = SocialPost(
                _id=f"tw-{t.id}",
                source_username=username,
                url=t.url,
                content=t.rawContent,
                images=images,
                metrics=TweetMetrics(
                    likes=t.likeCount,
                    retweets=t.retweetCount,
                    replies=t.replyCount
                ),
                published_at=t.date,
                discovered_at=datetime.now(timezone.utc)
            )
            results.append(post)

        return results
    except Exception as e:
        print(f"[TWITTER] ❌ Error: {e}")
        return []