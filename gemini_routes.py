"""
Gemini Analysis Routes - Flask Blueprint

Simple endpoints for storing works and analyzing with Gemini.
No RAG complexity - just large context analysis.
"""

import os
from flask import Blueprint, request, jsonify
from gemini_analyzer import GeminiAnalyzer, store_works, get_stored_works, clear_stored


# Create Blueprint
gemini_bp = Blueprint('gemini', __name__, url_prefix='/api/gemini')


@gemini_bp.route('/store', methods=['POST'])
def store_works_endpoint():
    """
    Store works for Gemini analysis.
    
    Request body:
        - works: List of work records
        - author_name: Author display name
    
    Returns:
        JSON with stored count and abstract count
    """
    data = request.get_json() or {}
    works = data.get('works', [])
    author_name = data.get('author_name')
    
    if not works:
        return jsonify({'error': 'No works provided'}), 400
    
    store_works(works, author_name)
    
    # Count works with abstracts
    with_abstracts = sum(1 for w in works if w.get('abstract'))
    
    return jsonify({
        'stored': len(works),
        'with_abstracts': with_abstracts,
        'author_name': author_name
    })


@gemini_bp.route('/analyze', methods=['POST'])
def analyze_endpoint():
    """
    Analyze all abstracts with Gemini.
    
    Request body:
        - question: The question to answer
        - model: (optional) Gemini model to use
    
    Returns:
        JSON with comprehensive analysis
    """
    data = request.get_json() or {}
    question = data.get('question', '').strip()
    model = data.get('model')
    
    if not question:
        return jsonify({'error': 'Question is required'}), 400
    
    works, author_name = get_stored_works()
    
    if not works:
        return jsonify({'error': 'No works stored. Search for an author first.'}), 400
    
    # Get API key
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
            **result
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'Analysis failed: {str(e)}'}), 500


@gemini_bp.route('/status', methods=['GET'])
def status_endpoint():
    """Get current stored works status."""
    works, author_name = get_stored_works()
    with_abstracts = sum(1 for w in works if w.get('abstract'))
    
    return jsonify({
        'stored_works': len(works),
        'with_abstracts': with_abstracts,
        'author_name': author_name,
        'ready': len(works) > 0
    })


@gemini_bp.route('/clear', methods=['POST'])
def clear_endpoint():
    """Clear stored works."""
    clear_stored()
    return jsonify({'success': True, 'message': 'Cleared'})
