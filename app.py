"""
Flask backend for Author Works & Abstracts Fetcher MVP.
"""

import json
import logging
import os
import queue
import threading
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, Response

# Load environment variables from .env file
load_dotenv()
import pyalex
from author_resolver import resolve_author, list_candidates
from abstract_extractor import extract_abstract, set_entrez_email

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='static')

# Store for SSE progress streams (session_id -> queue)
progress_streams = {}

# Configure pyalex with a default email (can be overridden per request)
DEFAULT_EMAIL = "openalex-user@example.com"
pyalex.config.email = DEFAULT_EMAIL
set_entrez_email(DEFAULT_EMAIL)  # Also set for PubMed/Entrez


@app.route('/')
def index():
    """Serve the main HTML page."""
    return send_from_directory('.', 'index.html')


def send_progress(session_id: str, message: str, progress: float = None, phase: str = None, total: int = None):
    """Send a progress update to the SSE stream for a session."""
    if session_id in progress_streams:
        data = {'message': message}
        if progress is not None:
            data['progress'] = progress
        if phase:
            data['phase'] = phase
        if total is not None:
            data['total'] = total
        try:
            progress_streams[session_id].put_nowait(data)
        except queue.Full:
            pass  # Skip if queue is full


@app.route('/api/progress/<session_id>')
def progress_stream(session_id):
    """SSE endpoint for streaming progress updates."""
    def generate():
        # Create queue for this session
        q = queue.Queue(maxsize=100)
        progress_streams[session_id] = q
        
        try:
            yield f"data: {json.dumps({'message': 'Connected', 'phase': 'connected'})}\n\n"
            
            while True:
                try:
                    # Wait for message with timeout
                    data = q.get(timeout=30)
                    
                    # Check for completion signal
                    if data.get('phase') == 'complete' or data.get('phase') == 'error':
                        yield f"data: {json.dumps(data)}\n\n"
                        break
                    
                    yield f"data: {json.dumps(data)}\n\n"
                except queue.Empty:
                    # Send keepalive
                    yield f": keepalive\n\n"
        finally:
            # Cleanup
            progress_streams.pop(session_id, None)
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/api/search', methods=['POST'])
def search_author():
    """
    Search for an author and return their works with abstracts.
    
    Request body:
        - identifier: OpenAlex ID, ORCID, or author name
        - email: (optional) Email for polite API access
        - affiliation: (optional) Affiliation hint for disambiguation
        - pubmed_fallback: (optional) Enable PubMed fallback for missing abstracts (slow!)
        - session_id: (optional) Session ID for SSE progress streaming
    
    Returns:
        - If direct ID/ORCID match or single name match: author + works
        - If multiple name matches: candidates list for disambiguation
    """
    data = request.get_json() or {}
    identifier = data.get('identifier', '').strip()
    email = data.get('email', '').strip()
    affiliation = data.get('affiliation', '').strip() or None
    pubmed_fallback = data.get('pubmed_fallback', False)  # Off by default - it's SLOW
    session_id = data.get('session_id')  # For SSE progress
    
    if not identifier:
        return jsonify({'error': 'Please provide an author identifier'}), 400
    
    # Set email if provided
    if email:
        pyalex.config.email = email
        set_entrez_email(email)  # Also for PubMed if enabled
    
    # Import here to check identifier types
    from author_resolver import is_openalex_id, is_orcid, resolve_by_name
    
    if session_id:
        send_progress(session_id, '🔍 Looking up author...', 0, 'searching')
    
    # For name searches, check if disambiguation is needed
    if not is_openalex_id(identifier) and not is_orcid(identifier):
        candidates = resolve_by_name(identifier, affiliation)
        
        if not candidates:
            if session_id:
                send_progress(session_id, f'❌ No authors found matching: {identifier}', 100, 'error')
            return jsonify({'error': f'No authors found matching: {identifier}'}), 404
        
        if len(candidates) > 1:
            if session_id:
                send_progress(session_id, f'📋 Found {len(candidates)} matching authors', 100, 'complete')
            # Return candidates for disambiguation
            return jsonify({
                'needs_disambiguation': True,
                'query': identifier,
                'candidates': [
                    {
                        'id': c.get('id', '').replace('https://openalex.org/', ''),
                        'display_name': c.get('display_name'),
                        'works_count': c.get('works_count'),
                        'cited_by_count': c.get('cited_by_count'),
                        'affiliations': [
                            aff.get('institution', {}).get('display_name')
                            for aff in c.get('affiliations', [])[:3]
                        ],
                        'orcid': c.get('orcid')
                    }
                    for c in candidates[:10]  # Limit to top 10
                ]
            })
    
    try:
        # Resolve author (direct ID, ORCID, or single name match)
        author = resolve_author(identifier, affiliation_hint=affiliation)
        
        return fetch_author_works(author, pubmed_fallback=pubmed_fallback, session_id=session_id)
        
    except ValueError as e:
        if session_id:
            send_progress(session_id, f'❌ {str(e)}', 100, 'error')
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        if session_id:
            send_progress(session_id, f'❌ Error: {str(e)}', 100, 'error')
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


