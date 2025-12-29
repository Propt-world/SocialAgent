# src/worker/methods.py
import asyncio
import redis
import json
import traceback
import sys
from datetime import datetime
from src.config import settings
from src.db.database import get_db
from src.scrapper.twitter_lib import init_twitter_session, fetch_profile_tweets
from src.utils.email_utils import send_error_email

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
                    post_dict = post.model_dump(by_alias=True)
                    
                    res = db.posts.update_one(
                        {"_id": post_dict["_id"]},
                        {"$set": post_dict},
                        upsert=True
                    )
                    if res.upserted_id:
                        new += 1
                except Exception as e:
                    print(f"[WORKER] ⚠️ Tweet Save Error: {e}")

            print(f"[WORKER] 💾 Saved {new} new tweets from @{username}")

async def run_worker():
    r = redis.Redis.from_url(settings.REDIS_URL)
    db = get_db()
    
    # Ensure Twitter session is valid before starting
    await init_twitter_session()
    
    print(f"[WORKER] 🚀 Listening on {settings.QUEUE_NAME}...")
    
    while True:
        try:
            # Blocking Pop: Waits here until a job arrives
            _, raw_data = r.brpop(settings.QUEUE_NAME)
            
            if raw_data:
                job_data = json.loads(raw_data)
                try:
                    # Try to process the job
                    await process_job(job_data, db)
                    
                except Exception as e:
                    # --- FAILURE HANDLER ---
                    error_msg = str(e)
                    print(f"[WORKER] ❌ Job Failed: {error_msg}")
                    
                    # 1. Enrich job with error metadata
                    job_data["error"] = error_msg
                    job_data["failed_at"] = str(datetime.now())
                    
                    # 2. Push to Dead Letter Queue (DLQ)
                    r.lpush(settings.DLQ_NAME, json.dumps(job_data))
                    print(f"[WORKER] ⚠️  Moved to DLQ: {settings.DLQ_NAME}")
                    
                    # 3. Send Email Alert
                    send_error_email(
                        job_id=job_data.get("job_id", "unknown"),
                        source_url=f"https://twitter.com/{job_data.get('username', 'unknown')}",
                        error_details=error_msg,
                        traceback_info=traceback.format_exc()
                    )

        except Exception as system_error:
            # Handles Redis connection errors or other critical system failures
            print(f"[WORKER] ☠️ Critical System Error: {system_error}")
            await asyncio.sleep(5) # Backoff to prevent CPU spam

if __name__ == "__main__":
    asyncio.run(run_worker())