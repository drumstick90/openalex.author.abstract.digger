"""
Abstract Extractor Module

Extracts abstracts from OpenAlex (handling inverted index format)
and falls back to PubMed when abstracts are missing.
"""

import logging
import re
import ssl
import time
from typing import Optional
from Bio import Entrez

# Setup logging
logger = logging.getLogger(__name__)


# Fix SSL certificate issues (common on macOS)
# This creates an unverified context for HTTPS requests
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context


# Configuration - set your email for NCBI
Entrez.email = None  # Will be set by user


def set_entrez_email(email: str):
    """Set email for NCBI Entrez API (required for polite access)."""
    Entrez.email = email


def decode_inverted_abstract(inverted_index: dict) -> Optional[str]:
    """
    Decode OpenAlex inverted abstract index to plain text.
    
    OpenAlex stores abstracts as word -> [positions] mapping.
    Example: {"This": [0], "is": [1, 4], "a": [2], "study": [3]}
    Becomes: "This is a study is"
    
    Note: pyalex usually does this automatically, but this is a fallback.
    """
    if not inverted_index:
        return None
    
    # Build position -> word mapping
    position_word = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_word[pos] = word
    
    if not position_word:
        return None
    
    # Reconstruct in order
    max_pos = max(position_word.keys())
    words = [position_word.get(i, "") for i in range(max_pos + 1)]
    
    return " ".join(words).strip()


def extract_openalex_abstract(work: dict) -> Optional[str]:
    """
    Extract abstract from an OpenAlex work record.
    
    Tries:
    1. Direct 'abstract' field (pyalex usually populates this)
    2. Decode 'abstract_inverted_index' manually
    """
    # Try direct abstract field first (pyalex decodes it)
    abstract = work.get("abstract")
    if abstract and isinstance(abstract, str) and abstract.strip():
        return abstract.strip()
    
    # Fallback: decode inverted index manually
    inverted = work.get("abstract_inverted_index")
    if inverted:
        return decode_inverted_abstract(inverted)
    
    return None


def clean_pmid(pmid: str) -> Optional[str]:
    """
    Clean PMID to just the numeric ID.
    
    Handles formats:
    - "12345678"
    - "https://pubmed.ncbi.nlm.nih.gov/12345678"
    - "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    - "pmid:12345678"
    """
    if not pmid:
        return None
    
    pmid = str(pmid).strip()
    
    # Extract just digits if it's a URL or has prefix
    match = re.search(r'(\d{6,9})', pmid)
    if match:
        return match.group(1)
    
    return None


def clean_doi(doi: str) -> Optional[str]:
    """
    Clean DOI to just the identifier (without URL prefix).
    
    Handles formats:
    - "10.1234/example"
    - "https://doi.org/10.1234/example"
    - "http://doi.org/10.1234/example"
    """
    if not doi:
        return None
    
    doi = str(doi).strip()
    
    # Remove URL prefixes
    if doi.startswith("https://doi.org/"):
        doi = doi[16:]
    elif doi.startswith("http://doi.org/"):
        doi = doi[15:]
    elif doi.startswith("doi.org/"):
        doi = doi[8:]
    
    return doi if doi else None


def search_pubmed_by_pmid(pmid: str) -> Optional[str]:
    """Fetch abstract from PubMed using PMID."""
    pmid = clean_pmid(pmid)
    if not pmid:
        return None
    
    try:
        handle = Entrez.efetch(
            db="pubmed",
            id=pmid,
            rettype="xml",
            retmode="xml"
        )
        records = Entrez.read(handle)
        handle.close()
        
        # Navigate XML structure to get abstract
        # records is a dict-like object with 'PubmedArticle' key
        pubmed_articles = records.get("PubmedArticle", [])
        if not pubmed_articles:
            return None
        
        article = pubmed_articles[0]
        medline = article.get("MedlineCitation", {})
        article_data = medline.get("Article", {})
        abstract_data = article_data.get("Abstract", {})
        abstract_texts = abstract_data.get("AbstractText", [])
        
        if not abstract_texts:
            return None
        
        # Join multiple sections (some abstracts have labeled sections)
        if isinstance(abstract_texts, list):
            parts = []
            for t in abstract_texts:
                # Handle StringElement with attributes (labeled sections)
                text = str(t).strip()
                if text:
                    parts.append(text)
            return " ".join(parts) if parts else None
        
        return str(abstract_texts).strip() or None
        
    except Exception as e:
        print(f"⚠️  PubMed fetch failed for PMID {pmid}: {e}")
        return None


