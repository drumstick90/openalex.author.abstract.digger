"""
Biomedical Abstract Explorer

A tool to retrieve all works and abstracts for a given author,
using OpenAlex as the primary source and PubMed as fallback.
"""

from .author_resolver import resolve_author, list_candidates
from .works_fetcher import fetch_all_works, fetch_works_paginated, extract_work_metadata
from .abstract_extractor import extract_abstract, extract_openalex_abstract, fetch_pubmed_abstract

__version__ = "0.1.0"
__all__ = [
    "resolve_author",
    "list_candidates", 
    "fetch_all_works",
    "fetch_works_paginated",
    "extract_work_metadata",
    "extract_abstract",
    "extract_openalex_abstract",
    "fetch_pubmed_abstract",
]

