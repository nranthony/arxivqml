"""
arXiv API searching functionality.
"""

import arxiv
from .database import paper_exists

def search_arxiv(category: str, query: str, collection) -> list:
    """Searches arXiv for papers, avoiding duplicates already in the database.

    Args:
        category: arXiv category (e.g., 'quant-ph', 'cs.LG').
        query: Search query string.
        collection: The MongoDB collection object for checking duplicates.

    Returns:
        List of new paper dictionaries.
    """
    print(f"Executing arXiv search in '{category}' for query: '{query[:60]}...'" )
    search = arxiv.Search(
        query=f'cat:{category} AND ({query})',
        max_results=25,  # Limit results per search to keep it focused
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    results = []
    client = arxiv.Client()
    for result in client.results(search):
        # Avoid duplicates
        if paper_exists(collection, result.entry_id):
            continue

        result_dict = {
            "entry_id": result.entry_id,
            "title": result.title,
            "authors": [author.name for author in result.authors],
            "summary": result.summary,
            "pdf_url": result.pdf_url,
            "published": result.published,
            "updated": result.updated,
            "primary_category": result.primary_category,
            "categories": result.categories
        }
        results.append(result_dict)

    print(f"Found {len(results)} new papers.")
    return results
