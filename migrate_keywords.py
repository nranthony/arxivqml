"""
Migration script to normalize existing keywords in the database.
Run this once to apply keyword mappings to existing papers.
"""

from arxivqml import database

def migrate_keywords():
    """Apply keyword normalization to all existing papers."""
    print("Starting keyword migration...")

    # Connect to database
    collection = database.get_db_collection()
    if collection is None:
        print("❌ Failed to connect to database")
        return

    # Load keyword mappings
    keyword_data = database.load_keyword_mappings()
    mappings = keyword_data.get("mappings", {})

    if not mappings:
        print("⚠️  No keyword mappings found in keywords.json")
        return

    print(f"Loaded {len(mappings)} keyword mappings")

    # Count papers before migration
    total_papers = collection.count_documents({})
    print(f"Total papers in database: {total_papers}")

    # Show keyword stats before migration
    print("\n--- Before Migration ---")
    keywords_before = database.get_unique_keywords(collection)
    print(f"Unique keywords: {len(keywords_before)}")

    # Show sample of keywords before (to see capitalization)
    print("Sample keywords (before):", ", ".join(sorted(keywords_before)[:10]))

    # Apply normalization
    print("\nApplying keyword normalization...")
    try:
        updated_count, error_count = database.normalize_paper_keywords(collection, mappings, verbose=False)
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return

    # Show keyword stats after migration
    print("\n--- After Migration ---")
    keywords_after = database.get_unique_keywords(collection)
    print(f"Unique keywords: {len(keywords_after)}")
    print(f"Papers updated: {updated_count}/{total_papers}")
    print(f"Errors encountered: {error_count}")
    print(f"Reduction: {len(keywords_before) - len(keywords_after)} keywords collapsed")

    # Show sample of keywords after (to see capitalization)
    print("Sample keywords (after):", ", ".join(sorted(keywords_after)[:10]))

    print("\n✅ Migration complete!")

    # Show top keywords after normalization
    print("\n--- Top 15 Keywords (after normalization) ---")
    keyword_freq = database.get_keyword_frequencies(collection)
    sorted_keywords = sorted(keyword_freq.items(), key=lambda x: x[1], reverse=True)
    for keyword, count in sorted_keywords[:15]:
        print(f"  {keyword}: {count} papers")

if __name__ == "__main__":
    migrate_keywords()
