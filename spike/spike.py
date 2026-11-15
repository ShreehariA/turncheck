"""Spike (23 Oct 2026): can a local model tell an answer from a question in an interview turn?

Runs 13 hand-written turns through a local model (Ollama) and a simple
question-form check, then shows what a controller would do with each turn:
  act  - both readings agree (record the answer, or clarify the question)
  ask  - the readings disagree ("Was that your answer, or a question?")
  wait - the model reads the turn as unfinished (thinking aloud)

Usage: python3 spike.py [model]          (needs Ollama running; default qwen2.5:7b)
"""
import json
import math
import re
import sys
import time
import urllib.request

MODEL = sys.argv[1] if len(sys.argv) > 1 else "qwen2.5:7b"
LABELS = ["answer", "question", "unfinished"]
SYSTEM = (
    "You read one turn from a candidate in a technical job interview. Label it:\n"
    "- answer: the candidate attempts to answer the interviewer's question, even if unsure or phrased tentatively\n"
    "- question: the candidate asks the interviewer something (to clarify a term, repeat, or check what is meant)\n"
    "- unfinished: thinking aloud or stalling, with no answer and no question yet\n"
    'Reply only with JSON: {"label": "answer" | "question" | "unfinished"}'
)
QUESTIONS = {
    1: "How would you make a dbt model incremental so it only processes new rows?",
    2: "What is the difference between a star schema and a snowflake schema?",
    3: "How would you remove duplicate events that arrive twice from a stream?",
    4: "What is a slowly changing dimension?",
}
# (question id, candidate turn, what should happen: answer / question / wait / ask)
CASES = [
    (1, "is this about dbt? I've mostly used Airflow", "question"),
    (1, "I'd set materialized to incremental and filter on updated_at with is_incremental, so only new rows get processed", "answer"),
    (1, "hmm okay, let me think about that for a second", "wait"),
    (1, "sorry, what does incremental mean here", "question"),
    (2, "A star schema joins one fact table straight to denormalised dimensions, a snowflake normalises the dimensions into more tables", "answer"),
    (2, "sorry, could you repeat the second one", "question"),
    (2, "star is flatter, snowflake splits dimensions further, I think", "answer"),
    (3, "do you mean during streaming or after the data lands in the warehouse", "question"),
    (3, "I'd give every event an id and keep the first one with ROW_NUMBER over the id", "answer"),
    (3, "would ROW_NUMBER over the event id work", "ask"),  # a tentative answer, or a request to check?
    (4, "what do you mean by dimension here, like in a data warehouse?", "question"),
    (4, "uh so, like type two", "wait"),
    (4, "it's a dimension where attributes change over time, and type 2 keeps history by adding a new row with valid from and to dates", "answer"),
]

FILLER = re.compile(r"^(sorry|so|um+|uh+|er+|okay|ok|right|and|but|hmm+|well)\b[\s,]*")
STARTS = re.compile(r"^(is|are|was|were|do|does|did|can|could|would|should|will|shall|may|might|has|have|am"
                    r"|what|which|who|where|when|why|how)\b")
PHRASES = re.compile(r"\b(do you mean|did you mean|could you|can you|what do you mean|what does .+ mean"
                     r"|say that again|repeat)\b")


def to_transcript(turn):
    """Speech transcripts may not carry question marks, so neither reading gets them."""
    return turn.replace("?", "").strip()


def looks_like_question(turn):
    t = turn.lower()
    while FILLER.match(t):
        t = FILLER.sub("", t, count=1)
    return bool(STARTS.match(t) or PHRASES.search(t))


def model_reading(question, turn):
    body = {
        "model": MODEL, "stream": False, "keep_alive": "10m", "think": False,
        "options": {"temperature": 0}, "logprobs": True, "top_logprobs": 8,
        "format": {"type": "object", "properties": {"label": {"type": "string", "enum": LABELS}}, "required": ["label"]},
        "messages": [{"role": "system", "content": SYSTEM},
                     {"role": "user", "content": f"Interviewer's question: {question}\nCandidate's turn: {turn}"}],
    }
    req = urllib.request.Request("http://localhost:11434/api/chat", data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    reply = json.load(urllib.request.urlopen(req, timeout=120))
    label = json.loads(reply["message"]["content"])["label"]
    # Probability of each label at the first token of the label value, renormalised over the three labels.
    tokens = reply.get("logprobs") or []
    first = next(t for t in tokens if t["token"].strip('" ') and label.startswith(t["token"].strip('" ')))
    mass = dict.fromkeys(LABELS, 0.0)
    for alt in first["top_logprobs"]:
        a = alt["token"].strip('" ')
        match = next((l for l in LABELS if a and l.startswith(a)), None)
        if match:
            mass[match] += math.exp(alt["logprob"])
    total = sum(mass.values()) or 1.0
    return label, {l: m / total for l, m in mass.items()}


def decide(label, form_says_question):
    if label == "unfinished":
        return "wait"
    if (label == "question") != form_says_question:
        return "ask"
    return label  # act on it: record the answer, or clarify the question


model_reading(QUESTIONS[1], "warm up")
rows, times, right = [], [], 0
for qid, turn, expected in CASES:
    heard = to_transcript(turn)
    start = time.time()
    label, p = model_reading(QUESTIONS[qid], heard)
    times.append(time.time() - start)
    form = looks_like_question(heard)
    action = decide(label, form)
    right += action == expected
    rows.append(f"{'ok ' if action == expected else 'NO '} expected {expected:8} got {action:8} | model {label:10} "
                f"p={p[label]:.2f} | form {'question' if form else '-':8} | {times[-1]:.2f}s | {heard}")

print(f"Model: {MODEL} (Ollama), temperature 0, question marks removed\n")
print("\n".join(rows))
print(f"\n{right}/{len(CASES)} turns handled as expected; median {sorted(times)[len(times) // 2]:.2f}s per model call")
