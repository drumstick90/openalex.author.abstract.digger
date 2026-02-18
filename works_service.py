"""
Works Service

Orchestrates author works fetching, abstract extraction, and funding
aggregation. Returns plain dicts — no Flask coupling — so it can be
used by both the web API (app.py) and the CLI (main.py).
"""

import logging
from typing import Callable, Optional

from abstract_extractor import extract_abstract
from works_fetcher import fetch_works_paginated

logger = logging.getLogger(__name__)


def process_author_works(
    author: dict,
    pubmed_fallback: bool = False,
    progress_callback: Optional[Callable] = None,
) -> dict:
    """
    Fetch all works for an author, extract abstracts, and aggregate funding.

    Args:
        author: Author dict from OpenAlex.
        pubmed_fallback: Try PubMed for missing abstracts (slow, ~0.3 s/work).
        progress_callback: Optional fn(message, pct, phase, total=None).

    Returns:
        Dict with keys: author, works, total_works, abstract_stats, funding.
    """
    def emit(msg: str, pct: float, phase: str = None, total: int = None):
        if progress_callback:
            progress_callback(msg, pct, phase, total)

    author_id_full = author.get('id', '')
    author_id_short = author_id_full.replace('https://openalex.org/', '')
    author_name = author.get('display_name', author_id_short)

    # --- Fetch phase ---
    logger.info(f"🔄 Fetching all works for {author_id_short}...")
    emit(f'🔄 Fetching works for {author_name}...', 5, 'fetching_works')

    all_works = list(fetch_works_paginated(author_id_short, show_progress=False))

    logger.info(f"✓ Total works fetched: {len(all_works)}")
    emit(f'✓ Total works fetched: {len(all_works)}', 15, 'processing', total=len(all_works))

    if pubmed_fallback:
        msg = '⚠️ PubMed fallback enabled - this may take a while...'
        logger.info(msg)
        emit(msg, 15, 'processing')

    # --- Process phase ---
    results = []
    stats = {'openalex': 0, 'pubmed': 0, 'none': 0}
    funders: dict = {}
    total_grants_found = 0
    total = len(all_works)

    for i, work in enumerate(all_works):
        work_id = work.get('id', '').replace('https://openalex.org/', '')
        work_title = work.get('title') or 'Untitled'
        title_short = (work_title[:50] + '...') if len(work_title) > 50 else work_title

        progress_pct = 15 + (i / total * 80) if total > 0 else 15
        msg = f'📝 Processing work {i + 1}/{total}: {title_short}'

        if (i + 1) % 10 == 0 or i == 0 or (i + 1) == total:
            logger.info(msg)
        emit(msg, progress_pct, 'processing')

        # Abstract extraction
        abstract_result = extract_abstract(work, fallback_to_pubmed=pubmed_fallback)
        abstract = abstract_result.get('abstract')
        abstract_source = abstract_result.get('source')

        if abstract_source == 'openalex':
            stats['openalex'] += 1
        elif abstract_source and abstract_source.startswith('pubmed'):
            stats['pubmed'] += 1
            logger.debug(f'📚 PubMed fallback success for: {title_short}')
        else:
            stats['none'] += 1

        # Funding aggregation
        for grant in work.get('grants', []):
            total_grants_found += 1
            funder_name = grant.get('funder_display_name') or grant.get('funder', 'Unknown Funder')
            funder_id = grant.get('funder')
            award_id = grant.get('award_id')

            if funder_name not in funders:
                funders[funder_name] = {
                    'funder_id': funder_id,
                    'count': 0,
                    'awards': [],
                    'works': [],
                }
            funders[funder_name]['count'] += 1
            if award_id and award_id not in funders[funder_name]['awards']:
                funders[funder_name]['awards'].append(award_id)
            if work_id not in funders[funder_name]['works']:
                funders[funder_name]['works'].append(work_id)

        results.append({
            'openalex_id': work_id,
            'doi': work.get('doi'),
            'pmid': work.get('ids', {}).get('pmid'),
            'title': work.get('title'),
            'publication_year': work.get('publication_year'),
            'publication_date': work.get('publication_date'),
            'type': work.get('type'),
            'cited_by_count': work.get('cited_by_count', 0),
            'abstract': abstract,
            'abstract_source': abstract_source,
        })

    stats_msg = f"📊 Abstract stats: OpenAlex={stats['openalex']}, PubMed={stats['pubmed']}, Missing={stats['none']}"
    logger.info(stats_msg)

    if funders:
        logger.info(
            f"💰 Funding stats: {len(funders)} funders, {total_grants_found} grant mentions "
            f"across {sum(len(f['works']) for f in funders.values())} works"
        )
        for name, data in sorted(funders.items(), key=lambda x: -x[1]['count'])[:5]:
            logger.info(f"   - {name}: {data['count']} mentions, {len(data['awards'])} unique awards")
    else:
        logger.info("💰 No funding/grant data found in OpenAlex for this author's works")

    emit(stats_msg, 100, 'complete')

    funders_list = [
        {
            'name': name,
            'funder_id': data['funder_id'],
            'mention_count': data['count'],
            'unique_awards': len(data['awards']),
            'awards': data['awards'][:10],
            'works_count': len(data['works']),
        }
        for name, data in sorted(funders.items(), key=lambda x: -x[1]['count'])
    ]

    return {
        'author': {
            'id': author_id_short,
            'display_name': author.get('display_name'),
            'works_count': author.get('works_count'),
            'cited_by_count': author.get('cited_by_count'),
            'orcid': author.get('orcid'),
            'affiliations': [
                aff.get('institution', {}).get('display_name')
                for aff in author.get('affiliations', [])[:3]
            ],
        },
        'works': results,
        'total_works': len(results),
        'abstract_stats': stats,
        'funding': {
            'funders': funders_list,
            'total_mentions': total_grants_found,
            'works_with_funding': len(set(w for f in funders.values() for w in f['works'])),
        },
    }
