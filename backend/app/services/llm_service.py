import re
import logging
from typing import List, Dict, Any, Optional
import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)

class LLMService:
    """
    Provider-agnostic LLM interface supporting Groq, OpenAI, Ollama,
    and a robust zero-dependency offline fallback engine.
    """

    def __init__(
        self,
        provider: Optional[str] = None,
        model_name: Optional[str] = None
    ):
        self.provider = (provider or settings.LLM_PROVIDER).lower()
        self.model_name = model_name or settings.LLM_MODEL_NAME
        self.groq_api_key = settings.GROQ_API_KEY
        self.openai_api_key = settings.OPENAI_API_KEY
        self.ollama_url = settings.OLLAMA_BASE_URL

    def generate_answer(
        self,
        question: str,
        passages: List[Dict[str, Any]],
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Generates an evidence-grounded answer based strictly on retrieved passages.
        """
        if not passages:
            return "Based on the provided documents, there is insufficient evidence to answer this question."

        if self.provider == "groq" and self.groq_api_key:
            try:
                return self._call_groq(question, passages, system_prompt)
            except Exception as e:
                logger.error(f"Groq API call failed: {e}. Falling back to offline synthesis engine.")
                return self._generate_fallback(question, passages)

        elif self.provider == "openai" and self.openai_api_key:
            try:
                return self._call_openai(question, passages, system_prompt)
            except Exception as e:
                logger.error(f"OpenAI API call failed: {e}. Attempting failover to Groq...")
                if self.groq_api_key:
                    try:
                        return self._call_groq(question, passages, system_prompt)
                    except Exception as ge:
                        logger.error(f"Groq failover call also failed: {ge}")
                return self._generate_fallback(question, passages)

        elif self.provider == "ollama":
            try:
                return self._call_ollama(question, passages, system_prompt)
            except Exception as e:
                logger.error(f"Ollama call failed: {e}. Falling back to offline synthesis engine.")
                return self._generate_fallback(question, passages)

        # If provider was unconfigured or other provider failed, try Groq if key exists
        if self.groq_api_key:
            try:
                return self._call_groq(question, passages, system_prompt)
            except Exception as e:
                logger.error(f"Groq primary attempt failed: {e}")

        # Default fallback engine
        return self._generate_fallback(question, passages)

    def _build_context_prompt(self, passages: List[Dict[str, Any]]) -> str:
        """
        Assembles passages inside strict XML-style delimiters to isolate
        untrusted document text and protect against prompt injection.
        """
        formatted_chunks = []
        for i, p in enumerate(passages, start=1):
            doc_id = p.get("document_id", "doc")
            page_num = p.get("page_number", 1)
            content = p.get("content", "").replace("<", "&lt;").replace(">", "&gt;")
            formatted_chunks.append(
                f'<passage index="{i}" document_id="{doc_id}" page="{page_num}">\n{content}\n</passage>'
            )
        return "\n\n".join(formatted_chunks)

    DEFAULT_SYSTEM_PROMPT = (
        "You are EvidenceAI, an ultra-precise, accurate scientific research assistant.\n"
        "CRITICAL RULES FOR ACCURACY AND CONCISENESS:\n"
        "1. SHORT, DIRECT & ESSENTIAL: Answer in 1 to 2 concise sentences (or concise bullet points if a list is explicitly requested). State ONLY the important and direct answer to the question asked. Strictly avoid filler, conversational preambles, and unasked background information.\n"
        "2. INTELLIGENT DOCUMENT PERCEPTION: Academic papers often do not print the explicit label 'Title' before their title or 'Author' before names. Identify the paper's title, authors, or affiliations directly from the document header on Page 1.\n"
        "3. SYNTHESIZE PRECISELY: Do not copy-paste raw text blocks. Deliver a clean, direct, factual statement answering the user's inquiry.\n"
        "4. ACCURATE CITATIONS: Embed exact citation tags in the format [Page X] or [DocID, Page X] for every fact, finding, or number.\n"
        "5. INSUFFICIENT EVIDENCE: If the passages lack sufficient information to answer the question, respond concisely: 'Based on the provided documents, there is insufficient evidence to answer this question.'"
    )

    def _call_groq(self, question: str, passages: List[Dict[str, Any]], system_prompt: Optional[str]) -> str:
        context = self._build_context_prompt(passages)
        sys_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        user_message = (
            f"<passages>\n{context}\n</passages>\n\n"
            f"Question: {question}\n\n"
            f"Answer concisely in 1-2 direct sentences with only the important answer and [Page X] citations. Do not write filler."
        )

        headers = {
            "Authorization": f"Bearer {self.groq_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name or "qwen/qwen3.8-27b",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.0,
            "max_tokens": 300
        }
        with httpx.Client(timeout=30.0) as client:
            try:
                resp = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
            except httpx.HTTPStatusError as e:
                if payload["model"] != "qwen/qwen3.8-27b":
                    logger.warning(f"Groq model {payload['model']} returned {e.response.status_code}. Retrying with qwen/qwen3.8-27b...")
                    payload["model"] = "qwen/qwen3.8-27b"
                    resp = client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
                raise

    def _call_openai(self, question: str, passages: List[Dict[str, Any]], system_prompt: Optional[str]) -> str:
        context = self._build_context_prompt(passages)
        sys_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        user_message = (
            f"<passages>\n{context}\n</passages>\n\n"
            f"Question: {question}\n\n"
            f"Answer concisely in 1-2 direct sentences with only the important answer and [Page X] citations. Do not write filler."
        )
        headers = {
            "Authorization": f"Bearer {self.openai_api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name or "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_message}
            ],
            "temperature": 0.0,
            "max_tokens": 300
        }
        with httpx.Client(timeout=30.0) as client:
            resp = client.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()

    def _call_ollama(self, question: str, passages: List[Dict[str, Any]], system_prompt: Optional[str]) -> str:
        context = self._build_context_prompt(passages)
        sys_prompt = system_prompt or self.DEFAULT_SYSTEM_PROMPT
        payload = {
            "model": self.model_name or "llama3",
            "prompt": f"System: {sys_prompt}\n\nPassages:\n{context}\n\nQuestion: {question}\n\nAnswer in 1-2 short, direct sentences with citations:",
            "stream": False
        }
        with httpx.Client(timeout=45.0) as client:
            resp = client.post(f"{self.ollama_url}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()

    def _generate_fallback(self, question: str, passages: List[Dict[str, Any]]) -> str:
        """
        Deterministic, offline evidence synthesis engine.
        Synthesizes the most salient findings matching query intent directly into
        short, coherent statements rather than pasting disjointed raw text chunks.
        """
        q_lower = question.lower()

        # 0. Intent Detection: Paper Title Query
        if re.search(r'\b(title|paper(?:[\'’]s)? name|what is (?:the|this)? (?:paper|document|study) called)\b', q_lower):
            for p in passages:
                if p.get("page_number", 1) == 1:
                    content = p.get("content", "")
                    lines = [l.strip().strip('|').strip() for l in content.splitlines() if l.strip() and l.strip() != '|']
                    if lines:
                        # First significant line on page 1 is the paper title
                        first_line = lines[0]
                        return f'The title of the paper is "{first_line}" [Page 1].'

        # 1. Intent Detection: Person / Author / Candidate Query
        if re.search(r'\b(author|who (?:wrote|authored|conducted|published)|candidate|applicant|person|researcher)\b', q_lower):
            for p in passages:
                page_num = p.get("page_number", 1)
                content = p.get("content", "")
                lines = [l.strip().strip('|').strip() for l in content.splitlines() if l.strip() and l.strip() != '|']
                if lines:
                    # Check author line
                    for l in lines[1:4]:
                        if re.search(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+', l) and not any(w in l.lower() for w in ['department', 'university', 'abstract', 'http']):
                            return f"The authors are {l} [Page {page_num}]."
                    first_line = lines[0]
                    words = first_line.split()
                    if 1 <= len(words) <= 5 and all(w.replace('.', '').replace('-', '').isalpha() for w in words):
                        name_str = first_line.title() if first_line.isupper() else first_line
                        return f"The referenced individual is {name_str} [Page {page_num}]."

        # 2. Intent Detection: Contact Information (Email / Phone / Links)
        if re.search(r'\b(email|contact|phone|number|reach|address|location|linkedin|github)\b', q_lower):
            for p in passages:
                page_num = p.get("page_number", 1)
                content = p.get("content", "")
                emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', content)
                phones = re.findall(r'(?:\+\d{1,3}\s*)?\d{9,15}', content)
                githubs = re.findall(r'https?://(?:www\.)?github\.com/[a-zA-Z0-9_-]+', content)
                linkedins = re.findall(r'https?://(?:www\.)?linkedin\.com/in/[a-zA-Z0-9_-]+', content)

                if "email" in q_lower and emails:
                    return f"The contact email is {emails[0]} [Page {page_num}]."
                if any(w in q_lower for w in ["phone", "call", "mobile", "number"]) and phones:
                    return f"The contact telephone number is {phones[0]} [Page {page_num}]."
                if "github" in q_lower and githubs:
                    return f"The GitHub repository is {githubs[0]} [Page {page_num}]."
                if "linkedin" in q_lower and linkedins:
                    return f"The LinkedIn profile is {linkedins[0]} [Page {page_num}]."

        # 3. Direct Synthesis from salient evidence sentences
        q_words = set(re.findall(r'\b[a-zA-Z0-9_\-]+\b', q_lower))
        stopwords = {"what", "which", "how", "did", "the", "and", "for", "with", "from", "were", "was", "does", "that", "this", "are", "about", "tell", "give"}
        q_keywords = q_words - stopwords

        selected_sentences = []
        seen_texts = set()
        for p in passages:
            page_num = p.get("page_number", 1)
            content = p.get("content", "")
            raw_units = re.split(r'(?<=[.!?])\s+|\n+', content)
            for unit in raw_units:
                # Clean table pipes, bullet characters, leading colons, and repeated whitespace
                s_clean = re.sub(r'\|+', ' ', unit)
                s_clean = re.sub(r'\s+', ' ', s_clean).strip().lstrip('•-–*:').strip()
                if len(s_clean) < 20 or s_clean in seen_texts:
                    continue
                s_words = set(re.findall(r'\b[a-zA-Z0-9_\-]+\b', s_clean.lower()))
                overlap = len(q_keywords.intersection(s_words))
                if overlap > 0:
                    seen_texts.add(s_clean)
                    selected_sentences.append({
                        "sentence": s_clean,
                        "page_number": page_num,
                        "overlap": overlap
                    })

        if not selected_sentences:
            top_p = passages[0]
            page_num = top_p.get("page_number", 1)
            raw_lines = [re.sub(r'\|+', ' ', l).strip().lstrip('•-–*:').strip() for l in top_p.get("content", "").splitlines() if l.strip() and l.strip() != '|']
            first_sent = raw_lines[0] if raw_lines else "the provided document contains relevant context"
            if not first_sent.endswith((".", "!", "?")):
                first_sent += "."
            return f"Based on the document records, {first_sent} [Page {page_num}]"

        # Rank by informational keyword overlap and take top 2-3
        selected_sentences.sort(key=lambda x: x["overlap"], reverse=True)
        top_sentences = selected_sentences[:3]

        answer_parts = []
        for i, item in enumerate(top_sentences):
            s_text = item["sentence"]
            if not s_text.endswith((".", "!", "?")):
                s_text += "."
            # Seamless synthesis prefix
            if i == 0:
                answer_parts.append(f"{s_text} [Page {item['page_number']}]")
            else:
                answer_parts.append(f"Additionally, {s_text[0].lower() + s_text[1:]} [Page {item['page_number']}]")

        return " ".join(answer_parts)

