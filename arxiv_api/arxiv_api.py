import os
# import schedule
import time
import arxiv
from pymongo import MongoClient
from datetime import datetime
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import json

load_dotenv()

# --- Configuration ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "arxiv_research"
COLLECTION_NAME = "qml_papers"
# Your Gemini API key should be set as an environment variable (GEMINI_API_KEY)

# --- LLM Configuration ---
gemini_llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-flash",  # Options: gemini-1.5-pro, gemini-1.5-flash, gemini-2.0-flash-exp
    verbose=True,
    google_api_key=os.getenv("GEMINI_API_KEY")
)

# --- MongoDB Connection ---
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]
print("Successfully connected to MongoDB.")


# --- arXiv Search Function ---
def search_arxiv(category: str, query: str) -> list:
    """Searches arXiv for papers in specific categories using a targeted query.

    Args:
        category: arXiv category (e.g., 'quant-ph', 'cs.LG')
        query: Search query string

    Returns:
        List of paper dictionaries
    """
    print(f"Executing arXiv search in '{category}' for query: '{query}'...")
    search = arxiv.Search(
        query=f'cat:{category} AND ({query})',
        max_results=25,  # Limit results per search to keep it focused
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    results = []
    for result in search.results():
        # Avoid duplicates
        if collection.find_one({"entry_id": result.entry_id}):
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


# --- Paper Curation with LLM ---
def curate_papers(papers: list, guidance_context: str) -> list:
    """Curate and score papers using LLM.

    Args:
        papers: List of paper dictionaries from arXiv search
        guidance_context: Context string to guide scoring

    Returns:
        List of papers with added relevance_score, score_justification, and keywords
    """
    if not papers:
        return []

    curated_papers = []

    for paper in papers:
        prompt = f"""Analyze this research paper and provide a relevance score.

GUIDANCE CONTEXT:
{guidance_context}

PAPER DETAILS:
Title: {paper['title']}
Authors: {', '.join(paper['authors'])}
Abstract: {paper['summary']}
Categories: {', '.join(paper['categories'])}

TASK:
1. Assign a relevance score from 1 (low) to 10 (high) based on the guidance context
2. Write a brief (1-2 sentence) justification for your score
3. Extract 3-5 keywords or key concepts from the abstract

Respond ONLY with valid JSON in this exact format:
{{
    "relevance_score": <number 1-10>,
    "score_justification": "<your justification>",
    "keywords": ["keyword1", "keyword2", "keyword3"]
}}"""

        try:
            response = gemini_llm.invoke(prompt)
            # Extract JSON from response
            response_text = response.content if hasattr(response, 'content') else str(response)

            # Handle potential markdown formatting
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            curation_data = json.loads(response_text)

            # Merge original paper data with curation data
            curated_paper = {**paper, **curation_data}
            curated_papers.append(curated_paper)

            print(f"Scored '{paper['title'][:60]}...' -> {curation_data['relevance_score']}/10")

        except Exception as e:
            print(f"Error curating paper '{paper['title'][:60]}...': {e}")
            # Add paper without curation data
            curated_papers.append(paper)

    return curated_papers


def run_arxiv_search_job():
    """
    Runs the arXiv search and curation job.
    """
    print(f"\n--- Starting new arXiv search job at {datetime.now()} ---")

    # --- Dynamic Context for the Curator ---
    # This context can be updated to guide the scoring
    guidance_context = (
        "My primary interest is in practical and near-term Quantum Machine Learning. "
        "Score papers higher if they mention: "
        "1. Specific algorithms like VQAs, QAOA, Quantum Kernels, or QNNs. "
        "2. Benchmarking against classical methods or other quantum algorithms. "
        "3. Implementations on actual quantum hardware or widely used simulators (like PennyLane). "
        "4. Association with major quantum computing companies (IBM, Google Quantum AI, Xanadu, D-Wave, etc.). "
        "Score lower if the paper is purely theoretical, highly abstract (e.g., quantum algebra), or lacks a clear connection to machine learning."
    )

    # --- Search Parameters ---
    # Base search terms
    search_terms = [
        '"Quantum Machine Learning"', '"QML"', '"Quantum AI"',
        '"Variational Quantum Algorithm"', '"VQA"', '"Quantum Neural Network"',
        '"Quantum Kernel Method"', '"Quantum Support Vector Machine"',
        '"Quantum Annealing" AND "machine learning"',
        '"parameterized quantum circuit"'
    ]
    query_string = " OR ".join([f'ti:"{term}" OR abs:"{term}"' for term in search_terms])

    # arXiv categories to search
    categories = [
        "quant-ph",  # Quantum Physics (Core)
        "cs.LG",     # Machine Learning (CS)
        "cs.AI",     # Artificial Intelligence (CS)
        "cond-mat.dis-nn",  # Disordered Systems and Neural Networks (Physics)
        "math-ph"    # Mathematical Physics
    ]

    for category in categories:
        print(f"\n--- Processing category: {category} ---")

        # Step 1: Search arXiv
        papers = search_arxiv(category, query_string)

        if not papers:
            print(f"No new papers found for category '{category}'.")
            continue

        # Step 2: Curate and score papers with LLM
        curated_papers = curate_papers(papers, guidance_context)

        # --- Database Insertion ---
        try:
            if curated_papers:
                for paper in curated_papers:
                    # Ensure we don't insert duplicates from a failed run
                    if not collection.find_one({"entry_id": paper.get("entry_id")}):
                        paper['timestamp_added'] = datetime.now(datetime.UTC)
                        collection.insert_one(paper)
                print(f"Successfully inserted {len(curated_papers)} new papers into MongoDB for category '{category}'.")

        except Exception as e:
            print(f"An error occurred during database insertion for category '{category}': {e}")


if __name__ == "__main__":
    # --- Scheduling ---
    # Run the job every 24 hours
    # schedule.every(24).hours.do(run_arxiv_search_job)

    print("Scheduler started. First job will run immediately, then every 24 hours.")
    
    # Run the job once immediately
    run_arxiv_search_job()

    while True:
        schedule.run_pending()
        time.sleep(1)
