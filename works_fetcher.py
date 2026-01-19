"""
Works Fetcher Module

Fetches all works for a given author from OpenAlex with pagination support.
"""

from typing import Iterator
from pyalex import Works
from tqdm import tqdm


def fetch_works_paginated(
    author_id: str,
    per_page: int = 200,
    year_from: int = None,
    year_to: int = None,
    work_types: list[str] = None,
    show_progress: bool = True
) -> Iterator[dict]:
    """
    Fetch all works for an author using cursor pagination.
    
    Args:
        author_id: OpenAlex author ID (e.g., "A5023888391")
        per_page: Number of works per API request (max 200)
        year_from: Optional filter - minimum publication year
        year_to: Optional filter - maximum publication year  
        work_types: Optional filter - list of work types (e.g., ["article", "book"])
        show_progress: Show tqdm progress bar
    
    Yields:
        Work records one by one
    """
    # Build filter
    filters = {"author": {"id": author_id}}
    
    if year_from and year_to:
        filters["publication_year"] = f"{year_from}-{year_to}"
    elif year_from:
        filters["publication_year"] = f">{year_from - 1}"
    elif year_to:
        filters["publication_year"] = f"<{year_to + 1}"
    
    if work_types:
        filters["type"] = "|".join(work_types)
    
    # Create query
    query = Works().filter(**filters)
    
    # Get total count for progress bar
    if show_progress:
        # First request to get count
        meta = query.get(per_page=1, return_meta=True)
        total_count = meta.get("meta", {}).get("count", 0)
        pbar = tqdm(total=total_count, desc="Fetching works")
    
    # Paginate through all results
    for page in query.paginate(per_page=per_page):
        for work in page:
            yield work
            if show_progress:
                pbar.update(1)
    
    if show_progress:
        pbar.close()


def fetch_all_works(
    author_id: str,
    year_from: int = None,
    year_to: int = None,
    work_types: list[str] = None,
    show_progress: bool = True
) -> list[dict]:
    """
    Fetch all works for an author as a list.
    
    Args:
        author_id: OpenAlex author ID (e.g., "A5023888391")
        year_from: Optional filter - minimum publication year
        year_to: Optional filter - maximum publication year
        work_types: Optional filter - list of work types
        show_progress: Show tqdm progress bar
    
    Returns:
        List of all work records
    """
    return list(fetch_works_paginated(
        author_id=author_id,
        year_from=year_from,
        year_to=year_to,
        work_types=work_types,
        show_progress=show_progress
    ))


def get_works_count(author_id: str) -> int:
    """Get total number of works for an author without fetching them all."""
    query = Works().filter(author={"id": author_id})
    meta = query.get(per_page=1, return_meta=True)
    return meta.get("meta", {}).get("count", 0)


def extract_work_metadata(work: dict) -> dict:
    """
    Extract key metadata from a work record.
    
    Returns a simplified dict with the fields we care about.
    """
    # Get IDs
    ids = work.get("ids", {})
    
    # Get DOI (clean format)
    doi = work.get("doi")
    if doi and doi.startswith("https://doi.org/"):
        doi = doi[16:]  # Remove prefix, keep just the DOI
    
    # Get PMID
    pmid = ids.get("pmid")
    if pmid and pmid.startswith("https://pubmed.ncbi.nlm.nih.gov/"):
        pmid = pmid.split("/")[-1]  # Extract just the ID
    
    # Get authors
    authors = []
    for authorship in work.get("authorships", []):
        author_info = authorship.get("author", {})
        if author_info:
            authors.append({
                "name": author_info.get("display_name"),
                "id": author_info.get("id"),
                "orcid": author_info.get("orcid")
            })
    
    return {
        "openalex_id": work.get("id"),
        "doi": doi,
        "pmid": pmid,
        "title": work.get("title"),
        "publication_year": work.get("publication_year"),
        "publication_date": work.get("publication_date"),
        "type": work.get("type"),
        "authors": authors,
        "journal": work.get("primary_location", {}).get("source", {}).get("display_name") if work.get("primary_location") else None,
        "cited_by_count": work.get("cited_by_count"),
        "is_open_access": work.get("open_access", {}).get("is_oa", False),
        # Raw abstract fields for extraction
        "abstract": work.get("abstract"),  # pyalex decodes inverted index
        "abstract_inverted_index": work.get("abstract_inverted_index"),
    }

