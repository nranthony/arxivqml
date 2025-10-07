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

def get_all_papers(collection, filters: dict = None, sort_by: str = "relevance_score", sort_order: int = -1):
    """Queries papers with dynamic filtering and sorting.

    Args:
        collection: MongoDB collection object.
        filters: Dictionary of filter criteria (e.g., {"primary_category": "quant-ph"}).
        sort_by: Field to sort by (default: "relevance_score").
        sort_order: 1 for ascending, -1 for descending (default: -1).

    Returns:
        List of paper documents.
    """
    query = filters if filters else {}
    return list(collection.find(query).sort(sort_by, sort_order))

def get_unique_keywords(collection):
    """Returns a sorted list of all unique keywords in the database."""
    pipeline = [
        {"$unwind": "$keywords"},
        {"$group": {"_id": "$keywords"}},
        {"$sort": {"_id": 1}}
    ]
    result = collection.aggregate(pipeline)
    return [doc["_id"] for doc in result]

def get_unique_categories(collection):
    """Returns a sorted list of all unique primary categories in the database."""
    categories = collection.distinct("primary_category")
    return sorted(categories)

def get_keyword_frequencies(collection):
    """Returns a dictionary of keywords and their occurrence counts."""
    from collections import Counter
    all_keywords = []
    for paper in collection.find():
        all_keywords.extend(paper.get('keywords', []))
    return dict(Counter(all_keywords))

def normalize_keyword(keyword: str, mappings: dict) -> str:
    """Maps raw keyword to canonical form using mappings dictionary.

    Args:
        keyword: Raw keyword string from paper.
        mappings: Dictionary mapping canonical forms to lists of variants.

    Returns:
        Canonical form of keyword with standardized capitalization.
    """
    keyword_lower = keyword.lower().strip()

    # Find canonical form
    for canonical, variants in mappings.items():
        if keyword_lower in [v.lower() for v in variants]:
            return canonical

    # No mapping found, return with title case capitalization
    # Preserve acronyms (all caps words ≤4 chars) and special cases
    return capitalize_keyword(keyword.strip())

def capitalize_keyword(keyword: str) -> str:
    """Apply consistent capitalization to keywords.

    Rules:
    - Preserve all-caps acronyms (≤4 chars): VQA, QAOA, SVM
    - Title case for phrases: "quantum annealing" → "Quantum Annealing"
    - Special cases: D-Wave, PennyLane, IBM Quantum

    Args:
        keyword: Raw keyword string.

    Returns:
        Keyword with standardized capitalization.
    """
    # Special cases that need exact capitalization
    special_cases = {
        "d-wave": "D-Wave",
        "pennylane": "PennyLane",
        "ibm quantum": "IBM Quantum",
        "xanadu": "Xanadu",
        "vqa": "VQA",
        "vqas": "VQAs",
        "qaoa": "QAOA",
        "qnn": "QNN",
        "svm": "SVM",
        "ml": "ML",
        "ai": "AI",
        "nn": "NN",
        "nns": "NNs"
    }

    keyword_lower = keyword.lower().strip()

    # Check special cases first
    if keyword_lower in special_cases:
        return special_cases[keyword_lower]

    # Check if it's a short acronym (all caps, ≤4 chars, no spaces)
    if len(keyword) <= 4 and keyword.isupper() and ' ' not in keyword:
        return keyword.upper()

    # Default: title case
    return keyword.title()

def normalize_paper_keywords(collection, mappings: dict, verbose: bool = False):
    """Batch normalize all keywords in database with error handling.

    Args:
        collection: MongoDB collection object.
        mappings: Dictionary mapping canonical forms to lists of variants.
        verbose: If True, print progress for each paper.

    Returns:
        Tuple of (updated_count, error_count).
    """
    updated_count = 0
    error_count = 0
    total_papers = collection.count_documents({})

    for i, paper in enumerate(collection.find(), 1):
        try:
            if 'keywords' in paper:
                normalized = [normalize_keyword(kw, mappings) for kw in paper['keywords']]
                # Deduplicate
                normalized = list(set(normalized))

                # Only update if changed
                if normalized != paper['keywords']:
                    collection.update_one(
                        {"_id": paper["_id"]},
                        {"$set": {"keywords": normalized}}
                    )
                    updated_count += 1

                    if verbose:
                        print(f"  [{i}/{total_papers}] Updated: {paper.get('title', 'Unknown')[:60]}...")

        except Exception as e:
            error_count += 1
            print(f"  ⚠️  Error updating paper {paper.get('_id', 'unknown')}: {e}")

    return updated_count, error_count

def load_keyword_mappings(json_path: str = "keywords.json"):
    """Load keyword mappings from JSON file with fallback to backup.

    Args:
        json_path: Path to keywords.json file.

    Returns:
        Dictionary containing mappings, hierarchy, and unmapped keywords.
    """
    import json
    import os

    default_data = {"mappings": {}, "hierarchy": {}, "unmapped_keywords": []}

    if not os.path.exists(json_path):
        return default_data

    # Try to load main file
    try:
        with open(json_path, 'r') as f:
            data = json.load(f)
            # Validate structure
            if not isinstance(data, dict):
                raise ValueError("Invalid JSON structure: root must be a dictionary")
            if "mappings" not in data:
                data["mappings"] = {}
            if "hierarchy" not in data:
                data["hierarchy"] = {}
            if "unmapped_keywords" not in data:
                data["unmapped_keywords"] = []
            return data

    except (json.JSONDecodeError, ValueError) as e:
        print(f"⚠️  Warning: Could not load {json_path}: {e}")

        # Try to load backup
        backup_path = f"{json_path}.bak"
        if os.path.exists(backup_path):
            print(f"Attempting to load backup from {backup_path}...")
            try:
                with open(backup_path, 'r') as f:
                    data = json.load(f)
                    print("✅ Successfully loaded from backup")
                    return data
            except Exception as backup_error:
                print(f"❌ Backup also corrupted: {backup_error}")

        print("Using empty keyword mappings")
        return default_data

def save_keyword_mappings(data: dict, json_path: str = "keywords.json"):
    """Save keyword mappings to JSON file with crash-safe atomic write.

    Uses atomic write pattern: write to temp file, then rename.
    This ensures the file is never corrupted mid-write.

    Args:
        data: Dictionary containing mappings, hierarchy, and unmapped keywords.
        json_path: Path to keywords.json file.
    """
    import json
    import os
    import tempfile
    import shutil

    # Create backup of existing file
    if os.path.exists(json_path):
        backup_path = f"{json_path}.bak"
        try:
            shutil.copy2(json_path, backup_path)
        except Exception as e:
            print(f"Warning: Could not create backup: {e}")

    # Atomic write: write to temp file, then rename
    temp_fd, temp_path = tempfile.mkstemp(
        dir=os.path.dirname(json_path) or '.',
        prefix='.keywords_',
        suffix='.json.tmp'
    )

    try:
        # Write to temp file
        with os.fdopen(temp_fd, 'w') as f:
            json.dump(data, f, indent=2)
            f.flush()
            os.fsync(f.fileno())  # Force write to disk

        # Atomic rename (overwrites target file)
        # On Unix: atomic operation, no partial writes possible
        # On Windows: may fail if file is open, but won't corrupt
        if os.name == 'nt':  # Windows
            # Windows doesn't support atomic replace, need to delete first
            if os.path.exists(json_path):
                os.remove(json_path)
        os.rename(temp_path, json_path)

    except Exception as e:
        # Clean up temp file on error
        try:
            os.remove(temp_path)
        except:
            pass
        raise Exception(f"Failed to save keyword mappings: {e}")

