# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

arxivqml is a Python tool for automatically curating Quantum Machine Learning (QML) research papers from arXiv using MongoDB for storage and Google's Gemini AI for relevance scoring.

## Architecture

The project follows a modular pipeline architecture:

1. **arxiv_search.py**: Queries arXiv API for papers matching specific categories and search terms
2. **curation.py**: Uses Gemini LLM to score papers (1-10) based on guidance context and extract keywords
3. **database.py**: Manages MongoDB operations (connection, deduplication, insertion, retrieval)
4. **config.py**: Centralizes configuration including:
   - MongoDB connection (MONGO_URI from .env)
   - Gemini API key (GEMINI_API_KEY from .env)
   - Search categories (quant-ph, cs.LG, cs.AI, cond-mat.dis-nn, math-ph)
   - Dynamic scoring guidance context
5. **main.py**: Orchestrates the full pipeline (search → curate → store)

**Data Flow**: For each arXiv category → Search new papers → Filter duplicates → Score with LLM → Store in MongoDB with relevance_score, score_justification, keywords, and timestamp_added

## Environment Setup

**Conda environment** (not .venv): Install dependencies using conda

```bash
conda env create -f environment.yml
conda activate arxiv
```

**Install package in development mode**:

```bash
pip install -e .
```

**Environment variables** (.env file required):

```bash
MONGO_URI=mongodb://localhost:27017/
GEMINI_API_KEY=your_api_key_here
```

## Running the Application

**Run the main curation job**:

```bash
python -m arxivqml.main
```

**Interactive exploration**: Use `arxivqml/demo.ipynb` for testing queries and viewing results

## Development Notes

- Use loguru logger for all logging requirements
- MongoDB database: `arxiv_research`, collection: `qml_papers`
- LLM model: `gemini-2.0-flash-lite` via langchain-google-genai
- Papers are deduplicated by `entry_id` before insertion
- Max 25 results per arXiv category search to stay focused
