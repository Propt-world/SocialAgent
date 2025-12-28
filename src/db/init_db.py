import logging
from pymongo import ASCENDING, DESCENDING
from src.db.database import get_db

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DB_INIT")

def init_db():
    """
    Initializes MongoDB collections and indexes.
    Idempotent: Can be run multiple times safely.
    """
    db = get_db()
    
    logger.info("⚙️  Initializing Database Indexes...")

    # --- 1. TARGETS COLLECTION ---
    # Constraint: A username must be unique per platform
    # Example: You can't have two "PakStartup" entries for "twitter"
    db.targets.create_index(
        [("username", ASCENDING), ("platform", ASCENDING)],
        unique=True,
        name="unique_source_constraint"
    )
    logger.info("✅ Targets: Unique Index (Username + Platform) created.")

    # --- 2. POSTS COLLECTION ---
    # Constraint: Prevent duplicate tweets (based on our generated _id)
    # Note: _id is unique by default in Mongo, but we ensure our custom ID is used.
    
    # Search Index: Fast lookup by source username (for filtering)
    db.posts.create_index(
        [("source_username", ASCENDING)],
        name="source_username_lookup"
    )
    
    # Sort Index: Fast sorting by publication date (for "Recent Tweets")
    db.posts.create_index(
        [("published_at", DESCENDING)],
        name="sort_by_date"
    )
    
    # TTL Index (Optional): Auto-delete tweets older than 1 year to save space?
    # db.posts.create_index("discovered_at", expireAfterSeconds=31536000) 

    logger.info("✅ Posts: Search & Sort Indexes created.")
    logger.info("🚀 Database Initialization Complete.")

if __name__ == "__main__":
    init_db()