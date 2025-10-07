"""
Paper curation using a Generative AI model.
"""

import json
from langchain_google_genai import ChatGoogleGenerativeAI
from . import config

def get_llm():
    """Initializes and returns the ChatGoogleGenerativeAI model."""
    try:
        llm = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash-lite",
            verbose=True,
            google_api_key=config.GEMINI_API_KEY
        )
        print(f"✓ LLM initialized: {llm.model}")
        return llm
    except Exception as e:
        print(f"Error initializing LLM: {e}")
        return None

def curate_papers(papers: list, guidance_context: str, llm) -> list:
    """Curates and scores a list of papers using the provided LLM.

    Args:
        papers: List of paper dictionaries from arXiv search.
        guidance_context: Context string to guide scoring.
        llm: The initialized ChatGoogleGenerativeAI model.

    Returns:
        List of papers with added curation data and normalized keywords.
    """
    from . import database

    if not papers:
        return []

    # Load keyword mappings
    keyword_data = database.load_keyword_mappings()
    mappings = keyword_data.get("mappings", {})

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
1. Assign a relevance score from 1 (low) to 10 (high) based on the guidance context.
2. Write a brief (1-2 sentence) justification for your score.
3. Extract 3-5 keywords or key concepts from the abstract.

Respond ONLY with valid JSON in this exact format:
{{
    "relevance_score": <number 1-10>,
    "score_justification": "<your justification>",
    "keywords": ["keyword1", "keyword2", "keyword3"]
}}"""

        try:
            response = llm.invoke(prompt)
            response_text = response.content if hasattr(response, 'content') else str(response)

            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()

            curation_data = json.loads(response_text)

            # Normalize keywords
            if 'keywords' in curation_data:
                normalized_keywords = [
                    database.normalize_keyword(kw, mappings)
                    for kw in curation_data['keywords']
                ]
                # Deduplicate after normalization
                curation_data['keywords'] = list(set(normalized_keywords))

            curated_paper = {**paper, **curation_data}
            curated_papers.append(curated_paper)
            print(f"Scored '{paper['title'][:60]}...' -> {curation_data['relevance_score']}/10")

        except Exception as e:
            print(f"Error curating paper '{paper['title'][:60]}...': {e}")
            curated_papers.append(paper) # Add paper without curation data

    return curated_papers
