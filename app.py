"""
Flask backend for Biomedical Abstract Explorer.
Routes delegate business logic to works_service and gemini_routes.
"""

import json
import logging
import os
import queue
import threading
from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_from_directory, Response

load_dotenv()
import pyalex
from author_resolver import resolve_author, list_candidates
from abstract_extractor import set_entrez_email
from works_service import process_author_works

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# SSE progress streams: session_id -> queue
progress_streams: dict[str, queue.Queue] = {}

DEFAULT_EMAIL = "openalex-user@example.com"
pyalex.config.email = DEFAULT_EMAIL
set_entrez_email(DEFAULT_EMAIL)

# Gemini blueprint
from gemini_routes import gemini_bp
app.register_blueprint(gemini_bp)


# ---------------------------------------------------------------------------
# Static / health
# ---------------------------------------------------------------------------

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


@app.route('/api/health')
def health():
    return jsonify({'status': 'ok'})


# ---------------------------------------------------------------------------
# SSE progress helpers
# ---------------------------------------------------------------------------

def send_progress(session_id: str, message: str, progress: float = None,
                  phase: str = None, total: int = None):
    if session_id not in progress_streams:
        return
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
        pass


@app.route('/api/progress/<session_id>')
def progress_stream(session_id):
    def generate():
        q = queue.Queue(maxsize=100)
        progress_streams[session_id] = q
        try:
            yield f"data: {json.dumps({'message': 'Connected', 'phase': 'connected'})}\n\n"
            while True:
                try:
                    data = q.get(timeout=30)
                    yield f"data: {json.dumps(data)}\n\n"
                    if data.get('phase') in ('complete', 'error'):
                        break
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            progress_streams.pop(session_id, None)

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
    })


# ---------------------------------------------------------------------------
# Author / works routes
# ---------------------------------------------------------------------------

def _run_author_works(author: dict, pubmed_fallback: bool, session_id: str):
    """Thin controller: wires SSE progress into works_service and returns JSON."""
    def cb(msg, pct, phase=None, total=None):
        send_progress(session_id, msg, pct, phase, total)

    result = process_author_works(
        author,
        pubmed_fallback=pubmed_fallback,
        progress_callback=cb if session_id else None,
    )
    return jsonify(result)


@app.route('/api/search', methods=['POST'])
def search_author():
    """
    Search for an author and return their works with abstracts.

    Body:
        identifier  – OpenAlex ID, ORCID, or name
        email       – (optional) for polite pool access
        affiliation – (optional) disambiguation hint
        pubmed_fallback – (optional) bool
        session_id  – (optional) for SSE progress
    """
    data = request.get_json() or {}
    identifier = data.get('identifier', '').strip()
    email = data.get('email', '').strip()
    affiliation = data.get('affiliation', '').strip() or None
    pubmed_fallback = data.get('pubmed_fallback', False)
    session_id = data.get('session_id')

    if not identifier:
        return jsonify({'error': 'Please provide an author identifier'}), 400

    if email:
        pyalex.config.email = email
        set_entrez_email(email)

    from author_resolver import is_openalex_id, is_orcid, resolve_by_name

    if session_id:
        send_progress(session_id, '🔍 Looking up author...', 0, 'searching')

    if not is_openalex_id(identifier) and not is_orcid(identifier):
        candidates = resolve_by_name(identifier, affiliation)

        if not candidates:
            if session_id:
                send_progress(session_id, f'❌ No authors found matching: {identifier}', 100, 'error')
            return jsonify({'error': f'No authors found matching: {identifier}'}), 404

        if len(candidates) > 1:
            if session_id:
                send_progress(session_id, f'📋 Found {len(candidates)} matching authors', 100, 'complete')
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
                        'orcid': c.get('orcid'),
                    }
                    for c in candidates[:10]
                ],
            })

    try:
        author = resolve_author(identifier, affiliation_hint=affiliation)
        return _run_author_works(author, pubmed_fallback, session_id)
    except ValueError as e:
        if session_id:
            send_progress(session_id, f'❌ {e}', 100, 'error')
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        if session_id:
            send_progress(session_id, f'❌ Error: {e}', 100, 'error')
        return jsonify({'error': f'An error occurred: {e}'}), 500


@app.route('/api/author/<author_id>/works', methods=['GET'])
def get_author_works(author_id):
    """Fetch works for a specific author by OpenAlex ID (used after disambiguation)."""
    from pyalex import Authors

    pubmed_fallback = request.args.get('pubmed_fallback', '').lower() == 'true'
    session_id = request.args.get('session_id')

    try:
        if session_id:
            send_progress(session_id, f'🔍 Fetching author {author_id}...', 0, 'fetching')
        author = Authors()[author_id]
        if not author:
            if session_id:
                send_progress(session_id, '❌ Author not found', 100, 'error')
            return jsonify({'error': 'Author not found'}), 404
        return _run_author_works(author, pubmed_fallback, session_id)
    except Exception as e:
        if session_id:
            send_progress(session_id, f'❌ Error: {e}', 100, 'error')
        return jsonify({'error': f'An error occurred: {e}'}), 500


@app.route('/api/candidates', methods=['POST'])
def get_candidates():
    """Return candidate authors for a name query."""
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    affiliation = data.get('affiliation', '').strip() or None

    if not name:
        return jsonify({'error': 'Please provide an author name'}), 400

    try:
        candidates = list_candidates(name, affiliation_hint=affiliation)
        return jsonify({'candidates': candidates})
    except Exception as e:
        return jsonify({'error': f'An error occurred: {e}'}), 500


if __name__ == '__main__':
    print("🚀 Biomedical Abstract Explorer — http://localhost:5001/")
    print("   Gemini endpoints at /api/gemini/*")
    app.run(debug=True, port=5001)
