"""
Quick test script for PubMed fallback.
Run with: python test_pubmed.py
"""

from abstract_extractor import (
    set_entrez_email,
    clean_pmid,
    clean_doi,
    search_pubmed_by_pmid,
    search_pubmed_by_doi,
    search_pubmed_by_title,
)

# Set your email first!
EMAIL = "your@email.com"  # <-- CHANGE THIS

def test_clean_pmid():
    """Test PMID cleaning."""
    print("\n=== Testing PMID cleaning ===")
    
    test_cases = [
        "12345678",
        "https://pubmed.ncbi.nlm.nih.gov/12345678",
        "https://pubmed.ncbi.nlm.nih.gov/12345678/",
        "pmid:12345678",
        None,
        "",
    ]
    
    for pmid in test_cases:
        result = clean_pmid(pmid)
        print(f"  {repr(pmid):50} -> {repr(result)}")


def test_clean_doi():
    """Test DOI cleaning."""
    print("\n=== Testing DOI cleaning ===")
    
    test_cases = [
        "10.1038/nature12373",
        "https://doi.org/10.1038/nature12373",
        "http://doi.org/10.1038/nature12373",
        None,
        "",
    ]
    
    for doi in test_cases:
        result = clean_doi(doi)
        print(f"  {repr(doi):50} -> {repr(result)}")


def test_pubmed_by_pmid():
    """Test fetching by PMID."""
    print("\n=== Testing PubMed fetch by PMID ===")
    
    # A known PMID (famous CRISPR paper)
    pmid = "23287718"
    print(f"  Fetching PMID: {pmid}")
    
    abstract = search_pubmed_by_pmid(pmid)
    if abstract:
        print(f"  ✓ Got abstract ({len(abstract)} chars)")
        print(f"  Preview: {abstract[:150]}...")
    else:
        print(f"  ✗ No abstract returned")


def test_pubmed_by_doi():
    """Test fetching by DOI."""
    print("\n=== Testing PubMed fetch by DOI ===")
    
    # Same CRISPR paper DOI
    doi = "10.1126/science.1231143"
    print(f"  Searching DOI: {doi}")
    
    abstract = search_pubmed_by_doi(doi)
    if abstract:
        print(f"  ✓ Got abstract ({len(abstract)} chars)")
        print(f"  Preview: {abstract[:150]}...")
    else:
        print(f"  ✗ No abstract returned")


def test_pubmed_by_title():
    """Test fetching by title."""
    print("\n=== Testing PubMed fetch by Title ===")
    
    # Title of a well-known paper
    title = "Multiplex genome engineering using CRISPR/Cas systems"
    print(f"  Searching title: {title[:50]}...")
    
    abstract = search_pubmed_by_title(title)
    if abstract:
        print(f"  ✓ Got abstract ({len(abstract)} chars)")
        print(f"  Preview: {abstract[:150]}...")
    else:
        print(f"  ✗ No abstract returned (may have multiple matches)")


if __name__ == "__main__":
    print(f"Setting Entrez email to: {EMAIL}")
    if EMAIL == "your@email.com":
        print("⚠️  WARNING: Change EMAIL variable to your actual email!")
    
    set_entrez_email(EMAIL)
    
    # Run tests
    test_clean_pmid()
    test_clean_doi()
    test_pubmed_by_pmid()
    test_pubmed_by_doi()
    test_pubmed_by_title()
    
    print("\n✓ Tests complete!")

