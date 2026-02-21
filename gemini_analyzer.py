"""
LLM Analyzer - Map-Reduce architecture for processing large numbers of abstracts.

Stage 1 (Extract): Process each abstract individually with structured questions
Stage 2 (Synthesize): Query the cached extracts for insights

Provider-agnostic: accepts any BaseLLMAdapter from llm_adapters.py.
"""

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from llm_adapters import BaseLLMAdapter


class LLMAnalyzer:
    """
    Two-stage analysis using any LLM provider:
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

    def __init__(self, adapter: BaseLLMAdapter):
        self.adapter = adapter

    @property
    def model(self) -> str:
        return self.adapter.get_model_name()

    def extract_single(self, work: dict, max_retries: int = 3) -> dict:
        abstract = work.get('abstract')
        if not abstract:
            return {
                'openalex_id': work.get('openalex_id'),
                'error': 'No abstract available',
                'extracted': False,
            }

        prompt = self.EXTRACTION_PROMPT.format(
            abstract=abstract,
            title=work.get('title', 'Unknown'),
            year=work.get('publication_year', 'Unknown'),
        )

        last_error = None
        for attempt in range(max_retries):
            try:
                text = self.adapter.generate(prompt, json_mode=True)
                extracted = json.loads(text)
                return {
                    'openalex_id': work.get('openalex_id'),
                    'title': work.get('title'),
                    'year': work.get('publication_year'),
                    'extracted': True,
                    **extracted,
                }
            except Exception as e:
                last_error = e
                error_str = str(e).lower()
                if '429' in error_str or 'quota' in error_str or 'rate' in error_str or 'resource' in error_str:
                    wait_time = 2 ** (attempt + 1)
                    print(f"⚠️ Rate limit hit, waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    continue
                else:
                    break

        return {
            'openalex_id': work.get('openalex_id'),
            'title': work.get('title'),
            'error': str(last_error),
            'extracted': False,
        }

    def extract_all(
        self,
        works: list[dict],
        max_workers: int = 5,
        requests_per_minute: int = 50,
        progress_callback: Callable[[int, int, str], None] = None,
    ) -> list[dict]:
        works_with_abstracts = [w for w in works if w.get('abstract')]
        total = len(works_with_abstracts)
        if total == 0:
            return []

        results = []
        completed = 0
        lock = threading.Lock()
        min_delay = (60.0 * max_workers) / requests_per_minute

        def process_work(work):
            nonlocal completed
            start_time = time.time()
            result = self.extract_single(work)
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

        print(f"🚀 Starting extraction of {total} abstracts with {self.model}...")
        print(f"   Workers: {max_workers}, Target RPM: {requests_per_minute}, Min delay: {min_delay:.1f}s")
        estimated_time = (total / max_workers) * min_delay
        print(f"   Estimated time: {estimated_time/60:.1f} minutes")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_work, work) for work in works_with_abstracts]
            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    print(f"⚠️ Worker error: {e}")

        results.sort(key=lambda x: x.get('year') or 0, reverse=True)
        success_count = sum(1 for r in results if r.get('extracted'))
        print(f"✓ Extraction complete: {success_count}/{total} successful")
        return results

    def synthesize(self, extracts: list[dict], question: str,
                   author_name: str = None) -> dict:
        valid_extracts = [e for e in extracts if e.get('extracted')]
        if not valid_extracts:
            return {
                "answer": "No extracted data available. Please run extraction first.",
                "extracts_used": 0,
                "model": self.model,
            }

        context = self._build_extract_context(valid_extracts)
        estimated_tokens = int(len(context.split()) * 1.3)

        prompt = f"""Author: {author_name or 'Unknown'}
Total publications analyzed: {len(valid_extracts)}

=== EXTRACTED METADATA FROM ALL PAPERS ===
{context}
=== END EXTRACTS ===

Question: {question}

