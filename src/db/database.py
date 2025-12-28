from pymongo import MongoClient
from src.config import settings

def get_db():
    """
    Establishes a connection to the SocialAgent MongoDB.
    Returns the database object so you can access collections 
    like db.targets or db.posts.
    """
    # Create the client using the URL from settings (e.g., mongodb://social_mongo:27018)
    client = MongoClient(settings.DATABASE_URL)
    
    # Return the specific database instance
    return client[settings.MONGO_DB_NAME]