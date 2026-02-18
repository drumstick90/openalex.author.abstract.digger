"""
Gemini Analysis Routes - Flask Blueprint

Map-Reduce architecture:
- POST /api/gemini/extract-all: Parallel extraction with SSE progress
- POST /api/gemini/synthesize: Query cached extracts
- POST /api/gemini/analyze: Legacy direct analysis (fallback)
"""

import json
import os
import queue
import threading
from flask import Blueprint, request, jsonify, Response

from gemini_analyzer import GeminiAnalyzer
from gemini_store import (
    store_works,
    get_stored_works,
    get_cached_extracts,
    set_cached_extracts,
    is_extraction_in_progress,
    set_extraction_in_progress,
    clear_stored,
    save_extracts_to_file,
    load_extracts_from_file,
)


# Create Blueprint
gemini_bp = Blueprint('gemini', __name__, url_prefix='/api/gemini')

# SSE queues for extraction progress
extraction_queues: dict[str, queue.Queue] = {}


@gemini_bp.route('/store', methods=['POST'])
def store_works_endpoint():
    """
    Store works for Gemini analysis.
    
    Request body:
        - works: List of work records
        - author_name: Author display name
        - author_id: Author OpenAlex ID
    
    Returns:
        JSON with stored count and abstract count
    """
    data = request.get_json() or {}
    works = data.get('works', [])
    author_name = data.get('author_name')
    author_id = data.get('author_id')
    
    if not works:
        return jsonify({'error': 'No works provided'}), 400
    
    store_works(works, author_name, author_id)
    
    # Count works with abstracts
    with_abstracts = sum(1 for w in works if w.get('abstract'))
    
    # Check if we have cached extracts for this author
    cached = load_extracts_from_file(author_id)
    
    return jsonify({
        'stored': len(works),
        'with_abstracts': with_abstracts,
        'author_name': author_name,
        'has_cached_extracts': len(cached) > 0,
        'cached_extracts_count': len(cached)
    })


@gemini_bp.route('/extract-all', methods=['POST'])
def extract_all_endpoint():
    """
    Start extraction of all abstracts. Returns SSE stream with progress.
    
    Request body:
        - session_id: Unique session ID for SSE progress
        - max_workers: Number of parallel workers (default 5)
        - rpm: Target requests per minute (default 50)
    
    Returns:
        JSON with extraction results when complete
    """
    data = request.get_json() or {}
    session_id = data.get('session_id', 'default')
    max_workers = min(data.get('max_workers', 5), 10)  # Cap at 10
    rpm = min(data.get('rpm', 50), 100)  # Cap at 100 RPM
    
    works, author_name = get_stored_works()
    
    if not works:
        return jsonify({'error': 'No works stored. Search for an author first.'}), 400
    
    if is_extraction_in_progress():
        return jsonify({'error': 'Extraction already in progress'}), 409
    
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'GEMINI_API_KEY not set in environment'}), 400
    
    # Create progress queue for this session
    progress_queue = queue.Queue(maxsize=1000)
    extraction_queues[session_id] = progress_queue
    
    def run_extraction():
        try:
            set_extraction_in_progress(True)
            
            analyzer = GeminiAnalyzer(api_key)
            
            def progress_callback(completed, total, message):
                try:
                    progress_queue.put_nowait({
                        'completed': completed,
                        'total': total,
                        'message': message,
                        'progress': int((completed / total) * 100) if total > 0 else 0
                    })
                except queue.Full:
                    pass
            
            extracts = analyzer.extract_all(
                works=works,
                max_workers=max_workers,
                requests_per_minute=rpm,
                progress_callback=progress_callback
            )
            
            # Cache the results
            set_cached_extracts(extracts)
            save_extracts_to_file(extracts)
            
            # Signal completion
            success_count = sum(1 for e in extracts if e.get('extracted'))
            progress_queue.put({
                'phase': 'complete',
                'total_extracted': len(extracts),
                'success_count': success_count,
                'message': f'Extraction complete: {success_count}/{len(extracts)} successful'
            })
            
        except Exception as e:
            progress_queue.put({
                'phase': 'error',
                'error': str(e)
            })
        finally:
            set_extraction_in_progress(False)
    
    # Start extraction in background thread
    thread = threading.Thread(target=run_extraction, daemon=True)
    thread.start()
    
    return jsonify({
        'status': 'started',
        'session_id': session_id,
        'total_works': len(works),
        'with_abstracts': sum(1 for w in works if w.get('abstract'))
    })


