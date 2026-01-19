"""
Gemini Analyzer - Simple large-context analysis of all abstracts.
No RAG, no embeddings - just send everything to Gemini.
"""

import os
from typing import Optional


class GeminiAnalyzer:
    """
    Deep analysis using Gemini's large context window.
    Sends ALL abstracts to Gemini for comprehensive analysis.
    """
    
    SYSTEM_PROMPT = """You are a research analyst summarizing an academic author's body of work.

You have access to ALL abstracts from this author's publications.

Guidelines:
1. Consider the ENTIRE body of work
2. Identify major themes, research trajectories, and evolution over time
3. Note methodological approaches and impact areas
4. Do NOT cite specific paper titles or years inline — synthesize themes naturally
5. Use a flat, neutral, matter-of-fact tone — no hype, no flourishes
6. Be direct and concise

Keep your response under 1500 characters."""

    # Preferred models in order (best first)
    PREFERRED_MODELS = [
        "gemini-2.0-flash-exp",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash", 
    ]

    def __init__(self, api_key: str = None, model: str = None):
        """
        Initialize the Gemini Analyzer.
        
        Args:
            api_key: Google AI API key (or uses GEMINI_API_KEY env var)
            model: Model to use (auto-detected if not specified)
        """
        import google.generativeai as genai
        
        self.api_key = api_key or os.environ.get('GEMINI_API_KEY', '')
        if not self.api_key:
            raise ValueError("Gemini API key required. Set GEMINI_API_KEY in .env")
        
        genai.configure(api_key=self.api_key)
        
        if model:
            self.model = model
            print(f"✓ Using specified model: {model}")
        else:
            self.model = self._find_best_model(genai)
    
    def _find_best_model(self, genai) -> str:
        """Find the best available model for content generation."""
        try:
            available_models = []
            for model in genai.list_models():
                if 'generateContent' in model.supported_generation_methods:
                    name = model.name.replace('models/', '')
                    available_models.append(name)
            
            print(f"🔍 Available Gemini models: {available_models[:8]}...")
            
            # Find the first preferred model that's available
            for preferred in self.PREFERRED_MODELS:
                for available in available_models:
                    if preferred in available:
                        print(f"✓ Auto-selected model: {available}")
                        return available
            
            # Fallback
            for available in available_models:
                if 'gemini' in available.lower() and 'flash' in available.lower():
                    print(f"✓ Fallback model: {available}")
                    return available
            
            raise ValueError("No suitable Gemini model found")
            
        except Exception as e:
            print(f"⚠️ Could not list models: {e}. Using gemini-1.5-flash...")
            return "gemini-1.5-flash"
    
    def analyze(
        self,
        question: str,
        works: list[dict],
        author_name: str = None
    ) -> dict:
        """
        Analyze ALL abstracts to answer a question.
        
        Args:
            question: User's question
            works: ALL work records 
            author_name: Author's name for context
            
        Returns:
            Dict with 'answer', 'works_analyzed', 'model', etc.
        """
        import google.generativeai as genai
        
        genai.configure(api_key=self.api_key)
        
        # Filter works with abstracts
        works_with_abstracts = [w for w in works if w.get('abstract')]
        
        if not works_with_abstracts:
            return {
                "answer": "No abstracts available to analyze.",
                "works_analyzed": 0,
                "total_works": len(works),
                "model": self.model
            }
        
        # Build full context
        context = self._build_context(works_with_abstracts)
        
        # Estimate tokens
        estimated_tokens = int(len(context.split()) * 1.3)
        
        # Generate
        model = genai.GenerativeModel(
            model_name=self.model,
            system_instruction=self.SYSTEM_PROMPT
        )
        
        prompt = f"""Author: {author_name or 'Unknown'}
Total publications with abstracts: {len(works_with_abstracts)}

=== ALL ABSTRACTS ===
{context}
=== END ABSTRACTS ===

Question: {question}

Please provide a comprehensive analysis based on ALL the abstracts above."""

        print(f"📤 Sending {len(works_with_abstracts)} abstracts to Gemini ({estimated_tokens} est. tokens)...")
        
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(temperature=0.5)
        )
        
        print(f"✓ Gemini response received")
        
        return {
            "answer": response.text,
            "works_analyzed": len(works_with_abstracts),
            "total_works": len(works),
            "model": self.model,
            "estimated_tokens": estimated_tokens
        }
    
    def _build_context(self, works: list[dict]) -> str:
        """Build context string with ALL abstracts."""
        parts = []
        
        # Sort by year (newest first)
        sorted_works = sorted(
            works, 
            key=lambda w: w.get('publication_year') or 0, 
            reverse=True
        )
        
        for i, work in enumerate(sorted_works, 1):
            title = work.get('title', 'Untitled')
            year = work.get('publication_year', 'N/A')
            abstract = work.get('abstract', '')
            
            parts.append(f"[{i}] {title} ({year})")
            parts.append(f"{abstract}")
            parts.append("")
        
        return "\n".join(parts)


# Global instance for session state
_stored_works: list[dict] = []
_author_name: Optional[str] = None


def store_works(works: list[dict], author_name: str = None):
    """Store works for later analysis."""
    global _stored_works, _author_name
    _stored_works = works
    _author_name = author_name
    print(f"📦 Stored {len(works)} works for {author_name or 'unknown author'}")


def get_stored_works() -> tuple[list[dict], Optional[str]]:
    """Get stored works and author name."""
    return _stored_works, _author_name


def clear_stored():
    """Clear stored works."""
    global _stored_works, _author_name
    _stored_works = []
    _author_name = None
