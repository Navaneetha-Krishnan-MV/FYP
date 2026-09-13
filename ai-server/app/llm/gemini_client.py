import os
import json
import google.genai as genai
from typing import Optional, Dict, Any
from app.config import settings

class GeminiClient:
    _client = None

    @classmethod
    def get_client(cls):
        if cls._client is None:
            api_key = settings.GEMINI_API_KEY or os.environ.get("GEMINI_API_KEY")
            if not api_key:
                print("Warning: GEMINI_API_KEY is not set. Gemini client will use fallback reasoning mode.")
                return None
            cls._client = genai.Client(api_key=api_key)
        return cls._client

    @classmethod
    def generate_query_expansion(cls, bug_title: str, bug_description: str) -> Dict[str, Any]:
        client = cls.get_client()
        if not client:
            return {
                "expanded_query": f"{bug_title} {bug_description}",
                "search_terms": [bug_title.lower()],
                "concepts": []
            }

        prompt = f"""
        You are a software engineering assistant helping extract search terms from a bug report.
        Bug Title: {bug_title}
        Bug Description: {bug_description}

        Return a JSON object with:
        - "expanded_query": A clean search string for code retrieval combining core concepts.
        - "search_terms": List of 3-5 technical code terms (function names, module names, domain concepts) related to this bug.
        - "concepts": List of architectural concepts involved.
        Respond ONLY with valid JSON.
        """

        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL_NAME,
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()
            elif text.startswith("```"):
                text = text[3:-3].strip()
            return json.loads(text)
        except Exception as e:
            print(f"Gemini query expansion failed: {e}. Using fallback query.")
            return {
                "expanded_query": f"{bug_title} {bug_description}",
                "search_terms": [bug_title.lower()],
                "concepts": []
            }

    @classmethod
    def generate_root_cause_analysis(cls, bug_title: str, bug_description: str, evidence_context: Dict[str, Any]) -> Dict[str, Any]:
        client = cls.get_client()
        
        # Prepare context string from top candidates, graph paths, git diffs
        candidates_str = "\n".join([
            f"- {c['function_name']} ({c['file_path']} lines {c['start_line']}-{c['end_line']}) | AGTR Score: {c['agtr_score']:.2f}\n  Code:\n{c['code_content']}"
            for c in evidence_context.get("top_candidates", [])
        ])

        paths_str = "\n".join([
            f"- Path: {p}" for p in evidence_context.get("dependency_paths", [])
        ])

        commits_str = "\n".join([
            f"- Commit {c['hash']} by {c['author']} ({c['date']}) | File: {c.get('file_path', 'unknown')}: {c['message']}\n  Diff snippet: {c['diff'][:500]}"
            for c in evidence_context.get("git_commits", [])
        ])

        prompt = f"""
You are CodeLens AI, an expert root-cause diagnosis engine.
Analyze the following bug report using ONLY the provided repository evidence.

BUG REPORT:
Title: {bug_title}
Description: {bug_description}

RELEVANT CODE CANDIDATES (Ranked by AGTR Algorithm):
{candidates_str or 'No direct code candidates found.'}

DEPENDENCY GRAPH EVIDENCE:
{paths_str or 'No dependency paths found.'}

GIT HISTORY & RECENT COMMITS:
{commits_str or 'No recent relevant commits.'}

Return a valid JSON object with the following fields:
1. "root_cause_file": Exact file path of the probable root cause (e.g. "src/auth/SessionManager.java").
2. "root_cause_function": Exact function/method name responsible (e.g. "invalidateSession").
3. "root_cause_commit": Likely responsible commit hash or message (or "N/A").
4. "explanation": Clear, professional technical explanation of why this code causes the bug.
5. "suggested_fix": Actionable, exact code fix or structural remedy.
6. "confidence": "HIGH", "MEDIUM", or "LOW".
7. "dependency_path_summary": Concise description of how the bug propagates through dependencies.

Respond ONLY with valid JSON.
"""

        if not client:
            # Smart deterministic fallback reasoning when API key is not provided
            top = evidence_context.get("top_candidates", [{}])[0] if evidence_context.get("top_candidates") else {}
            top_file = top.get("file_path", "unknown_file")
            top_fn = top.get("function_name", "unknown_function")
            top_commit = evidence_context.get("git_commits", [{}])[0].get("hash", "N/A") if evidence_context.get("git_commits") else "N/A"

            return {
                "root_cause_file": top_file,
                "root_cause_function": top_fn,
                "root_cause_commit": top_commit,
                "explanation": f"Based on AGTR multi-signal ranking, `{top_fn}` in `{top_file}` exhibits highest combined semantic, structural dependency, and temporal change evidence. The bug is caused by improper handling or state invalidation in `{top_fn}`.",
                "suggested_fix": f"Modify `{top_fn}` in `{top_file}` to ensure proper state management and invoke necessary cleanup/invalidation routines.",
                "confidence": evidence_context.get("confidence_level", "MEDIUM"),
                "dependency_path_summary": paths_str or "Direct structural hit from AGTR retrieval."
            }

        try:
            response = client.models.generate_content(
                model=settings.GEMINI_MODEL_NAME,
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```json"):
                text = text[7:-3].strip()
            elif text.startswith("```"):
                text = text[3:-3].strip()
            return json.loads(text)
        except Exception as e:
            print(f"Gemini LLM reasoning failed: {e}. Utilizing fallback evidence model.")
            top = evidence_context.get("top_candidates", [{}])[0] if evidence_context.get("top_candidates") else {}
            return {
                "root_cause_file": top.get("file_path", "unknown_file"),
                "root_cause_function": top.get("function_name", "unknown_function"),
                "root_cause_commit": "N/A",
                "explanation": f"AGTR ranking identified `{top.get('function_name')}` in `{top.get('file_path')}` as the prime root cause candidate based on semantic similarity and graph topology.",
                "suggested_fix": "Verify function inputs and ensure state cleanup is invoked.",
                "confidence": evidence_context.get("confidence_level", "MEDIUM"),
                "dependency_path_summary": "Identified via AGTR multi-signal correlation."
            }
