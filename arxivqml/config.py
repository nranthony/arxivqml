"""
Configuration for the arXiv QML Curation project.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# --- MongoDB Configuration ---
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = "arxiv_research"
COLLECTION_NAME = "qml_papers"

# --- LLM Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# --- Dynamic Context for the Curator ---
GUIDANCE_CONTEXT = (
    "My primary interest is in practical and near-term Quantum Machine Learning. "
    "Score papers higher if they mention: "
    "1. Specific algorithms like VQAs, QAOA, Quantum Kernels, or QNNs. "
    "2. Benchmarking against classical methods or other quantum algorithms. "
    "3. Implementations on actual quantum hardware or widely used simulators (like PennyLane). "
    "4. Association with major quantum computing companies (IBM, Google Quantum AI, Xanadu, D-Wave, etc.). "
    "Score lower if the paper is purely theoretical, highly abstract (e.g., quantum algebra), or lacks a clear connection to machine learning."
)

# --- arXiv Search Parameters ---
SEARCH_TERMS = [
    '"Quantum Machine Learning"', '"QML"', '"Quantum AI"',
    '"Variational Quantum Algorithm"', '"VQA"', '"Quantum Neural Network"',
    '"Quantum Kernel Method"', '"Quantum Support Vector Machine"',
    '"Quantum Annealing" AND "machine learning"',
    '"parameterized quantum circuit"'
]
QUERY_STRING = " OR ".join([f'ti:{term} OR abs:{term}' for term in SEARCH_TERMS])

# arXiv categories to search
CATEGORIES = [
    "quant-ph",  # Quantum Physics (Core)
    "cs.LG",     # Machine Learning (CS)
    "cs.AI",     # Artificial Intelligence (CS)
    "cond-mat.dis-nn",  # Disordered Systems and Neural Networks (Physics)
    "math-ph"    # Mathematical Physics
]

# --- Relevance Score Filtering ---
MIN_RELEVANCE_SCORE = 5  # Only store papers with score >= this threshold
