"""
Main script to run the arXiv QML curation job.
"""

from datetime import datetime
from . import config
from . import database
from . import arxiv_search
from . import curation

def run_arxiv_search_job():
    """Runs the full arXiv search and curation job."""
    print(f"\n--- Starting new arXiv search job at {datetime.now()} ---")

    # 1. Initialize connections
    collection = database.get_db_collection()
    if not collection:
        return

    llm = curation.get_llm()
    if not llm:
        return

    # 2. Loop through categories and process papers
    for category in config.CATEGORIES:
        print(f"\n--- Processing category: {category} ---")

        # Step 2a: Search arXiv for new papers
        new_papers = arxiv_search.search_arxiv(
            category=category, 
            query=config.QUERY_STRING, 
            collection=collection
        )

        if not new_papers:
            print(f"No new papers found for category '{category}'.")
            continue

        # Step 2b: Curate and score papers with LLM
        curated_papers = curation.curate_papers(
            papers=new_papers,
            guidance_context=config.GUIDANCE_CONTEXT,
            llm=llm
        )

        # Step 2c: Filter papers by relevance score threshold
        filtered_papers = [
            p for p in curated_papers
            if p.get('relevance_score', 0) >= config.MIN_RELEVANCE_SCORE
        ]

        if filtered_papers:
            print(f"Filtered {len(curated_papers)} papers to {len(filtered_papers)} "
                  f"(threshold: {config.MIN_RELEVANCE_SCORE}/10)")

        # Step 2d: Insert filtered papers into the database
        if filtered_papers:
            database.insert_papers(collection, filtered_papers)

    print(f"\n--- Job finished at {datetime.now()} ---")

if __name__ == '__main__':
    run_arxiv_search_job()
