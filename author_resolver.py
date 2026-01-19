"""
Author Resolver Module

Resolves author input (name, ORCID, or OpenAlex ID) to a canonical OpenAlex Author ID.
"""

import re
from pyalex import Authors


def is_openalex_id(identifier: str) -> bool:
    """Check if identifier is an OpenAlex Author ID (e.g., A5023888391)."""
    return bool(re.match(r'^A\d+$', identifier.strip()))


def is_orcid(identifier: str) -> bool:
    """Check if identifier is an ORCID (e.g., 0000-0002-1825-0097)."""
    # ORCID format: 4 groups of 4 digits/X separated by dashes
    return bool(re.match(r'^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$', identifier.strip()))


def resolve_by_openalex_id(author_id: str) -> dict | None:
    """Fetch author by OpenAlex ID."""
    try:
        author = Authors()[author_id]
        return author
    except Exception:
        return None


def resolve_by_orcid(orcid: str) -> dict | None:
    """Fetch author by ORCID."""
    try:
        results = list(Authors().filter(orcid=orcid).get())
        if results:
            return results[0]
        return None
    except Exception:
        return None


def resolve_by_name(name: str, affiliation_hint: str = None) -> list[dict]:
    """
    Search for author by name. Returns list of candidates.
    
    Args:
        name: Author name to search
        affiliation_hint: Optional affiliation to help disambiguate
    
    Returns:
        List of matching author records, sorted by relevance/works_count
    """
    try:
        # Use .search() for full-text search on author names
        query = Authors().search(name)
        
        # Get top candidates (limit to avoid too many results)
        candidates = list(query.get(per_page=10))
        
        # If affiliation hint provided, try to prioritize matches
        if affiliation_hint and candidates:
            affiliation_lower = affiliation_hint.lower()
            
            def has_affiliation_match(author: dict) -> bool:
                affiliations = author.get("affiliations", [])
                for aff in affiliations:
                    inst = aff.get("institution", {})
                    inst_name = inst.get("display_name", "").lower()
                    if affiliation_lower in inst_name:
                        return True
                return False
            
            # Sort: matching affiliation first, then by works_count
            candidates.sort(
                key=lambda a: (not has_affiliation_match(a), -a.get("works_count", 0))
            )
        else:
            # Sort by works_count (most prolific first)
            candidates.sort(key=lambda a: -a.get("works_count", 0))
        
        return candidates
    except Exception:
        return []


def resolve_author(identifier: str, affiliation_hint: str = None) -> dict:
    """
    Main resolver function. Takes any identifier type and returns author record.
    
    Args:
        identifier: OpenAlex ID, ORCID, or author name
        affiliation_hint: Optional affiliation to help disambiguate name searches
    
    Returns:
        Author record dict with 'id', 'display_name', 'works_count', etc.
    
    Raises:
        ValueError: If author cannot be found or identifier is ambiguous
    """
    identifier = identifier.strip()
    
    # Try OpenAlex ID
    if is_openalex_id(identifier):
        author = resolve_by_openalex_id(identifier)
        if author:
            return author
        raise ValueError(f"OpenAlex author ID not found: {identifier}")
    
    # Try ORCID
    if is_orcid(identifier):
        author = resolve_by_orcid(identifier)
        if author:
            return author
        raise ValueError(f"ORCID not found in OpenAlex: {identifier}")
    
    # Try name search
    candidates = resolve_by_name(identifier, affiliation_hint)
    
    if not candidates:
        raise ValueError(f"No authors found matching: {identifier}")
    
    if len(candidates) == 1:
        return candidates[0]
    
    # Multiple candidates - return top match but warn
    # In a real application, you might want to prompt for disambiguation
    top_candidate = candidates[0]
    print(f"⚠️  Multiple authors found for '{identifier}'. Using top match:")
    print(f"   {top_candidate.get('display_name')} ({top_candidate.get('id')})")
    print(f"   Works: {top_candidate.get('works_count')}, Citations: {top_candidate.get('cited_by_count')}")
    
    return top_candidate


def list_candidates(name: str, affiliation_hint: str = None) -> list[dict]:
    """
    List all candidate authors for a name search (for disambiguation UI).
    
    Returns simplified records with key info for selection.
    """
    candidates = resolve_by_name(name, affiliation_hint)
    
    return [
        {
            "id": c.get("id"),
            "display_name": c.get("display_name"),
            "works_count": c.get("works_count"),
            "cited_by_count": c.get("cited_by_count"),
            "affiliations": [
                aff.get("institution", {}).get("display_name")
                for aff in c.get("affiliations", [])[:3]  # Top 3 affiliations
            ],
            "orcid": c.get("orcid")
        }
        for c in candidates
    ]

