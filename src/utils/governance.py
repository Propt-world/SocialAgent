# src/governance.py
from datetime import datetime, timezone, timedelta
from src.models.config_models import SocialTarget

class SocialGovernance:
    @staticmethod
    def can_fetch(target: SocialTarget) -> bool:
        """
        Checks if the target is due for a scrape.
        """
        if not target.enabled:
            return False

        if not target.last_run_at:
            return True

        # Ensure timezone aware
        last_run = target.last_run_at
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)

        # Use config from the model
        interval = target.config.fetch_interval_minutes
        next_run = last_run + timedelta(minutes=interval)
        
        return datetime.now(timezone.utc) >= next_run