@gemini_bp.route('/extract-progress/<session_id>')
def extract_progress_stream(session_id):
    """SSE endpoint for extraction progress."""
    def generate():
        q = extraction_queues.get(session_id)
        if not q:
            yield f"data: {json.dumps({'error': 'No active extraction for this session'})}\n\n"
            return
        
        yield f"data: {json.dumps({'phase': 'connected'})}\n\n"
        
        while True:
            try:
                data = q.get(timeout=60)
                yield f"data: {json.dumps(data)}\n\n"
                
                # Check for completion
                if data.get('phase') in ('complete', 'error'):
                    break
                    
            except queue.Empty:
                yield f": keepalive\n\n"
        
        # Cleanup
        extraction_queues.pop(session_id, None)
    
    return Response(
        generate(),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no'
        }
    )


@gemini_bp.route('/synthesize', methods=['POST'])
def synthesize_endpoint():
    """
    Synthesize insights from cached extracts.
    
    Request body:
        - question: The question to answer
    
    Returns:
        JSON with synthesis results
    """
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    
    if not question:
        return jsonify({'error': 'Question is required'}), 400
    
    # Try to get cached extracts
    extracts = get_cached_extracts()
    if not extracts:
        extracts = load_extracts_from_file()
    
    if not extracts:
        return jsonify({
            'error': 'No cached extracts available. Please run extraction first.',
            'needs_extraction': True
        }), 400
    
    _, author_name = get_stored_works()
    
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'GEMINI_API_KEY not set in environment'}), 400
    
    try:
        analyzer = GeminiAnalyzer(api_key)
        result = analyzer.synthesize(
            extracts=extracts,
            question=question,
            author_name=author_name
        )
        
        return jsonify({
            'question': question,
            **result
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Synthesis failed: {str(e)}'}), 500


@gemini_bp.route('/analyze', methods=['POST'])
def analyze_endpoint():
    """
    Legacy: Analyze all abstracts directly (without extraction caching).
    Use /synthesize with cached extracts for better performance.
    
    Request body:
        - question: The question to answer
        - model: (optional) Gemini model to use
    
    Returns:
        JSON with analysis results
    """
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    model = data.get('model')
    use_cache = data.get('use_cache', True)  # Try cache by default
    
    if not question:
        return jsonify({'error': 'Question is required'}), 400
    
    # If we have cached extracts and use_cache is True, use synthesize instead
    if use_cache:
        extracts = get_cached_extracts()
        if not extracts:
            extracts = load_extracts_from_file()
        
        if extracts:
            _, author_name = get_stored_works()
            api_key = os.environ.get('GEMINI_API_KEY', '')
            
            try:
                analyzer = GeminiAnalyzer(api_key, model)
                result = analyzer.synthesize(
                    extracts=extracts,
                    question=question,
                    author_name=author_name
                )
                
                return jsonify({
                    'question': question,
                    'source': 'cached_extracts',
                    **result
                })
            except Exception as e:
                print(f"Cache synthesis failed, falling back to direct: {e}")
    
    # Fall back to direct analysis
    works, author_name = get_stored_works()
    
    if not works:
        return jsonify({'error': 'No works stored. Search for an author first.'}), 400
    
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'GEMINI_API_KEY not set in environment'}), 400
    
    try:
        analyzer = GeminiAnalyzer(api_key, model)
        result = analyzer.analyze(
            question=question,
            works=works,
            author_name=author_name
        )
        
        return jsonify({
            'question': question,
            'source': 'direct_abstracts',
            **result
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500


@gemini_bp.route('/status', methods=['GET'])
def status_endpoint():
    """Get current stored works and extraction status."""
    works, author_name = get_stored_works()
    with_abstracts = sum(1 for w in works if w.get('abstract'))
    
    extracts = get_cached_extracts()
    if not extracts:
        extracts = load_extracts_from_file()
    
    extracted_count = sum(1 for e in extracts if e.get('extracted')) if extracts else 0
    
    return jsonify({
        'stored_works': len(works),
        'with_abstracts': with_abstracts,
        'author_name': author_name,
        'ready': len(works) > 0,
        'extraction_in_progress': is_extraction_in_progress(),
        'has_cached_extracts': len(extracts) > 0,
        'cached_extracts_count': len(extracts),
        'successful_extracts': extracted_count
    })


@gemini_bp.route('/extracts', methods=['GET'])
def get_extracts_endpoint():
    """Get the cached extracts data with comprehensive summary statistics."""
    extracts = get_cached_extracts()
    if not extracts:
        extracts = load_extracts_from_file()
    
    if not extracts:
        return jsonify({'error': 'No cached extracts available'}), 404
    
    # Build comprehensive summary statistics
    themes = {}
    study_types = {}
    all_keywords = {}
    evidence_levels = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    novelty_counts = {}
    all_drugs = {}
    all_conditions = {}
    all_biomarkers = {}
    limitations_count = 0
    clinical_implications_count = 0
    
    for ext in extracts:
        if not ext.get('extracted'):
            continue
            
        # Count themes
        theme = ext.get('theme', 'Unknown')
        themes[theme] = themes.get(theme, 0) + 1
        
        # Count study types
        study_type = ext.get('study_type', 'Unknown')
        study_types[study_type] = study_types.get(study_type, 0) + 1
        
        # Count keywords
        for kw in ext.get('keywords', []):
            all_keywords[kw] = all_keywords.get(kw, 0) + 1
        
        # Count evidence levels
        ev_level = ext.get('evidence_level')
        if ev_level and isinstance(ev_level, int) and 1 <= ev_level <= 5:
            evidence_levels[ev_level] += 1
        
        # Count novelty types
        novelty = ext.get('novelty')
        if novelty:
            novelty_counts[novelty] = novelty_counts.get(novelty, 0) + 1
        
        # Count drugs
        for drug in ext.get('drugs_studied', []):
            if drug:
                all_drugs[drug] = all_drugs.get(drug, 0) + 1
        
        # Count conditions
        for cond in ext.get('conditions', []):
            if cond:
                all_conditions[cond] = all_conditions.get(cond, 0) + 1
        
        # Count biomarkers
        for bio in ext.get('biomarkers', []):
            if bio:
                all_biomarkers[bio] = all_biomarkers.get(bio, 0) + 1
        
        # Count papers with limitations mentioned
        if ext.get('limitations'):
            limitations_count += 1
        
        # Count papers with clinical implications
        if ext.get('clinical_implication'):
            clinical_implications_count += 1
    
    # Sort by frequency
    top_themes = sorted(themes.items(), key=lambda x: -x[1])[:10]
    top_keywords = sorted(all_keywords.items(), key=lambda x: -x[1])[:20]
    top_drugs = sorted(all_drugs.items(), key=lambda x: -x[1])[:10]
    top_conditions = sorted(all_conditions.items(), key=lambda x: -x[1])[:10]
    top_biomarkers = sorted(all_biomarkers.items(), key=lambda x: -x[1])[:10]
    
    successful_count = sum(1 for e in extracts if e.get('extracted'))
    
    return jsonify({
        'extracts': extracts,
        'count': len(extracts),
        'successful': successful_count,
        'summary': {
            'top_themes': top_themes,
            'study_types': dict(study_types),
            'top_keywords': top_keywords,
            'evidence_levels': evidence_levels,
            'novelty': dict(novelty_counts),
            'top_drugs': top_drugs,
            'top_conditions': top_conditions,
            'top_biomarkers': top_biomarkers,
            'with_limitations': limitations_count,
            'with_clinical_implications': clinical_implications_count
        }
    })


@gemini_bp.route('/clear', methods=['POST'])
def clear_endpoint():
    """Clear stored works and cached extracts."""
    clear_stored()
    return jsonify({'success': True, 'message': 'Cleared works and extracts'})
