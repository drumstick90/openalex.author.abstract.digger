"""
Gemini Analyzer - Map-Reduce architecture for processing large numbers of abstracts.

Stage 1 (Extract): Process each abstract individually with structured questions
Stage 2 (Synthesize): Query the cached extracts for insights
"""

import json
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Callable


class GeminiAnalyzer:
    """
    Two-stage analysis using Gemini:
    1. Extract: Per-abstract structured extraction (parallel)
    2. Synthesize: Query cached extracts for insights
    """
    
    EXTRACTION_PROMPT = """You are an expert research analyst. Analyze this academic abstract and extract comprehensive structured information for a graduate-level literature review.

Abstract:
{abstract}

Title: {title}
Year: {year}

Extract ALL of the following fields as JSON. Use null for fields that cannot be determined from the abstract.

{{
  // CORE FIELDS
  "theme": "Main research theme in 3-5 words",
  "methodology": "Research approach/method in a short phrase",
  "finding": "Key finding or contribution in 1 sentence",
  "study_type": "One of: experimental, review, clinical, computational, meta-analysis, theoretical, case-report, other",
  "keywords": ["3-5 relevant keywords"],
  
  // PICO FRAMEWORK (for clinical/empirical studies)
  "population": "Who/what was studied (e.g., 'adult males with BPH', 'cancer cell lines') or null",
  "intervention": "What was tested/applied/measured or null",
  "comparison": "Control or comparison group if any, or null",
  "outcome": "Primary outcome or endpoint measured",
  "sample_size": "n=X, or 'not specified', or 'N/A' for reviews/theoretical",
  "evidence_level": "Integer 1-5 where: 1=systematic review/meta-analysis, 2=RCT, 3=cohort/case-control, 4=case series/case report, 5=expert opinion/theoretical",
  
  // RESEARCH CHARACTERIZATION
  "novelty": "One of: novel (first to report), replication (confirming prior work), incremental (extending prior work), synthesis (combining existing knowledge)",
  "limitations": "Key limitation mentioned in abstract, or null if none stated",
  "clinical_implication": "Actionable clinical takeaway, or null if basic science/no clinical relevance",
  
  // ENTITY EXTRACTION
  "drugs_studied": ["List specific drug/compound/supplement names mentioned, empty array if none"],
  "conditions": ["List diseases/syndromes/conditions studied, empty array if none"],
  "biomarkers": ["List biomarkers/lab values/measurements if any, empty array if none"],
  "outcomes_measured": ["List specific outcome variables/endpoints measured"]
}}

Return ONLY the valid JSON object, no other text or markdown."""

    SYNTHESIS_SYSTEM_PROMPT = """You are a research analyst synthesizing insights from comprehensive extracted metadata of an academic author's publications.

You have access to structured extracts from ALL papers, each containing:

CORE: theme, methodology, finding, study_type, keywords
PICO: population, intervention, comparison, outcome, sample_size, evidence_level (1-5 scale)
RESEARCH: novelty (novel/replication/incremental/synthesis), limitations, clinical_implication
ENTITIES: drugs_studied, conditions, biomarkers, outcomes_measured

Evidence Level Scale:
- Level 1: Systematic review / meta-analysis (strongest)
- Level 2: Randomized controlled trial
- Level 3: Cohort or case-control study
- Level 4: Case series / case report
- Level 5: Expert opinion / theoretical (weakest)

Guidelines:
1. Synthesize patterns across the ENTIRE body of work
2. Consider evidence levels when assessing research strength
3. Identify research trajectories, methodological evolution, and thematic shifts over time
4. Note common limitations across studies
5. Highlight key drugs, conditions, and biomarkers studied
6. Be direct and concise - no hype or flourishes
7. Do NOT cite specific paper titles unless asked

Keep responses under 1500 characters unless more detail is requested."""

    # Preferred models in order (best first)
    PREFERRED_MODELS = [
        "gemini-2.0-flash-exp",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
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
        self.genai = genai
        
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
    
    def extract_single(self, work: dict, max_retries: int = 3) -> dict:
        """
        Extract structured data from a single abstract.
        
        Args:
            work: Work record with 'abstract', 'title', 'publication_year', 'openalex_id'
            max_retries: Number of retries for rate limit errors
            
        Returns:
            Dict with extracted fields or error info
        """
        import time
        
        abstract = work.get('abstract')
        if not abstract:
            return {
                'openalex_id': work.get('openalex_id'),
                'error': 'No abstract available',
                'extracted': False
            }
        
        prompt = self.EXTRACTION_PROMPT.format(
            abstract=abstract,
            title=work.get('title', 'Unknown'),
            year=work.get('publication_year', 'Unknown')
        )
        
        last_error = None
        for attempt in range(max_retries):
            try:
                model = self.genai.GenerativeModel(
                    model_name=self.model,
                    generation_config={"response_mime_type": "application/json"}
                )
                
                response = model.generate_content(prompt)
                extracted = json.loads(response.text)
                
                return {
                    'openalex_id': work.get('openalex_id'),
                    'title': work.get('title'),
                    'year': work.get('publication_year'),
                    'extracted': True,
                    **extracted
                }
                
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                
                # Check for rate limit errors (429 or "quota" or "rate")
                if '429' in error_str or 'quota' in error_str or 'rate' in error_str or 'resource' in error_str:
                    # Exponential backoff: 2s, 4s, 8s
                    wait_time = 2 ** (attempt + 1)
                    print(f"⚠️ Rate limit hit, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                else:
                    # Non-rate-limit error, don't retry
                    break
        
        return {
            'openalex_id': work.get('openalex_id'),
            'title': work.get('title'),
            'error': str(last_error),
            'extracted': False
        }
    
    def extract_all(
        self,
        works: list[dict],
        max_workers: int = 5,
        requests_per_minute: int = 50,
        progress_callback: Callable[[int, int, str], None] = None
    ) -> list[dict]:
        """
        Extract structured data from all abstracts in parallel with rate limiting.
        
        Args:
            works: List of work records
            max_workers: Number of concurrent threads (default 5)
            requests_per_minute: Target RPM to stay under rate limits (default 50)
            progress_callback: Optional callback(completed, total, message)
            
        Returns:
            List of extracted records
        """
        import time
        
        # Filter to works with abstracts
        works_with_abstracts = [w for w in works if w.get('abstract')]
        total = len(works_with_abstracts)
        
        if total == 0:
            return []
        
        results = []
        completed = 0
        lock = threading.Lock()
        
        # Rate limiting: calculate delay between requests
        # With N workers and target RPM, each worker should wait (60 * N / RPM) seconds
        min_delay = (60.0 * max_workers) / requests_per_minute
        
        def process_work(work):
            nonlocal completed
            start_time = time.time()
            
            result = self.extract_single(work)
            
            # Enforce minimum delay to respect rate limits
            elapsed = time.time() - start_time
            if elapsed < min_delay:
                time.sleep(min_delay - elapsed)
            
            with lock:
                completed += 1
                results.append(result)
                
                if progress_callback:
                    title = work.get('title', 'Unknown')[:40]
                    status = "✓" if result.get('extracted') else "⚠️"
                    progress_callback(completed, total, f"{status} {title}...")
            
            return result
        
        print(f"🚀 Starting extraction of {total} abstracts...")
        print(f"   Workers: {max_workers}, Target RPM: {requests_per_minute}, Min delay: {min_delay:.1f}s")
        
        estimated_time = (total / max_workers) * min_delay
        print(f"   Estimated time: {estimated_time/60:.1f} minutes")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_work, work) for work in works_with_abstracts]
            
            # Wait for all to complete
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"⚠️ Worker error: {e}")
        
        # Sort by year (newest first) for consistent ordering
        results.sort(key=lambda x: x.get('year') or 0, reverse=True)
        
        success_count = sum(1 for r in results if r.get('extracted'))
        print(f"✓ Extraction complete: {success_count}/{total} successful")
        
        return results
    
    def synthesize(
        self,
        extracts: list[dict],
        question: str,
        author_name: str = None
    ) -> dict:
        """
        Synthesize insights from cached extracts.
        
        Args:
            extracts: List of extracted records from extract_all()
            question: User's question
            author_name: Optional author name for context
            
        Returns:
            Dict with 'answer', 'extracts_used', 'model'
        """
        # Filter to successful extracts
        valid_extracts = [e for e in extracts if e.get('extracted')]
        
        if not valid_extracts:
            return {
                "answer": "No extracted data available. Please run extraction first.",
                "extracts_used": 0,
                "model": self.model
            }
        
        # Build context from extracts (much smaller than raw abstracts!)
        context_parts = []
        for i, ext in enumerate(valid_extracts, 1):
            # Core fields
            parts = [f"[{i}] {ext.get('title', 'Untitled')} ({ext.get('year', 'N/A')})"]
            parts.append(f"  Theme: {ext.get('theme', 'N/A')}")
            parts.append(f"  Method: {ext.get('methodology', 'N/A')}")
            parts.append(f"  Finding: {ext.get('finding', 'N/A')}")
            parts.append(f"  Type: {ext.get('study_type', 'N/A')} | Evidence Level: {ext.get('evidence_level', 'N/A')} | Novelty: {ext.get('novelty', 'N/A')}")
            
            # PICO (if available)
            if ext.get('population'):
                parts.append(f"  Population: {ext.get('population')}")
            if ext.get('intervention'):
                parts.append(f"  Intervention: {ext.get('intervention')}")
            if ext.get('sample_size') and ext.get('sample_size') != 'N/A':
                parts.append(f"  Sample: {ext.get('sample_size')}")
            
            # Entities (if available)
            if ext.get('drugs_studied'):
                parts.append(f"  Drugs: {', '.join(ext.get('drugs_studied', []))}")
            if ext.get('conditions'):
                parts.append(f"  Conditions: {', '.join(ext.get('conditions', []))}")
            if ext.get('biomarkers'):
                parts.append(f"  Biomarkers: {', '.join(ext.get('biomarkers', []))}")
            
            # Clinical implication
            if ext.get('clinical_implication'):
                parts.append(f"  Clinical Implication: {ext.get('clinical_implication')}")
            
            # Limitations
            if ext.get('limitations'):
                parts.append(f"  Limitations: {ext.get('limitations')}")
            
            # Keywords
            parts.append(f"  Keywords: {', '.join(ext.get('keywords', []))}")
            
            context_parts.append("\n".join(parts))
        
        context = "\n\n".join(context_parts)
        
        # Estimate tokens (extracts are much more compact)
        estimated_tokens = int(len(context.split()) * 1.3)
        
        model = self.genai.GenerativeModel(
            model_name=self.model,
            system_instruction=self.SYNTHESIS_SYSTEM_PROMPT
        )
        
        prompt = f"""Author: {author_name or 'Unknown'}
Total publications analyzed: {len(valid_extracts)}

=== EXTRACTED METADATA FROM ALL PAPERS ===
{context}
=== END EXTRACTS ===

Question: {question}

Synthesize insights based on the extracted metadata above."""

        print(f"📤 Synthesizing from {len(valid_extracts)} extracts ({estimated_tokens} est. tokens)...")
        
        response = model.generate_content(
            prompt,
            generation_config=self.genai.types.GenerationConfig(temperature=0.5)
        )
        
        print(f"✓ Synthesis complete")
        
        return {
            "answer": response.text,
            "extracts_used": len(valid_extracts),
            "model": self.model,
            "estimated_tokens": estimated_tokens
        }
    
    def analyze(
        self,
        question: str,
        works: list[dict],
        author_name: str = None
    ) -> dict:
        """
        Legacy method: Analyze ALL abstracts directly (no caching).
        Use synthesize() with cached extracts for better performance.
        
        Args:
            question: User's question
            works: ALL work records 
            author_name: Author's name for context
            
        Returns:
            Dict with 'answer', 'works_analyzed', 'model', etc.
        """
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
        model = self.genai.GenerativeModel(
            model_name=self.model,
            system_instruction=self.SYNTHESIS_SYSTEM_PROMPT
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
            generation_config=self.genai.types.GenerationConfig(temperature=0.5)
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


# ============================================================================
# Global State Management
# ============================================================================

_stored_works: list[dict] = []
_author_name: Optional[str] = None
_author_id: Optional[str] = None
_cached_extracts: list[dict] = []
_extraction_in_progress: bool = False


def store_works(works: list[dict], author_name: str = None, author_id: str = None):
    """Store works for later analysis."""
    global _stored_works, _author_name, _author_id, _cached_extracts
    _stored_works = works
    _author_name = author_name
    _author_id = author_id
    _cached_extracts = []  # Clear cache when new works are stored
    print(f"📦 Stored {len(works)} works for {author_name or 'unknown author'}")


def get_stored_works() -> tuple[list[dict], Optional[str]]:
    """Get stored works and author name."""
    return _stored_works, _author_name


def get_cached_extracts() -> list[dict]:
    """Get cached extracts."""
    return _cached_extracts


def set_cached_extracts(extracts: list[dict]):
    """Set cached extracts."""
    global _cached_extracts
    _cached_extracts = extracts
    print(f"💾 Cached {len(extracts)} extracts")


def is_extraction_in_progress() -> bool:
    """Check if extraction is currently running."""
    return _extraction_in_progress


def set_extraction_in_progress(value: bool):
    """Set extraction in progress flag."""
    global _extraction_in_progress
    _extraction_in_progress = value


def clear_stored():
    """Clear stored works and cache."""
    global _stored_works, _author_name, _author_id, _cached_extracts
    _stored_works = []
    _author_name = None
    _author_id = None
    _cached_extracts = []


def get_extraction_cache_path(author_id: str = None) -> str:
    """Get path to temp file for extraction cache."""
    aid = author_id or _author_id or "unknown"
    return os.path.join(tempfile.gettempdir(), f"openalex_extracts_{aid}.json")


def save_extracts_to_file(extracts: list[dict], author_id: str = None):
    """Save extracts to temp file."""
    path = get_extraction_cache_path(author_id)
    with open(path, 'w') as f:
        json.dump({
            'author_id': author_id or _author_id,
            'author_name': _author_name,
            'extracts': extracts,
            'count': len(extracts)
        }, f)
    print(f"💾 Saved {len(extracts)} extracts to {path}")
    return path


def load_extracts_from_file(author_id: str = None) -> list[dict]:
    """Load extracts from temp file if it exists."""
    path = get_extraction_cache_path(author_id)
    try:
        with open(path, 'r') as f:
            data = json.load(f)
            return data.get('extracts', [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []
