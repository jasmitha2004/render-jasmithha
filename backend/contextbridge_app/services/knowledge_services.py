"""
Knowledge extraction, gap detection, readiness, and Q&A services.
Falls back to deterministic rule-based extraction when Anthropic key is absent.
"""
import json
import logging
import re
import os
from pathlib import Path
from typing import List, Dict, Any, Optional

from django.conf import settings

logger = logging.getLogger('contextbridge.ai')

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_text_from_file(file_path: str, file_type: str) -> tuple[str, int]:
    """Return (full_text, page_count)."""
    path = Path(file_path)
    if not path.exists():
        return "", 0

    file_type = file_type.lower().lstrip('.')
    if file_type in ('txt', 'text'):
        text = path.read_text(encoding='utf-8', errors='ignore')
        return text, 1

    if file_type == 'pdf' and fitz:
        doc = fitz.open(file_path)
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return "\n\n".join(pages), len(pages)

    if file_type in ('docx', 'doc') and DocxDocument:
        doc = DocxDocument(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        return "\n\n".join(paragraphs), max(1, len(paragraphs) // 30)

    # Fallback: try reading as text
    try:
        return path.read_text(encoding='utf-8', errors='ignore'), 1
    except Exception:
        return "", 0


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 100) -> List[str]:
    """Simple sliding-window chunking."""
    if not text:
        return []
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


# ---------------------------------------------------------------------------
# Rule-based extraction (MVP fallback)
# ---------------------------------------------------------------------------

DECISION_PATTERNS = [
    r'(?i)(?:we\s+)?(?:decided|decision|chose|selected|approved)\s+(?:to\s+)?(.{20,120})',
    r'(?i)decision[:\s]+(.{20,120})',
    r'(?i)(?:final\s+)?(?:choice|option)\s*:\s*(.{15,100})',
]

TASK_PATTERNS = [
    r'(?i)(?:todo|task|action\s*item|must\s+do|need\s+to)\s*[:\-]?\s*(.{15,120})',
    r'(?i)(?:assignee|owner)\s*:\s*(\w+).{0,40}(?:task|work|implement)',
    r'(?i)(?:will|should|must)\s+(?:implement|complete|finish|migrate|update)\s+(.{15,100})',
]

RISK_PATTERNS = [
    r'(?i)(?:risk|concern|blocker|issue|threat)\s*[:\-]?\s*(.{20,150})',
    r'(?i)(?:high|medium|low|critical)\s+risk\s*[:\-]?\s*(.{15,120})',
    r'(?i)(?:potential|possible)\s+(?:delay|failure|outage|loss)\s+(.{15,100})',
]


def _extract_with_patterns(text: str, patterns: List[str], limit: int = 15) -> List[str]:
    found = []
    seen = set()
    for pat in patterns:
        for m in re.finditer(pat, text):
            item = m.group(1).strip()
            # Clean trailing punctuation / newlines
            item = re.sub(r'[\n\r]+', ' ', item)
            item = re.sub(r'\s+', ' ', item).strip(' .,;:')
            key = item.lower()[:60]
            if key not in seen and len(item) > 12:
                seen.add(key)
                found.append(item)
                if len(found) >= limit:
                    return found
    return found


def extract_decisions(text: str) -> List[Dict[str, Any]]:
    items = _extract_with_patterns(text, DECISION_PATTERNS)
    results = []
    for i, title in enumerate(items):
        results.append({
            'title': title[:200],
            'description': title,
            'rationale': '',
            'decided_by': '',
            'decided_at': '',
            'confidence': 0.65,
        })
    return results


def extract_tasks(text: str) -> List[Dict[str, Any]]:
    items = _extract_with_patterns(text, TASK_PATTERNS)
    results = []
    for title in items:
        results.append({
            'title': title[:200],
            'description': title,
            'assignee': '',
            'status': 'pending',
            'due_date': '',
        })
    return results


def extract_risks(text: str) -> List[Dict[str, Any]]:
    items = _extract_with_patterns(text, RISK_PATTERNS)
    results = []
    for title in items:
        severity = 'medium'
        low = title.lower()
        if any(w in low for w in ('critical', 'severe', 'blocker', 'outage')):
            severity = 'high'
        elif any(w in low for w in ('minor', 'low')):
            severity = 'low'
        results.append({
            'title': title[:200],
            'description': title,
            'severity': severity,
            'mitigation': '',
            'owner': '',
        })
    return results


# ---------------------------------------------------------------------------
# Knowledge gap detection
# ---------------------------------------------------------------------------

COMPETING_TECH = {
    'database': ['mongodb', 'postgres', 'mysql', 'dynamodb', 'cassandra'],
    'message broker': ['kafka', 'rabbitmq', 'sqs', 'pulsar'],
    'cloud provider': ['aws', 'azure', 'gcp'],
}


class KnowledgeGapDetector:
    """Detect missing ownership, rationale, dates, and conflicting decisions."""

    def detect(self, project) -> List[Dict[str, Any]]:
        gaps = []
        decisions = list(project.decisions.all())
        tasks = list(project.tasks.all())
        risks = list(project.risks.all())

        # Missing rationale
        for d in decisions:
            if not (d.rationale or '').strip():
                gaps.append({
                    'title': f'Missing rationale for decision: {d.title[:80]}',
                    'description': 'Decision recorded without supporting rationale or context.',
                    'category': 'decision_quality',
                    'severity': 'medium',
                    'suggested_action': 'Interview original decision makers and document the why.',
                })

        # Missing ownership on tasks
        for t in tasks:
            if not (t.assignee or '').strip():
                gaps.append({
                    'title': f'Unassigned task: {t.title[:80]}',
                    'description': 'Task has no clear owner.',
                    'category': 'ownership',
                    'severity': 'high',
                    'suggested_action': 'Assign an owner before handover.',
                })

        # Missing mitigation on high risks
        for r in risks:
            if r.severity in ('high', 'critical') and not (r.mitigation or '').strip():
                gaps.append({
                    'title': f'No mitigation for {r.severity} risk: {r.title[:60]}',
                    'description': 'High-severity risk lacks a documented mitigation plan.',
                    'category': 'risk',
                    'severity': 'high',
                    'suggested_action': 'Define and document mitigation steps.',
                })

        # Conflicting technology decisions: two competing options from the same family
        # both appear in decision titles (generalised from the old MongoDB/Postgres special case).
        titles = ' '.join(d.title.lower() for d in decisions)
        for family, options in COMPETING_TECH.items():
            present = [o for o in options if o in titles]
            if len(present) > 1:
                gaps.append({
                    'title': f'Conflicting {family} decisions: {" vs ".join(present)}',
                    'description': f'Multiple {family} technologies appear as selected options. Clarify which is authoritative for which domain.',
                    'category': 'conflicting_decision',
                    'severity': 'critical',
                    'suggested_action': 'Resolve the architecture decision and update documentation.',
                })

        # No documents processed
        if project.documents.filter(processed=True).count() == 0:
            gaps.append({
                'title': 'No processed documents',
                'description': 'Project has no extracted knowledge yet.',
                'category': 'coverage',
                'severity': 'high',
                'suggested_action': 'Upload and process project documents.',
            })

        return gaps


# ---------------------------------------------------------------------------
# Readiness calculator (fixed dependency clarity)
# ---------------------------------------------------------------------------

class ReadinessCalculator:
    """Compute handover readiness score with category breakdown."""

    def calculate(self, project) -> Dict[str, Any]:
        decisions = project.decisions.count()
        tasks = list(project.tasks.all())
        risks = list(project.risks.all())
        gaps = project.knowledge_gaps.count()
        docs_processed = project.documents.filter(processed=True).count()
        total_docs = project.documents.count()

        # Documentation coverage
        doc_score = 0.0
        if total_docs > 0:
            doc_score = (docs_processed / total_docs) * 100
        elif decisions + len(tasks) + len(risks) > 0:
            doc_score = 40.0  # some knowledge exists without docs

        # Decision quality (has rationale)
        decision_score = 0.0
        if decisions > 0:
            with_rationale = project.decisions.exclude(rationale='').count()
            decision_score = (with_rationale / decisions) * 100
        else:
            decision_score = 30.0  # no decisions is weak

        # Ownership clarity
        ownership_score = 0.0
        if tasks:
            assigned = sum(1 for t in tasks if (t.assignee or '').strip())
            ownership_score = (assigned / len(tasks)) * 100
        else:
            ownership_score = 50.0

        # Risk mitigation
        risk_score = 100.0
        if risks:
            mitigated = sum(1 for r in risks if (r.mitigation or '').strip() or r.severity == 'low')
            risk_score = (mitigated / len(risks)) * 100

        # Dependency clarity — FIXED: only count tasks that actually declare depends_on
        dep_score = 100.0
        if tasks:
            # Score higher when dependencies are explicitly recorded for non-trivial work
            with_deps = sum(1 for t in tasks if t.depends_on.exists())
            # If many tasks exist but zero dependencies recorded, lower the score
            if len(tasks) >= 3 and with_deps == 0:
                dep_score = 40.0
            elif with_deps > 0:
                dep_score = min(100.0, 60 + (with_deps / len(tasks)) * 40)
            else:
                dep_score = 70.0  # small task set, assume ok

        # Knowledge gaps penalty
        gap_penalty = min(40.0, gaps * 8)

        weights = {
            'documentation': 0.25,
            'decisions': 0.20,
            'ownership': 0.20,
            'risk_mitigation': 0.15,
            'dependency_clarity': 0.10,
            'gap_penalty': 0.10,
        }

        raw = (
            doc_score * weights['documentation']
            + decision_score * weights['decisions']
            + ownership_score * weights['ownership']
            + risk_score * weights['risk_mitigation']
            + dep_score * weights['dependency_clarity']
        )
        overall = max(0.0, min(100.0, raw - gap_penalty * weights['gap_penalty'] * 10))

        return {
            'overall_score': round(overall, 1),
            'categories': {
                'documentation': round(doc_score, 1),
                'decision_quality': round(decision_score, 1),
                'ownership_clarity': round(ownership_score, 1),
                'risk_mitigation': round(risk_score, 1),
                'dependency_clarity': round(dep_score, 1),
            },
            'gap_count': gaps,
            'recommendation': self._recommendation(overall),
        }

    def _recommendation(self, score: float) -> str:
        if score >= 80:
            return 'Project is well prepared for handover.'
        if score >= 60:
            return 'Moderate readiness. Address open ownership and high-severity gaps before handover.'
        if score >= 40:
            return 'Significant gaps remain. Complete missing rationales, owners, and risk mitigations.'
        return 'Not ready for handover. Process documents and close critical knowledge gaps first.'


# ---------------------------------------------------------------------------
# Simple keyword Q&A
# ---------------------------------------------------------------------------

def answer_question(project, question: str, top_k: int = 5, claude: Optional["ClaudeExtractionService"] = None) -> Dict[str, Any]:
    """Local keyword match over document chunks. Returns evidence-backed reply."""
    q_tokens = set(re.findall(r'\w+', question.lower()))
    if not q_tokens:
        return {
            'answer': 'Please ask a more specific question.',
            'mode': 'local_keyword_match',
            'evidence': [],
        }

    scored = []
    for chunk in project.chunks.all():
        content_lower = chunk.content.lower()
        hits = sum(1 for t in q_tokens if t in content_lower and len(t) > 2)
        if hits > 0:
            scored.append((hits, chunk))

    scored.sort(key=lambda x: -x[0])
    evidence = []
    for hits, chunk in scored[:top_k]:
        evidence.append({
            'excerpt': chunk.content[:400] + ('...' if len(chunk.content) > 400 else ''),
            'document': chunk.document.filename if chunk.document_id else 'unknown',
            'page': chunk.page_number,
            'score': hits,
        })

    if not evidence:
        return {
            'answer': 'No matching evidence found in the processed documents. Try different keywords or process more documents first.',
            'mode': 'local_keyword_match',
            'evidence': [],
        }

    claude = claude or ClaudeExtractionService()
    if claude.available:
        try:
            return {'answer': claude.answer(question, evidence), 'mode': MODE_CLAUDE, 'evidence': evidence}
        except Exception as exc:
            logger.warning('Claude Q&A failed (%s); returning local evidence.', type(exc).__name__)
            fallback_mode = MODE_FALLBACK
    else:
        fallback_mode = 'local_keyword_match'

    answer_parts = [f"Found {len(evidence)} relevant excerpt(s):"]
    for i, ev in enumerate(evidence, 1):
        answer_parts.append(f"\n[{i}] ({ev['document']}, p.{ev['page']}): {ev['excerpt']}")

    return {
        'answer': '\n'.join(answer_parts),
        'mode': fallback_mode,
        'evidence': evidence,
    }


# ---------------------------------------------------------------------------
# Claude (optional). Every code path that can use it reports which mode ran.
# ---------------------------------------------------------------------------

MODE_RULES = 'rule_based'
MODE_CLAUDE = 'claude'
MODE_FALLBACK = 'rule_based_fallback'   # Claude was configured but failed

_EXTRACTION_PROMPT = """You extract structured project knowledge from a document.
Return ONLY a JSON object (no prose, no markdown fences) with this shape:
{
 "decisions": [{"title": str, "rationale": str, "decided_by": str, "decided_at": str}],
 "tasks": [{"title": str, "assignee": str, "status": "pending|in_progress|done|blocked", "due_date": str}],
 "risks": [{"title": str, "severity": "low|medium|high|critical", "mitigation": str, "owner": str}]
}
Rules: only include items explicitly supported by the text. Use "" for unknown fields; never invent names,
dates or rationales. Maximum 15 items per list."""


def _clip(value: Any, n: int) -> str:
    return str(value or '').strip()[:n]


class ClaudeExtractionService:
    """Optional Anthropic-backed extraction and Q&A. Used only when a key is present."""

    def __init__(self):
        self.api_key = getattr(settings, 'ANTHROPIC_API_KEY', '') or os.getenv('ANTHROPIC_API_KEY', '')
        self.model = getattr(settings, 'ANTHROPIC_MODEL', 'claude-sonnet-4-5')
        self.timeout = getattr(settings, 'ANTHROPIC_TIMEOUT', 30.0)
        self.client = None
        if self.api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key, timeout=self.timeout, max_retries=1)
            except Exception:
                logger.warning('Anthropic client failed to initialise; using rule-based mode.')
                self.client = None

    @property
    def available(self) -> bool:
        return self.client is not None

    def list_models(self) -> List[str]:
        if not self.client:
            return []
        try:
            models = self.client.models.list()
            return [m.id for m in models.data]
        except Exception:
            return []

    def _complete(self, system: str, user: str, max_tokens: int = 2000) -> str:
        msg = self.client.messages.create(
            model=self.model, max_tokens=max_tokens, system=system,
            messages=[{'role': 'user', 'content': user}],
        )
        return ''.join(b.text for b in msg.content if getattr(b, 'type', '') == 'text')

    def extract(self, text: str) -> Dict[str, List[Dict[str, Any]]]:
        """Return validated decisions/tasks/risks dicts. Raises on any failure (caller falls back)."""
        raw = self._complete(_EXTRACTION_PROMPT, text[:30000]).strip()
        raw = re.sub(r'^```(?:json)?|```$', '', raw, flags=re.M).strip()
        data = json.loads(raw)

        decisions = [{
            'title': _clip(d.get('title'), 200), 'description': _clip(d.get('title'), 1000),
            'rationale': _clip(d.get('rationale'), 1000), 'decided_by': _clip(d.get('decided_by'), 255),
            'decided_at': _clip(d.get('decided_at'), 100), 'confidence': 0.85,
        } for d in (data.get('decisions') or [])[:15] if isinstance(d, dict) and d.get('title')]

        tasks = []
        for t in (data.get('tasks') or [])[:15]:
            if not (isinstance(t, dict) and t.get('title')):
                continue
            st = t.get('status') if t.get('status') in ('pending', 'in_progress', 'done', 'blocked') else 'pending'
            tasks.append({
                'title': _clip(t['title'], 200), 'description': _clip(t['title'], 1000),
                'assignee': _clip(t.get('assignee'), 255), 'status': st,
                'due_date': _clip(t.get('due_date'), 100),
            })

        risks = []
        for r in (data.get('risks') or [])[:15]:
            if not (isinstance(r, dict) and r.get('title')):
                continue
            sev = r.get('severity') if r.get('severity') in ('low', 'medium', 'high', 'critical') else 'medium'
            risks.append({
                'title': _clip(r['title'], 200), 'description': _clip(r['title'], 1000),
                'severity': sev, 'mitigation': _clip(r.get('mitigation'), 1000),
                'owner': _clip(r.get('owner'), 255),
            })
        return {'decisions': decisions, 'tasks': tasks, 'risks': risks}

    def answer(self, question: str, evidence: List[Dict[str, Any]]) -> str:
        """Synthesize an answer strictly from the supplied evidence excerpts."""
        context = '\n\n'.join(
            f"[{i}] ({e['document']}, p.{e['page']}) {e['excerpt']}" for i, e in enumerate(evidence, 1)
        )
        system = ('Answer the question using ONLY the numbered excerpts. Cite excerpts like [1]. '
                  'If the excerpts do not contain the answer, say so plainly. Be concise.')
        return self._complete(system, f'Excerpts:\n{context}\n\nQuestion: {question}', max_tokens=700).strip()


def extract_knowledge(text: str, claude: Optional[ClaudeExtractionService] = None) -> tuple[Dict[str, list], str, str]:
    """Extract decisions/tasks/risks. Returns (data, mode, error). Mode names the method actually used."""
    claude = claude or ClaudeExtractionService()
    error = ''
    if claude.available and text.strip():
        try:
            return claude.extract(text), MODE_CLAUDE, ''
        except Exception as exc:  # network, auth, bad JSON...
            error = type(exc).__name__
            logger.warning('Claude extraction failed (%s); falling back to rule-based.', error)
    data = {'decisions': extract_decisions(text), 'tasks': extract_tasks(text), 'risks': extract_risks(text)}
    return data, (MODE_FALLBACK if error else MODE_RULES), error
