# Author Works & Abstracts Fetcher

A Python tool using **pyalex** to retrieve all works for a given author, extract abstracts from OpenAlex (handling the inverted index format), and fallback to PubMed when abstracts are missing.

---

## 🎯 Goal

Given an author identifier, retrieve:
1. **All works** associated with that author from OpenAlex
2. **All abstracts** — first from OpenAlex, then from PubMed as fallback
3. Output clean, ready-to-index data for future RAG search

---

## 📥 Inputs

| Input | Type | Description |
|-------|------|-------------|
| Author ID | `str` | OpenAlex ID (e.g., `A5023888391`), ORCID, or author name |
| Email | `str` | Required for polite API access (OpenAlex & NCBI) |
| Date range | `tuple` | Optional: filter works by publication year |
| Work types | `list` | Optional: filter by type (article, book, dataset, etc.) |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│   │   Author     │───▶│   Works      │───▶│  Abstract    │     │
│   │   Resolver   │    │   Fetcher    │    │  Extractor   │     │
│   └──────────────┘    └──────────────┘    └──────┬───────┘     │
│                                                  │              │
│                              ┌───────────────────┴────────┐     │
│                              ▼                            ▼     │
│                     ┌──────────────┐            ┌──────────────┐│
│                     │  OpenAlex    │            │   PubMed     ││
│                     │  Abstract    │            │   Fallback   ││
│                     └──────────────┘            └──────────────┘│
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🔧 Modules

### 1. `author_resolver.py`
Resolve author input to a canonical OpenAlex Author ID.

**Functions:**
- `resolve_author(identifier: str) -> str`
  - If OpenAlex ID format → validate and return
  - If ORCID → query `Authors().filter(orcid=...)`
  - If name → search `Authors().search(name)` and disambiguate

**Disambiguation hints:**
- Use affiliation if provided
- Use ORCID if known
- Return top match or raise ambiguity error

---

### 2. `works_fetcher.py`
Fetch all works for a given author from OpenAlex.

**Functions:**
- `fetch_all_works(author_id: str, filters: dict = None) -> list[Work]`

**Key implementation details:**
```python
from pyalex import Works

works = Works().filter(author={"id": author_id})

# Use cursor pagination to get ALL works (not just first page)
all_works = []
for page in works.paginate(per_page=200):
    all_works.extend(page)
```

**Important:** Always use `.paginate()` — authors can have hundreds/thousands of works.

---

### 3. `abstract_extractor.py`
Extract abstracts, prioritizing OpenAlex, falling back to PubMed.

#### 3.1 OpenAlex Abstract Extraction

OpenAlex stores abstracts as **inverted indices** (word → positions mapping) for legal/compression reasons.

**Example of inverted index:**
```json
{
  "abstract_inverted_index": {
    "This": [0],
    "is": [1, 4],
    "a": [2],
    "study": [3],
    "important": [5]
  }
}
```
Reconstructs to: `"This is a study is important"`

**pyalex handles this automatically** — just access the abstract directly:
```python
work = Works()["W2741809807"]
abstract_text = work.get("abstract")  # pyalex converts it for you
```

Or manually decode if needed:
```python
def decode_inverted_abstract(inverted_index: dict) -> str:
    if not inverted_index:
        return None
    
    # Build position → word mapping
    position_word = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            position_word[pos] = word
    
    # Reconstruct in order
    return " ".join(position_word[i] for i in sorted(position_word.keys()))
```

#### 3.2 PubMed Fallback

When OpenAlex abstract is missing, try these strategies **in order**:

1. **By PMID** — Check if work has `ids.pmid` field (fastest, most reliable)
2. **By DOI** — Query PubMed using DOI if available
3. **By Title** — Search PubMed by title (last resort, may have false matches)

```python
from metapub import PubMedFetcher

fetcher = PubMedFetcher()

def fetch_pubmed_abstract(pmid: str = None, doi: str = None, title: str = None) -> str | None:
    """
    Try to fetch abstract from PubMed using available identifiers.
    Priority: PMID > DOI > Title
    """
    
    # 1. Try PMID first (most reliable)
    if pmid:
        try:
            article = fetcher.article_by_pmid(pmid)
            if article and article.abstract:
                return article.abstract
        except Exception:
            pass
    
    # 2. Try DOI
    if doi:
        try:
            article = fetcher.article_by_doi(doi)
            if article and article.abstract:
                return article.abstract
        except Exception:
            pass
    
    # 3. Try title search (last resort)
    if title:
        try:
            # Search by title - be careful of false positives
            pmids = fetcher.pmids_for_query(f'"{title}"[Title]')
            if pmids and len(pmids) == 1:  # Only use if exactly one match
                article = fetcher.article_by_pmid(pmids[0])
                if article and article.abstract:
                    return article.abstract
        except Exception:
            pass
    
    return None
```

**Alternative: Direct E-utilities**
```python
from Bio import Entrez

Entrez.email = "your@email.com"

def search_pubmed(doi: str = None, title: str = None) -> str | None:
    """Search PubMed by DOI or title, return PMID if found."""
    
    if doi:
        handle = Entrez.esearch(db="pubmed", term=f"{doi}[DOI]")
        record = Entrez.read(handle)
        if record["IdList"]:
            return record["IdList"][0]
    
    if title:
        # Exact title search
        handle = Entrez.esearch(db="pubmed", term=f'"{title}"[Title]')
        record = Entrez.read(handle)
        if record["IdList"] and len(record["IdList"]) == 1:
            return record["IdList"][0]
    
    return None

def fetch_abstract_by_pmid(pmid: str) -> str | None:
    """Fetch abstract text given a PMID."""
    handle = Entrez.efetch(db="pubmed", id=pmid, rettype="abstract", retmode="text")
    return handle.read().strip() or None
```

