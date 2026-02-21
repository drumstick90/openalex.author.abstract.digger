"""
AI Analysis Routes - Flask Blueprint

Map-Reduce architecture with multi-provider support (Gemini, OpenAI, Anthropic):
- POST /api/gemini/extract-all: Parallel extraction with SSE progress
- POST /api/gemini/synthesize: Query cached extracts
- POST /api/gemini/analyze: Legacy direct analysis (fallback)
- GET  /api/ai/providers: List available providers and models
"""

import json
import queue
import threading
from flask import Blueprint, request, jsonify, Response

from gemini_analyzer import LLMAnalyzer
from llm_adapters import create_adapter, get_providers_info
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


gemini_bp = Blueprint('gemini', __name__, url_prefix='/api/gemini')
ai_bp = Blueprint('ai', __name__, url_prefix='/api/ai')

extraction_queues: dict[str, queue.Queue] = {}


def _get_ai_config(data: dict) -> dict:
    """Extract provider/api_key/model from request body."""
    return {
        "provider": data.get("provider", "gemini"),
        "api_key": data.get("api_key") or None,
        "model": data.get("model") or None,
    }


def _make_analyzer(data: dict) -> LLMAnalyzer:
    """Create an LLMAnalyzer from request-level AI config."""
    cfg = _get_ai_config(data)
    adapter = create_adapter(cfg["provider"], cfg["api_key"], cfg["model"])
    return LLMAnalyzer(adapter)


# ── Provider info ────────────────────────────────────────────

@ai_bp.route('/providers', methods=['GET'])
def providers_endpoint():
    return jsonify({"providers": get_providers_info()})


# ── Store works ──────────────────────────────────────────────

@gemini_bp.route('/store', methods=['POST'])
def store_works_endpoint():
    data = request.get_json() or {}
    works = data.get('works', [])
    author_name = data.get('author_name')
    author_id = data.get('author_id')

    if not works:
        return jsonify({'error': 'No works provided'}), 400

    store_works(works, author_name, author_id)
    with_abstracts = sum(1 for w in works if w.get('abstract'))
    cached = load_extracts_from_file(author_id)

    return jsonify({
        'stored': len(works),
        'with_abstracts': with_abstracts,
        'author_name': author_name,
        'has_cached_extracts': len(cached) > 0,
        'cached_extracts_count': len(cached),
    })


# ── Extract all ──────────────────────────────────────────────

@gemini_bp.route('/extract-all', methods=['POST'])
def extract_all_endpoint():
    data = request.get_json() or {}
    session_id = data.get('session_id', 'default')
    max_workers = min(data.get('max_workers', 5), 10)
    rpm = min(data.get('rpm', 50), 100)
    ai_cfg = _get_ai_config(data)

    works, author_name = get_stored_works()
    if not works:
        return jsonify({'error': 'No works stored. Search for an author first.'}), 400

    if is_extraction_in_progress():
        return jsonify({'error': 'Extraction already in progress'}), 409

    try:
        adapter = create_adapter(ai_cfg["provider"], ai_cfg["api_key"], ai_cfg["model"])
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    progress_queue = queue.Queue(maxsize=1000)
    extraction_queues[session_id] = progress_queue

    def run_extraction():
        try:
            set_extraction_in_progress(True)
            analyzer = LLMAnalyzer(adapter)

            def progress_callback(completed, total, message):
                try:
                    progress_queue.put_nowait({
                        'completed': completed,
                        'total': total,
                        'message': message,
                        'progress': int((completed / total) * 100) if total > 0 else 0,
                    })
                except queue.Full:
                    pass

            extracts = analyzer.extract_all(
                works=works,
                max_workers=max_workers,
                requests_per_minute=rpm,
                progress_callback=progress_callback,
            )

            set_cached_extracts(extracts)
            save_extracts_to_file(extracts)

            success_count = sum(1 for e in extracts if e.get('extracted'))
            progress_queue.put({
                'phase': 'complete',
                'total_extracted': len(extracts),
                'success_count': success_count,
                'message': f'Extraction complete: {success_count}/{len(extracts)} successful',
            })
        except Exception as e:
            progress_queue.put({'phase': 'error', 'error': str(e)})
        finally:
            set_extraction_in_progress(False)

    thread = threading.Thread(target=run_extraction, daemon=True)
    thread.start()

    return jsonify({
        'status': 'started',
        'session_id': session_id,
        'total_works': len(works),
        'with_abstracts': sum(1 for w in works if w.get('abstract')),
    })


# ── Extraction progress SSE ─────────────────────────────────

@gemini_bp.route('/extract-progress/<session_id>')
def extract_progress_stream(session_id):
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
                if data.get('phase') in ('complete', 'error'):
                    break
            except queue.Empty:
                yield ": keepalive\n\n"
        extraction_queues.pop(session_id, None)

    return Response(generate(), mimetype='text/event-stream', headers={
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'X-Accel-Buffering': 'no',
    })