Synthesize insights based on the extracted metadata above."""

        print(f"📤 Synthesizing from {len(valid_extracts)} extracts ({estimated_tokens} est. tokens) with {self.model}...")
        text = self.adapter.generate(prompt, system_prompt=self.SYNTHESIS_SYSTEM_PROMPT)
        print("✓ Synthesis complete")

        return {
            "answer": text,
            "extracts_used": len(valid_extracts),
            "model": self.model,
            "estimated_tokens": estimated_tokens,
        }

    def analyze(self, question: str, works: list[dict],
                author_name: str = None) -> dict:
        works_with_abstracts = [w for w in works if w.get('abstract')]
        if not works_with_abstracts:
            return {
                "answer": "No abstracts available to analyze.",
                "works_analyzed": 0,
                "total_works": len(works),
                "model": self.model,
            }

        context = self._build_abstract_context(works_with_abstracts)
        estimated_tokens = int(len(context.split()) * 1.3)

        prompt = f"""Author: {author_name or 'Unknown'}
Total publications with abstracts: {len(works_with_abstracts)}

=== ALL ABSTRACTS ===
{context}
=== END ABSTRACTS ===

Question: {question}

Please provide a comprehensive analysis based on ALL the abstracts above."""

        print(f"📤 Sending {len(works_with_abstracts)} abstracts to {self.model} ({estimated_tokens} est. tokens)...")
        text = self.adapter.generate(prompt, system_prompt=self.SYNTHESIS_SYSTEM_PROMPT)
        print("✓ Analysis complete")

        return {
            "answer": text,
            "works_analyzed": len(works_with_abstracts),
            "total_works": len(works),
            "model": self.model,
            "estimated_tokens": estimated_tokens,
        }

    # ── helpers ──────────────────────────────────────────────

    @staticmethod
    def _build_extract_context(extracts: list[dict]) -> str:
        parts = []
        for i, ext in enumerate(extracts, 1):
            lines = [f"[{i}] {ext.get('title', 'Untitled')} ({ext.get('year', 'N/A')})"]
            lines.append(f"  Theme: {ext.get('theme', 'N/A')}")
            lines.append(f"  Method: {ext.get('methodology', 'N/A')}")
            lines.append(f"  Finding: {ext.get('finding', 'N/A')}")
            lines.append(f"  Type: {ext.get('study_type', 'N/A')} | Evidence Level: {ext.get('evidence_level', 'N/A')} | Novelty: {ext.get('novelty', 'N/A')}")
            if ext.get('population'):
                lines.append(f"  Population: {ext['population']}")
            if ext.get('intervention'):
                lines.append(f"  Intervention: {ext['intervention']}")
            if ext.get('sample_size') and ext['sample_size'] != 'N/A':
                lines.append(f"  Sample: {ext['sample_size']}")
            if ext.get('drugs_studied'):
                lines.append(f"  Drugs: {', '.join(ext['drugs_studied'])}")
            if ext.get('conditions'):
                lines.append(f"  Conditions: {', '.join(ext['conditions'])}")
            if ext.get('biomarkers'):
                lines.append(f"  Biomarkers: {', '.join(ext['biomarkers'])}")
            if ext.get('clinical_implication'):
                lines.append(f"  Clinical Implication: {ext['clinical_implication']}")
            if ext.get('limitations'):
                lines.append(f"  Limitations: {ext['limitations']}")
            lines.append(f"  Keywords: {', '.join(ext.get('keywords', []))}")
            parts.append("\n".join(lines))
        return "\n\n".join(parts)

    @staticmethod
    def _build_abstract_context(works: list[dict]) -> str:
        sorted_works = sorted(works, key=lambda w: w.get('publication_year') or 0, reverse=True)
        parts = []
        for i, work in enumerate(sorted_works, 1):
            parts.append(f"[{i}] {work.get('title', 'Untitled')} ({work.get('publication_year', 'N/A')})")
            parts.append(work.get('abstract', ''))
            parts.append("")
        return "\n".join(parts)


# Backwards-compatible alias
GeminiAnalyzer = LLMAnalyzer
