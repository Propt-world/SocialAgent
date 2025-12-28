# src/worker.py
import asyncio
import redis
import json
from src.config import settings
from src.database import get_db
from src.scrapper.twitter_lib import init_twitter_session, fetch_profile_tweets

async def process_job(job: dict, db):
    task = job.get("task")
    username = job.get("username")
    limit = job.get("limit")

    if task == "scrape_profile":
        # Returns List[SocialPost]
        posts = await fetch_profile_tweets(username, limit)
        
        if posts:
            new = 0
            for post in posts:
                try:
                    # Convert Pydantic -> Dict for MongoDB
                    # by_alias=True ensures '_id' is used instead of 'id'
                    post_dict = post.model_dump(by_alias=True)
                    
                    res = db.posts.update_one(
                        {"_id": post_dict["_id"]},
                        {"$set": post_dict},
                        upsert=True
                    )
                    if res.upserted_id:
                        new += 1
                except Exception as e:
                    print(f"[WORKER] Save Error: {e}")

            print(f"[WORKER] 💾 Saved {new} new tweets from @{username}")

async def run_worker():
    r = redis.Redis.from_url(settings.REDIS_URL)
    db = get_db()
    
    await init_twitter_session()
    
    print(f"[WORKER] 🚀 Listening on {settings.QUEUE_NAME}...")
    
    while True:
        # Blocking Pop
        _, data = r.brpop(settings.QUEUE_NAME)
        if data:
            await process_job(json.loads(data), db)

if __name__ == "__main__":
    asyncio.run(run_worker())