def search_pubmed_by_doi(doi: str) -> Optional[str]:
    """Search PubMed by DOI and fetch abstract."""
    doi = clean_doi(doi)
    if not doi:
        return None
    
    try:
        # Search for PMID using DOI
        handle = Entrez.esearch(db="pubmed", term=f"{doi}[DOI]")
        record = Entrez.read(handle)
        handle.close()
        
        id_list = record.get("IdList", [])
        if id_list:
            pmid = id_list[0]
            time.sleep(0.34)  # Rate limit: 3 requests/sec
            return search_pubmed_by_pmid(pmid)
        
        return None
    except Exception as e:
        print(f"⚠️  PubMed DOI search failed for {doi}: {e}")
        return None


def search_pubmed_by_title(title: str) -> Optional[str]:
    """
    Search PubMed by title and fetch abstract.
    
    Only returns result if exactly ONE match found (to avoid false positives).
    """
    if not title:
        return None
    
    # Clean title for search - escape special chars, remove brackets
    title_clean = title.strip()
    title_clean = re.sub(r'[\[\]{}()]', '', title_clean)  # Remove brackets
    title_clean = title_clean.replace('"', "'")  # Replace quotes
    title_clean = title_clean[:200]  # Truncate very long titles
    
    if len(title_clean) < 10:  # Title too short, skip
        return None
    
    try:
        # Search with title match
        handle = Entrez.esearch(
            db="pubmed",
            term=f'"{title_clean}"[Title]',
            retmax=5  # Get a few to check for uniqueness
        )
        record = Entrez.read(handle)
        handle.close()
        
        id_list = record.get("IdList", [])
        
        # Only proceed if exactly one match (avoid false positives)
        if len(id_list) == 1:
            pmid = id_list[0]
            time.sleep(0.34)  # Rate limit
            return search_pubmed_by_pmid(pmid)
        
        return None
    except Exception as e:
        print(f"⚠️  PubMed title search failed: {e}")
        return None


def fetch_pubmed_abstract(
    pmid: str = None,
    doi: str = None,
    title: str = None
) -> tuple[Optional[str], Optional[str]]:
    """
    Fetch abstract from PubMed using available identifiers.
    
    Tries in order: PMID -> DOI -> Title
    
    Args:
        pmid: PubMed ID
        doi: Digital Object Identifier
        title: Work title (last resort)
    
    Returns:
        Tuple of (abstract_text, method_used)
        method_used is one of: "pmid", "doi", "title", or None if not found
    """
    logger.debug(f"🔍 PubMed fallback: pmid={pmid}, doi={doi}, title={title[:30] if title else None}...")
    
    # 1. Try PMID (most reliable)
    if pmid:
        logger.debug(f"  Trying PMID: {pmid}")
        abstract = search_pubmed_by_pmid(pmid)
        if abstract:
            logger.debug(f"  ✓ Found via PMID ({len(abstract)} chars)")
            return abstract, "pmid"
        time.sleep(0.34)  # Rate limit between attempts
    
    # 2. Try DOI
    if doi:
        logger.debug(f"  Trying DOI: {doi}")
        abstract = search_pubmed_by_doi(doi)
        if abstract:
            logger.debug(f"  ✓ Found via DOI ({len(abstract)} chars)")
            return abstract, "doi"
        time.sleep(0.34)
    
    # 3. Try title (last resort)
    if title:
        logger.debug(f"  Trying title search...")
        abstract = search_pubmed_by_title(title)
        if abstract:
            logger.debug(f"  ✓ Found via title ({len(abstract)} chars)")
            return abstract, "title"
    
    logger.debug(f"  ✗ No PubMed abstract found")
    return None, None


def extract_abstract(
    work: dict,
    fallback_to_pubmed: bool = True
) -> dict:
    """
    Main function to extract abstract from a work record.
    
    Tries OpenAlex first, then falls back to PubMed if enabled.
    
    Args:
        work: Work record dict (from works_fetcher)
        fallback_to_pubmed: Whether to try PubMed if OpenAlex fails
    
    Returns:
        Dict with keys:
        - abstract: The abstract text (or None)
        - source: Where abstract came from ("openalex", "pubmed_pmid", 
                  "pubmed_doi", "pubmed_title", or None)
    """
    # Try OpenAlex first
    abstract = extract_openalex_abstract(work)
    if abstract:
        return {"abstract": abstract, "source": "openalex"}
    
    # Fallback to PubMed
    if fallback_to_pubmed:
        # Try multiple places where PMID might be stored
        pmid = (
            work.get("pmid") or 
            work.get("ids", {}).get("pmid") or
            work.get("ids", {}).get("pmid_url")
        )
        doi = work.get("doi") or work.get("ids", {}).get("doi")
        title = work.get("title")
        
        abstract, method = fetch_pubmed_abstract(pmid, doi, title)
        if abstract:
            return {"abstract": abstract, "source": f"pubmed_{method}"}
    
    return {"abstract": None, "source": None}
