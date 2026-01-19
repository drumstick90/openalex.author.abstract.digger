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
    print("   - POST /api/gemini/analyze  - Ask Gemini about all abstracts")
    print("   - GET  /api/gemini/status   - Check stored works status")
    print("   - POST /api/gemini/clear    - Clear stored works")
    print()
    print("💡 After fetching an author's works, you can ask Gemini questions!")
    print()
    app.run(debug=True, port=5001)
