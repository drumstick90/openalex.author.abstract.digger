"""
Extended Flask App with Gemini Analysis Support

Run this instead of app.py to enable Gemini analysis functionality.

Usage:
    python3.11 app_rag.py
"""

from app import app
from gemini_routes import gemini_bp

# Register Gemini blueprint
app.register_blueprint(gemini_bp)  # API routes at /api/gemini/*

if __name__ == '__main__':
    print("🚀 Starting Biomedical Abstract Explorer...")
    print("📍 Main page: http://localhost:5001/")
    print("📍 Gemini endpoints available at /api/gemini/*")
    print("   - POST /api/gemini/store    - Store works for analysis")
    print("   - POST /api/gemini/extract-all  - Start parallel extraction (SSE progress)")
    print("   - GET  /api/gemini/extract-progress/<id> - SSE stream for extraction progress")
    print("   - POST /api/gemini/synthesize   - Query cached extracts (fast)")
    print("   - POST /api/gemini/analyze      - Direct analysis (fallback)")
    print("   - GET  /api/gemini/extracts     - Get cached extracts with summary")
    print("   - GET  /api/gemini/status       - Check stored works status")
    print("   - POST /api/gemini/clear        - Clear stored works and cache")
    print()
    print("💡 Two-stage analysis:")
    print("   1. Click 'Extract All Insights' to process all abstracts (parallel, ~2-3 min)")
    print("   2. Ask follow-up questions using cached extracts (instant, cheap)")
    print()
    app.run(debug=True, port=5001)
