"""
Database management for MongoDB.
"""

from pymongo import MongoClient
from datetime import datetime

from . import config

def get_db_collection():
    """Establishes a connection to MongoDB and returns the collection object."""
    try:
        client = MongoClient(config.MONGO_URI)
        db = client[config.DB_NAME]
        collection = db[config.COLLECTION_NAME]
        # Test the connection
        client.admin.command('ping')
        print(f"✓ Successfully connected to MongoDB: {config.DB_NAME}.{config.COLLECTION_NAME}")
        return collection
    except Exception as e:
        print(f"Error connecting to MongoDB: {e}")
        return None

def paper_exists(collection, entry_id: str) -> bool:
    """Checks if a paper with the given entry_id already exists in the database."""
    return collection.find_one({"entry_id": entry_id}) is not None

def insert_papers(collection, papers: list):
    """Inserts a list of curated papers into the database, avoiding duplicates."""
    if not papers:
        return

    insert_count = 0
    for paper in papers:
        if not paper_exists(collection, paper.get("entry_id")):
            paper['timestamp_added'] = datetime.utcnow()
            collection.insert_one(paper)
            insert_count += 1
            print(f"✓ Inserted: {paper['title'][:60]}...")
        else:
            print(f"⊘ Already exists: {paper['title'][:60]}...")
    
    print(f"\nSuccessfully inserted {insert_count} new papers into MongoDB.")

def get_top_papers(collection, limit: int = 5):
    """Queries and returns the top papers by relevance score."""
    return collection.find(
        {"relevance_score": {"$exists": True}}
    ).sort("relevance_score", -1).limit(limit)

