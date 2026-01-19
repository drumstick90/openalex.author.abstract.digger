"""
Author Abstract Digger - Main Orchestrator

Retrieves all works for a given author and extracts abstracts from
OpenAlex (with PubMed fallback).
"""

import json
import argparse
from pathlib import Path
from datetime import datetime
from tqdm import tqdm

import pyalex

from author_resolver import resolve_author, list_candidates
from works_fetcher import fetch_works_paginated, get_works_count, extract_work_metadata
from abstract_extractor import extract_abstract, set_entrez_email


def configure_apis(email: str):
    """Configure API access with email for polite pools."""
    pyalex.config.email = email
    set_entrez_email(email)
    print(f"✓ Configured APIs with email: {email}")


def fetch_author_abstracts(
    author_input: str,
    email: str,
    output_file: str = None,
    year_from: int = None,
    year_to: int = None,
    skip_pubmed: bool = False,
    affiliation_hint: str = None
) -> list[dict]:
    """
    Main entry point: fetch all works and abstracts for an author.
    
    Args:
        author_input: Author identifier (OpenAlex ID, ORCID, or name)
        email: Your email for API access
        output_file: Optional path to save JSONL output
        year_from: Optional filter - minimum publication year
        year_to: Optional filter - maximum publication year
        skip_pubmed: If True, don't fallback to PubMed
        affiliation_hint: Optional affiliation to help disambiguate name
    
    Returns:
        List of work records with abstracts
    """
    # Configure APIs
    configure_apis(email)
    
    # 1. Resolve author
    print(f"\n🔍 Resolving author: {author_input}")
    author = resolve_author(author_input, affiliation_hint)
    
    author_id = author.get("id")
    author_name = author.get("display_name")
    works_count = author.get("works_count", 0)
    
    print(f"✓ Found: {author_name}")
    print(f"  OpenAlex ID: {author_id}")
    print(f"  Total works: {works_count}")
    
    # 2. Fetch all works
    print(f"\n📚 Fetching works...")
    
    results = []
    stats = {
        "total": 0,
        "abstract_openalex": 0,
        "abstract_pubmed": 0,
        "no_abstract": 0
    }
    
    # Process works with progress bar
    for work in tqdm(
        fetch_works_paginated(
            author_id=author_id,
            year_from=year_from,
            year_to=year_to,
            show_progress=False  # We use our own progress bar
        ),
        total=works_count,
        desc="Processing"
    ):
        stats["total"] += 1
        
        # Extract metadata
        record = extract_work_metadata(work)
        
        # Extract abstract (with optional PubMed fallback)
        abstract_result = extract_abstract(
            work,
            fallback_to_pubmed=not skip_pubmed
        )
        
        record["abstract"] = abstract_result["abstract"]
        record["abstract_source"] = abstract_result["source"]
        
        # Update stats
        if abstract_result["source"] == "openalex":
            stats["abstract_openalex"] += 1
        elif abstract_result["source"] and abstract_result["source"].startswith("pubmed"):
            stats["abstract_pubmed"] += 1
        else:
            stats["no_abstract"] += 1
        
        # Add metadata
        record["fetched_at"] = datetime.utcnow().isoformat()
        record["author_queried"] = author_id
        
        results.append(record)
        
        # Stream to file if specified
        if output_file:
            with open(output_file, "a") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    
    # Print summary
    print(f"\n📊 Summary:")
    print(f"  Total works processed: {stats['total']}")
    print(f"  Abstracts from OpenAlex: {stats['abstract_openalex']}")
    print(f"  Abstracts from PubMed: {stats['abstract_pubmed']}")
    print(f"  No abstract found: {stats['no_abstract']}")
    
    if output_file:
        print(f"\n💾 Results saved to: {output_file}")
    
    return results


def interactive_disambiguate(name: str) -> str:
    """Interactive author disambiguation."""
    print(f"\n🔍 Searching for: {name}")
    candidates = list_candidates(name)
    
    if not candidates:
        raise ValueError(f"No authors found for: {name}")
    
    if len(candidates) == 1:
        return candidates[0]["id"]
    
    print(f"\nFound {len(candidates)} candidates:\n")
    for i, c in enumerate(candidates, 1):
        affs = ", ".join(filter(None, c["affiliations"][:2])) or "No affiliation"
        print(f"  [{i}] {c['display_name']}")
        print(f"      Works: {c['works_count']}, Citations: {c['cited_by_count']}")
        print(f"      {affs}")
        if c["orcid"]:
            print(f"      ORCID: {c['orcid']}")
        print()
    
    while True:
        try:
            choice = input("Select author (number): ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(candidates):
                return candidates[idx]["id"]
        except (ValueError, KeyboardInterrupt):
            pass
        print("Invalid selection, try again.")


def main():
    parser = argparse.ArgumentParser(
        description="Fetch all works and abstracts for an author from OpenAlex",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --email you@example.com --author "A5023888391"
  %(prog)s --email you@example.com --author "0000-0002-1825-0097"
  %(prog)s --email you@example.com --author "Jane Doe" --affiliation "Harvard"
  %(prog)s --email you@example.com --author "Jane Doe" --year-from 2020 --output results.jsonl
        """
    )
    
    parser.add_argument(
        "--author", "-a",
        required=True,
        help="Author identifier: OpenAlex ID, ORCID, or name"
    )
    parser.add_argument(
        "--email", "-e",
        required=True,
        help="Your email (required for API polite pool access)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output file path (JSONL format)"
    )
    parser.add_argument(
        "--year-from",
        type=int,
        help="Filter: minimum publication year"
    )
    parser.add_argument(
        "--year-to",
        type=int,
        help="Filter: maximum publication year"
    )
    parser.add_argument(
        "--affiliation",
        help="Affiliation hint to help disambiguate author name"
    )
    parser.add_argument(
        "--skip-pubmed",
        action="store_true",
        help="Skip PubMed fallback (only use OpenAlex)"
    )
    parser.add_argument(
        "--interactive", "-i",
        action="store_true",
        help="Interactive mode for author disambiguation"
    )
    
    args = parser.parse_args()
    
    # Handle interactive disambiguation
    author_input = args.author
    if args.interactive and not (
        author_input.startswith("A") or  # OpenAlex ID
        "-" in author_input  # ORCID
    ):
        configure_apis(args.email)
        author_input = interactive_disambiguate(args.author)
    
    # Prepare output file
    output_file = args.output
    if output_file:
        # Clear existing file
        Path(output_file).write_text("")
    
    # Run main fetch
    results = fetch_author_abstracts(
        author_input=author_input,
        email=args.email,
        output_file=output_file,
        year_from=args.year_from,
        year_to=args.year_to,
        skip_pubmed=args.skip_pubmed,
        affiliation_hint=args.affiliation
    )
    
    # If no output file, print sample
    if not output_file and results:
        print("\n📄 Sample record:")
        sample = results[0]
        for key in ["openalex_id", "title", "doi", "abstract_source"]:
            print(f"  {key}: {sample.get(key)}")
        if sample.get("abstract"):
            abstract_preview = sample["abstract"][:200] + "..." if len(sample.get("abstract", "")) > 200 else sample.get("abstract")
            print(f"  abstract: {abstract_preview}")


if __name__ == "__main__":
    main()

