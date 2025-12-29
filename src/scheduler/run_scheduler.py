# src/scheduler.py
import time
import json
import redis
from datetime import datetime, timezone
from src.config import settings
from src.db.database import get_db
from src.models.config_models import SocialTarget
from src.utils.governance import SocialGovernance

def run_scheduler():
    r = redis.Redis.from_url(settings.REDIS_URL)
    db = get_db()
    
    print("[SCHEDULER] 🚀 Social Scheduler Started.")

    while True:
        try:
            # 1. Fetch raw dicts
            raw_targets = list(db.targets.find({"enabled": True}))
            
            count = 0
            for raw in raw_targets:
                try:
                    # 2. Convert to Pydantic Model (Validation)
                    # This ensures 'config' exists and has defaults
                    target = SocialTarget(**raw)
                    
                    # 3. Governance Check
                    if SocialGovernance.can_fetch(target):
                        
                        # 4. Create Job
                        job_payload = {
                            "task": "scrape_profile",
                            "username": target.username,
                            "limit": target.config.max_tweets,
                            "target_id": str(target.id)
                        }
                        
                        r.lpush(settings.QUEUE_NAME, json.dumps(job_payload))
                        
                        # 5. Update Status immediately
                        db.targets.update_one(
                            {"_id": target.id}, # Pydantic handles the ObjectId mapping
                            {"$set": {"last_run_at": datetime.now(timezone.utc)}}
                        )
                        
                        print(f"[SCHEDULER] 🟢 Queued @{target.username}")
                        count += 1
                        
                except Exception as e:
                    print(f"[SCHEDULER] ⚠️ Validation failed for a target: {e}")

            if count > 0:
                print(f"[SCHEDULER] ➡️ Pushed {count} jobs.")

        except Exception as e:
            print(f"[SCHEDULER] ❌ Loop Error: {e}")

        time.sleep(60) # Poll every minute

if __name__ == "__main__":
    run_scheduler()