---

### 4. `orchestrator.py`
Main workflow coordinator.

```python
def fetch_author_abstracts(author_input: str, email: str) -> list[dict]:
    """
    Main entry point.
    
    Returns list of work records with abstracts.
    """
    # 1. Resolve author
    author_id = resolve_author(author_input)
    
    # 2. Fetch all works
    works = fetch_all_works(author_id)
    
    # 3. Extract abstracts
    results = []
    missing_abstracts = []
    
    for work in works:
        record = {
            "openalex_id": work["id"],
            "doi": work.get("doi"),
            "pmid": work.get("ids", {}).get("pmid"),
            "title": work.get("title"),
            "publication_year": work.get("publication_year"),
            "authors": [a["author"]["display_name"] for a in work.get("authorships", [])],
            "abstract": None,
            "abstract_source": None
        }
        
        # Try OpenAlex first
        abstract = work.get("abstract")  # pyalex decodes inverted index
        if abstract:
            record["abstract"] = abstract
            record["abstract_source"] = "openalex"
        else:
            # Try PubMed fallback
            abstract = fetch_from_pubmed(
                pmid=record["pmid"],
                doi=record["doi"]
            )
            if abstract:
                record["abstract"] = abstract
                record["abstract_source"] = "pubmed"
            else:
                missing_abstracts.append(record["openalex_id"])
        
        results.append(record)
    
    # Log missing
    if missing_abstracts:
        logger.warning(f"No abstract found for {len(missing_abstracts)} works")
    
    return results
```

---

## 📤 Output Format

Each work record (JSON/dict):

```json
{
  "openalex_id": "W2741809807",
  "doi": "https://doi.org/10.1234/example",
  "pmid": "12345678",
  "title": "A groundbreaking study on...",
  "publication_year": 2023,
  "authors": ["Jane Doe", "John Smith"],
  "abstract": "This study investigates...",
  "abstract_source": "openalex"  // or "pubmed" or null
}
```

Save as **JSONL** (one JSON object per line) for easy streaming/indexing:
```
{"openalex_id": "W123...", "title": "...", ...}
{"openalex_id": "W456...", "title": "...", ...}
```

---

## ⚠️ Important Considerations

### Rate Limits & Polite Access

| API | Limit | Best Practice |
|-----|-------|---------------|
| OpenAlex | ~10 req/sec (polite pool) | Set email in pyalex config |
| PubMed/NCBI | 3 req/sec (10 with API key) | Use `Entrez.email`, batch requests |

```python
import pyalex
pyalex.config.email = "your@email.com"  # Gets you into polite pool
```

### Coverage Gaps

- **OpenAlex**: Wide coverage but abstracts often missing or inverted-only
- **PubMed**: Only biomedical/life sciences — non-medical works won't be there
- **Some works will have NO abstract** in either source — track these

### Error Handling

- Network failures → retry with exponential backoff
- Rate limiting → sleep and retry
- Author disambiguation → log ambiguous cases
- Missing PMIDs → try DOI-to-PMID mapping

---

## 📦 Dependencies

**Requires Python 3.11+**

```
pyalex>=0.13
biopython>=1.81  # for Entrez (PubMed fallback)
requests>=2.28
tqdm>=4.64
```

---

## 🔮 Future: RAG Indexing Prep

This tool outputs clean abstracts ready for:
- **Text embedding** (OpenAI, sentence-transformers, etc.)
- **Vector DB ingestion** (Pinecone, Chroma, Weaviate, etc.)
- **Chunking** if abstracts are long (though most are <500 words)

Metadata to preserve for RAG filtering:
- `publication_year` — temporal filtering
- `doi` — deduplication & citation
- `authors` — author-based retrieval
- `title` — semantic search fallback

---

## 🚀 Quick Start Pseudocode

```python
from author_resolver import resolve_author
from works_fetcher import fetch_all_works
from abstract_extractor import extract_abstract
from pubmed_fallback import fetch_pubmed_abstract

def main(author_input: str):
    # Setup
    pyalex.config.email = "you@example.com"
    
    # Resolve
    author_id = resolve_author(author_input)
    print(f"Found author: {author_id}")
    
    # Fetch works
    works = fetch_all_works(author_id)
    print(f"Found {len(works)} works")
    
    # Get abstracts
    for work in tqdm(works):
        abstract = extract_abstract(work)
        if not abstract:
            abstract = fetch_pubmed_abstract(work)
        
        yield {
            "id": work["id"],
            "title": work["title"],
            "abstract": abstract,
            "source": "openalex" if work.get("abstract") else "pubmed"
        }

if __name__ == "__main__":
    results = list(main("A5023888391"))  # or ORCID or name
    
    # Save
    with open("abstracts.jsonl", "w") as f:
        for r in results:
            f.write(json.dumps(r) + "\n")
```

---

## 📋 Summary Checklist

- [ ] Author resolution (ID, ORCID, or name → OpenAlex Author ID)
- [ ] Paginated works fetching (handle 1000s of works)
- [ ] OpenAlex abstract extraction (handle inverted index)
- [ ] PubMed fallback (via PMID or DOI lookup)
- [ ] Clean output format (JSONL with metadata)
- [ ] Rate limit compliance (email for polite pool)
- [ ] Error handling & logging
- [ ] Progress tracking for large authors