@app.route('/api/author/<author_id>/works', methods=['GET'])
def get_author_works(author_id):
    """
    Fetch works for a specific author by OpenAlex ID.
    Used after disambiguation.
    
    Query params:
        - pubmed_fallback: "true" to enable PubMed abstract fallback (slow!)
        - session_id: (optional) Session ID for SSE progress streaming
    """
    from pyalex import Authors
    
    pubmed_fallback = request.args.get('pubmed_fallback', '').lower() == 'true'
    session_id = request.args.get('session_id')
    
    try:
        if session_id:
            send_progress(session_id, f'🔍 Fetching author {author_id}...', 0, 'fetching')
        
        # Fetch author info
        author = Authors()[author_id]
        if not author:
            if session_id:
                send_progress(session_id, '❌ Author not found', 100, 'error')
            return jsonify({'error': 'Author not found'}), 404
        
        return fetch_author_works(author, pubmed_fallback=pubmed_fallback, session_id=session_id)
        
    except Exception as e:
        if session_id:
            send_progress(session_id, f'❌ Error: {str(e)}', 100, 'error')
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


def fetch_author_works(author: dict, pubmed_fallback: bool = False, session_id: str = None):
    """Helper to fetch works for a resolved author.
    
    Args:
        author: Author dict from OpenAlex
        pubmed_fallback: If True, try PubMed for missing abstracts (SLOW - adds ~0.3s per work)
        session_id: Optional session ID for SSE progress streaming
    """
    from pyalex import Works
    
    # Get author ID in both formats
    author_id_full = author.get('id', '')
    author_id_short = author_id_full.replace('https://openalex.org/', '')
    author_name = author.get('display_name', author_id_short)
    
    # pyalex filter expects just the short ID (A123456)
    works_query = Works().filter(author={"id": author_id_short})
    
    # Paginate through ALL works (no limit)
    all_works = []
    logger.info(f"🔄 Fetching all works for {author_id_short}...")
    if session_id:
        send_progress(session_id, f'🔄 Fetching works for {author_name}...', 5, 'fetching_works')
    
    for page in works_query.paginate(per_page=200):
        all_works.extend(page)
        msg = f'📥 Fetched {len(all_works)} works so far...'
        logger.info(f"  {msg}")
        if session_id:
            send_progress(session_id, msg, 10, 'fetching_works')
    
    logger.info(f"✓ Total works fetched: {len(all_works)}")
    if session_id:
        send_progress(session_id, f'✓ Total works fetched: {len(all_works)}', 15, 'processing', total=len(all_works))
    
    if pubmed_fallback:
        msg = '⚠️ PubMed fallback enabled - this may take a while...'
        logger.info(msg)
        if session_id:
            send_progress(session_id, msg, 15, 'processing')
    
    # Format results with abstract extraction
    results = []
    stats = {'openalex': 0, 'pubmed': 0, 'none': 0}
    
    # NEW: Aggregate funding/grant data
    funders = {}
    total_grants_found = 0
    
    total = len(all_works)
    for i, work in enumerate(all_works):
        work_id = work.get('id', '').replace('https://openalex.org/', '')
        work_title = work.get('title', 'Untitled')
        if work_title and len(work_title) > 50:
            work_title = work_title[:50] + '...'
        
        # Progress update for every work
        progress_pct = 15 + (i / total * 80) if total > 0 else 15
        msg = f'📝 Processing work {i + 1}/{total}: {work_title}'
        
        # Log every 10 works (less spam)
        if (i + 1) % 10 == 0 or i == 0 or (i + 1) == total:
            logger.info(msg)
        
        # Always send to SSE stream
        if session_id:
            send_progress(session_id, msg, progress_pct, 'processing')
        
        # Use abstract_extractor - PubMed fallback only if explicitly requested
        abstract_result = extract_abstract(work, fallback_to_pubmed=pubmed_fallback)
        abstract = abstract_result.get('abstract')
        abstract_source = abstract_result.get('source')
        
        # Track stats
        if abstract_source:
            if abstract_source == 'openalex':
                stats['openalex'] += 1
            elif abstract_source.startswith('pubmed'):
                stats['pubmed'] += 1
                pubmed_msg = f'📚 PubMed fallback success for: {work_title}'
                logger.debug(pubmed_msg)
                if session_id:
                    send_progress(session_id, pubmed_msg, progress_pct, 'processing')
        else:
            stats['none'] += 1
        
        # NEW: Extract grant/funding data from this work
        work_grants = work.get('grants', [])
        if work_grants:
            logger.debug(f"💰 Found {len(work_grants)} grant(s) for: {work_title[:40]}...")
            for grant in work_grants:
                total_grants_found += 1
                funder_name = grant.get('funder_display_name') or grant.get('funder', 'Unknown Funder')
                funder_id = grant.get('funder')  # OpenAlex funder ID
                award_id = grant.get('award_id')
                
                if funder_name not in funders:
                    funders[funder_name] = {
                        'funder_id': funder_id,
                        'count': 0,
                        'awards': [],
                        'works': []
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
            'publication_date': work.get('publication_date'),  # Full date when available (YYYY-MM-DD)
            'type': work.get('type'),
            'cited_by_count': work.get('cited_by_count', 0),
            'abstract': abstract,
            'abstract_source': abstract_source
        })
    
    stats_msg = f"📊 Abstract stats: OpenAlex={stats['openalex']}, PubMed={stats['pubmed']}, Missing={stats['none']}"
    logger.info(stats_msg)
    
    # NEW: Log funding stats
    if funders:
        funding_msg = f"💰 Funding stats: {len(funders)} funders, {total_grants_found} grant mentions across {sum(len(f['works']) for f in funders.values())} works"
        logger.info(funding_msg)
        logger.info("💰 Top funders:")
        for funder_name, funder_data in sorted(funders.items(), key=lambda x: -x[1]['count'])[:5]:
            logger.info(f"   - {funder_name}: {funder_data['count']} mentions, {len(funder_data['awards'])} unique awards")
    else:
        logger.info("💰 No funding/grant data found in OpenAlex for this author's works")
    
    if session_id:
        send_progress(session_id, stats_msg, 100, 'complete')
    
    # Build sorted funders list for response
    funders_list = [
        {
            'name': name,
            'funder_id': data['funder_id'],
            'mention_count': data['count'],
            'unique_awards': len(data['awards']),
            'awards': data['awards'][:10],  # Limit to first 10 award IDs
            'works_count': len(data['works'])
        }
        for name, data in sorted(funders.items(), key=lambda x: -x[1]['count'])
    ]
    
    return jsonify({
        'author': {
            'id': author_id_short,
            'display_name': author.get('display_name'),
            'works_count': author.get('works_count'),
            'cited_by_count': author.get('cited_by_count'),
            'orcid': author.get('orcid'),
            'affiliations': [
                aff.get('institution', {}).get('display_name')
                for aff in author.get('affiliations', [])[:3]
            ]
        },
        'works': results,
        'total_works': len(results),
        'abstract_stats': stats,
        # NEW: Include funding data in response
        'funding': {
            'funders': funders_list,
            'total_mentions': total_grants_found,
            'works_with_funding': len(set(w for f in funders.values() for w in f['works']))
        }
    })


@app.route('/api/candidates', methods=['POST'])
def get_candidates():
    """
    Get list of candidate authors for disambiguation.
    
    Request body:
        - name: Author name to search
        - affiliation: (optional) Affiliation hint
    """
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    affiliation = data.get('affiliation', '').strip() or None
    
    if not name:
        return jsonify({'error': 'Please provide an author name'}), 400
    
    try:
        candidates = list_candidates(name, affiliation_hint=affiliation)
        return jsonify({'candidates': candidates})
    except Exception as e:
        return jsonify({'error': f'An error occurred: {str(e)}'}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5001)