# ── Synthesize ───────────────────────────────────────────────

@gemini_bp.route('/synthesize', methods=['POST'])
def synthesize_endpoint():
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    if not question:
        return jsonify({'error': 'Question is required'}), 400

    extracts = get_cached_extracts()
    if not extracts:
        extracts = load_extracts_from_file()
    if not extracts:
        return jsonify({
            'error': 'No cached extracts available. Please run extraction first.',
            'needs_extraction': True,
        }), 400

    _, author_name = get_stored_works()

    try:
        analyzer = _make_analyzer(data)
        result = analyzer.synthesize(extracts=extracts, question=question, author_name=author_name)
        return jsonify({'question': question, **result})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Synthesis failed: {str(e)}'}), 500


# ── Analyze (legacy / fallback) ──────────────────────────────

@gemini_bp.route('/analyze', methods=['POST'])
def analyze_endpoint():
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    use_cache = data.get('use_cache', True)

    if not question:
        return jsonify({'error': 'Question is required'}), 400

    if use_cache:
        extracts = get_cached_extracts()
        if not extracts:
            extracts = load_extracts_from_file()
        if extracts:
            _, author_name = get_stored_works()
            try:
                analyzer = _make_analyzer(data)
                result = analyzer.synthesize(extracts=extracts, question=question, author_name=author_name)
                return jsonify({'question': question, 'source': 'cached_extracts', **result})
            except Exception as e:
                print(f"Cache synthesis failed, falling back to direct: {e}")

    works, author_name = get_stored_works()
    if not works:
        return jsonify({'error': 'No works stored. Search for an author first.'}), 400

    try:
        analyzer = _make_analyzer(data)
        result = analyzer.analyze(question=question, works=works, author_name=author_name)
        return jsonify({'question': question, 'source': 'direct_abstracts', **result})
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500


# ── Status / Extracts / Clear ────────────────────────────────

@gemini_bp.route('/status', methods=['GET'])
def status_endpoint():
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
        'successful_extracts': extracted_count,
    })


@gemini_bp.route('/extracts', methods=['GET'])
def get_extracts_endpoint():
    extracts = get_cached_extracts()
    if not extracts:
        extracts = load_extracts_from_file()
    if not extracts:
        return jsonify({'error': 'No cached extracts available'}), 404

    themes, study_types, all_keywords = {}, {}, {}
    evidence_levels = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    novelty_counts, all_drugs, all_conditions, all_biomarkers = {}, {}, {}, {}
    limitations_count = clinical_implications_count = 0

    for ext in extracts:
        if not ext.get('extracted'):
            continue
        themes[ext.get('theme', 'Unknown')] = themes.get(ext.get('theme', 'Unknown'), 0) + 1
        st = ext.get('study_type', 'Unknown')
        study_types[st] = study_types.get(st, 0) + 1
        for kw in ext.get('keywords', []):
            all_keywords[kw] = all_keywords.get(kw, 0) + 1
        ev = ext.get('evidence_level')
        if isinstance(ev, int) and 1 <= ev <= 5:
            evidence_levels[ev] += 1
        n = ext.get('novelty')
        if n:
            novelty_counts[n] = novelty_counts.get(n, 0) + 1
        for d in ext.get('drugs_studied', []):
            if d: all_drugs[d] = all_drugs.get(d, 0) + 1
        for c in ext.get('conditions', []):
            if c: all_conditions[c] = all_conditions.get(c, 0) + 1
        for b in ext.get('biomarkers', []):
            if b: all_biomarkers[b] = all_biomarkers.get(b, 0) + 1
        if ext.get('limitations'):
            limitations_count += 1
        if ext.get('clinical_implication'):
            clinical_implications_count += 1

    successful_count = sum(1 for e in extracts if e.get('extracted'))

    return jsonify({
        'extracts': extracts,
        'count': len(extracts),
        'successful': successful_count,
        'summary': {
            'top_themes': sorted(themes.items(), key=lambda x: -x[1])[:10],
            'study_types': dict(study_types),
            'top_keywords': sorted(all_keywords.items(), key=lambda x: -x[1])[:20],
            'evidence_levels': evidence_levels,
            'novelty': dict(novelty_counts),
            'top_drugs': sorted(all_drugs.items(), key=lambda x: -x[1])[:10],
            'top_conditions': sorted(all_conditions.items(), key=lambda x: -x[1])[:10],
            'top_biomarkers': sorted(all_biomarkers.items(), key=lambda x: -x[1])[:10],
            'with_limitations': limitations_count,
            'with_clinical_implications': clinical_implications_count,
        },
    })


@gemini_bp.route('/clear', methods=['POST'])
def clear_endpoint():
    clear_stored()
    return jsonify({'success': True, 'message': 'Cleared works and extracts'})
