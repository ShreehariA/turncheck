"""Two independent readings of one candidate turn.

1. The model reading: a local language model (through Ollama) labels the turn
   as an answer, a question or unfinished.
2. The wording reading: a few regular expressions check whether the turn is
   phrased as a question.

Neither is trusted on its own; controller.py compares them and decides.
For a question, the model also picks a sheet entry. It returns an id, never text.
"""
import json
import math
import re
import time
import urllib.request

LABELS = ("answer", "question", "unfinished")

LABEL_PROMPT = (
    "You read one turn from a candidate in a technical job interview. Label it:\n"
    "- answer: the candidate attempts to answer the interviewer's question, even if unsure or phrased tentatively\n"
    "- question: the candidate asks the interviewer something (to clarify a term, repeat, or check what is meant)\n"
    "- unfinished: thinking aloud or stalling, with no answer and no question yet\n"
    'Reply only with JSON: {"label": "answer" | "question" | "unfinished"}'
)

ENTRY_PROMPT = (
    "A candidate in a job interview asked the interviewer something. The interviewer may only give a prepared reply.\n"
    "Pick the one prepared reply whose description matches what the candidate asked.\n"
    'If none of them matches, pick "none". Do not pick a reply only because it is on a similar topic.\n'
    'Reply only with JSON: {"entry": "<id>"}'
)

FILLER = re.compile(r"^(sorry|so|um+|uh+|er+|okay|ok|right|and|but|hmm+|well)\b[\s,]*")
STARTS = re.compile(r"^(is|are|was|were|do|does|did|can|could|would|should|will|shall|may|might|has|have|am"
                    r"|what|which|who|where|when|why|how)\b")
PHRASES = re.compile(r"\b(do you mean|did you mean|could you|can you|what do you mean|what does .+ mean"
                     r"|say that again|repeat)\b")


def to_transcript(text):
    """Typed turns stand in for speech, and a transcript may not carry question marks, so they are removed."""
    return " ".join(text.replace("?", " ").split())


def wording_says_question(turn):
    """The second reading: is the turn phrased as a question? It looks at word order only, not meaning."""
    words = turn.lower()
    while FILLER.match(words):
        words = FILLER.sub("", words, count=1)
    return bool(STARTS.match(words) or PHRASES.search(words))


def label_probability(logprobs, label):
    """The model's probability for the label it chose, at the label's first token, over the three labels.

    Saved for inspection only. The spike showed it stays near 1 even on ambiguous turns,
    so the controller never uses it to decide.
    """
    try:
        first = next(t for t in logprobs if t["token"].strip('" ') and label.startswith(t["token"].strip('" ')))
        mass = dict.fromkeys(LABELS, 0.0)
        for other in first["top_logprobs"]:
            start = other["token"].strip('" ')
            match = next((name for name in LABELS if start and name.startswith(start)), None)
            if match:
                mass[match] += math.exp(other["logprob"])
        return round(mass[label] / (sum(mass.values()) or 1.0), 3)
    except (StopIteration, KeyError, TypeError):
        return None


class OllamaReader:
    """Asks a local model through Ollama. A call that fails comes back with no value and an error, never a guess."""

    def __init__(self, model="qwen2.5:7b", host="http://localhost:11434", timeout=10):
        self.model, self.host, self.timeout = model, host, timeout

    def _call(self, system, user, field, choices, timeout=None):
        """One call that must return {field: one of choices}. The dict it returns goes into the trace unchanged."""
        messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        body = {
            "model": self.model, "stream": False, "keep_alive": "10m", "think": False,
            "options": {"temperature": 0}, "logprobs": field == "label", "top_logprobs": 8 if field == "label" else 0,
            "format": {"type": "object", "properties": {field: {"type": "string", "enum": list(choices)}},
                       "required": [field]},
            "messages": messages,
        }
        call = {"purpose": field, "model": self.model, "sent": messages, "raw": None, field: None, "p": None,
                "ms": None, "error": None}
        start = time.time()
        try:
            request = urllib.request.Request(self.host + "/api/chat", data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json"})
            reply = json.load(urllib.request.urlopen(request, timeout=timeout or self.timeout))
            call["raw"] = reply["message"]["content"]
            value = json.loads(call["raw"]).get(field)
            if value not in choices:
                raise ValueError(f"{value!r} is not an allowed value")
            call[field] = value
            if field == "label":
                call["p"] = label_probability(reply.get("logprobs"), value)
        except Exception as problem:  # no reply, slow reply, bad JSON, or a value outside the schema
            call["error"] = f"{type(problem).__name__}: {problem}"
        call["ms"] = round((time.time() - start) * 1000)
        return call

    def label(self, question, turn):
        return self._call(LABEL_PROMPT, f"Interviewer's question: {question}\nCandidate's turn: {turn}", "label", LABELS)

    def pick_entry(self, question, entries, turn):
        listed = "\n".join(f"- {entry['id']}: use when the candidate {entry['when']}" for entry in entries)
        user = f"Interviewer's question: {question}\nPrepared replies:\n{listed}\nCandidate asked: {turn}"
        return self._call(ENTRY_PROMPT, user, "entry", [entry["id"] for entry in entries] + ["none"])

    def warm_up(self):
        """Load the model before the first turn, which can take a few seconds. True if it replied."""
        user = "Interviewer's question: Are you ready?\nCandidate's turn: yes, ready"
        return self._call(LABEL_PROMPT, user, "label", LABELS, timeout=90)["label"] is not None


class RecordedReader:
    """Gives back the model calls saved in a trace, in order, so a saved interview can be re-run without a model."""

    def __init__(self, calls):
        self.calls = list(calls)

    def _next(self, purpose):
        if not self.calls or self.calls[0]["purpose"] != purpose:
            raise ValueError(f"the trace has no saved '{purpose}' call at this point")
        return self.calls.pop(0)

    def label(self, question, turn):
        return self._next("label")

    def pick_entry(self, question, entries, turn):
        return self._next("entry")
