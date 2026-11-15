"""The turn graph: what TurnCheck does with each candidate turn.

Code fixes the order of the steps. The model only proposes a label or a sheet
entry id, and this file checks the proposal before anything is recorded or said.
Every edge below has a test in tests/test_controller.py.

After reading a turn:
  no-reading         the model gave no usable label                      -> ask the candidate
  disagree           the model and the wording disagree on "question"    -> ask the candidate
  unfinished         the model reads thinking aloud, wording agrees      -> wait, and keep the words
  unfinished-twice   two of those in a row                               -> ask: keep thinking, repeat, or move on
  agree-answer       both read an answer                                 -> record it, then the next question
  agree-question     both read a question                                -> reply from the sheet, or decline
Started by the candidate:
  chose-...          a button, after being asked
  corrected-X-to-Y   one tap on the last reading, whatever it was, until the next turn
The candidate is never scored.
"""
from .readings import to_transcript, wording_says_question

# The label under each turn: who decided how it was read, what it was read as, and what happened to it.
WHO = {"read": "Read as", "you": "You said", "fix": "You corrected"}
READ = {"answer": "answer · recorded", "question": "question · not recorded", "unfinished": "thinking · not recorded"}
ASKED = "Not sure how to read this · asked you"
SHOWN = {"answer": "answer", "question": "question", "unfinished": "thinking", None: "no reply"}
# Every reading can be corrected with one tap: what each one can be changed to, and the button's words.
FIX = {"answer": {"question": "That was a question"},
       "question": {"answer": "That was my answer"},
       "unfinished": {"question": "That was a question", "answer": "That was my answer"}}
WHICH = ("answer", "question", "thinking")   # the buttons when TurnCheck asks how to read a turn
STUCK = ("keep", "repeat", "move_on")        # the buttons after two thinking-aloud turns in a row
INDICATOR = {"start": "", "listening": "waiting for you", "asking": "asked you: choose below", "done": "finished"}
WAITS_BEFORE_ASKING = 2  # thinking-aloud turns in a row before TurnCheck offers a way out


class Interview:
    def __init__(self, script, reader, start_at=1):
        self.script, self.reader = script, reader
        self.questions = script["questions"]
        self.say = script["phrases"]
        self.at = self._index(start_at)   # which question we are on
        self.state = "start"              # start, listening, asking or done
        self.items = []                   # the transcript, in order: everything the page draws
        self.trace = []                   # one entry per step: what was sent, what came back, which edge
        self.notes = {q["id"]: {"answer": None, "entries": [], "declined": [], "asks": 0, "waits": 0,
                                "corrections": 0, "moved_on": False, "left_unfinished": ""}
                      for q in self.questions}
        self.fragments = []               # thinking-aloud words, kept until the answer comes
        self.unfinished_run = 0
        self.open = None                  # what the candidate has been asked: ("which" or "stuck", the turn)
        self.last = None                  # the last turn that was read; it can be corrected once
        self.model_ok = True
        self.step = {}

    # ---- what the candidate can do -------------------------------------------------------

    def start(self):
        if self.state == "start":
            self.state = "listening"
            self._ask_question()

    def turn(self, text):
        heard = to_transcript(text)
        if self.state != "listening" or not heard:
            return
        self._begin({"turn": heard})
        self.last = None  # a new turn closes the undo window on the one before
        question = self._question()
        turn = {"who": "candidate", "id": len(self.items), "q": question["id"], "text": heard}
        self.items.append(turn)

        reading = self.reader.label(question["ask"], heard)
        wording = wording_says_question(heard)
        self.step["calls"].append(reading)
        self.step["wording_says_question"] = wording
        label = reading["label"]
        self.model_ok = label is not None
        turn["why"] = f"model: {SHOWN[label]} · wording: {'question' if wording else 'not a question'}"

        if label is None:
            self._ask_which(turn, "no-reading")
        elif label == "unfinished" and not wording:
            self._wait(turn, "read")
        elif (label == "question") != wording:  # the two readings disagree about whether this is a question
            self._ask_which(turn, "disagree")
        elif label == "answer":
            self.step["edge"] = "agree-answer"
            self._record(turn, "read")
        else:
            self.step["edge"] = "agree-question"
            self._clarify(turn, "read")

    def choose(self, option):
        if self.state != "asking":
            return
        kind, turn = self.open
        if option not in (WHICH if kind == "which" else STUCK):
            return
        self._begin({"choose": option})
        self.step["edge"] = "chose-" + option.replace("_", "-")
        self.open, self.state = None, "listening"
        if option == "answer":
            self._record(turn, "you")
        elif option == "question":
            self._clarify(turn, "you")
        elif option == "thinking":
            self._wait(turn, "you")
        elif option == "keep":
            self.unfinished_run = 0
            self.step["did"] = "wait"
        elif option == "repeat":
            self.unfinished_run = 0
            self.step["did"] = "repeat"
            self._say("clarify", f"{self.say['repeat']} {self._question()['ask']}")
        else:  # move on, with no answer for this question
            notes = self.notes[self._question()["id"]]
            notes["moved_on"], notes["left_unfinished"] = True, " ".join(self.fragments)
            self.fragments, self.unfinished_run, self.last = [], 0, None
            self.step["did"] = "move on"
            self._say("note", self.say["moved_on"])
            self._next_question(thanks=False)

    def correct(self, turn_id, to):
        turn = self.last
        if turn is None or turn["id"] != turn_id or turn.get("corrected") or to not in FIX[turn["read"]]:
            return
        was = turn["read"]
        self._begin({"correct": turn_id, "to": to})
        self.step["edge"] = f"corrected-{was}-to-{to}"
        turn["corrected"] = True
        self.notes[turn["q"]]["corrections"] += 1
        if self.open:                 # "keep thinking, repeat or move on?" no longer applies
            self.open, self.state = None, "listening"
        if was == "unfinished":       # it was not thinking aloud: take its words out of the kept ones
            self.fragments.pop()
            self.unfinished_run = 0
        elif was == "answer":         # take the answer back and return to the question it belongs to
            self.notes[turn["q"]]["answer"] = None
            self.fragments = turn.pop("with")
            self.at, self.state = self._index(turn["q"]), "listening"
            self._say("note", self.say["back"].format(n=self.at + 1))
        if to == "answer":
            self._record(turn, "fix")
        else:
            self._clarify(turn, "fix")

    # ---- what TurnCheck does -------------------------------------------------------------

    def _record(self, turn, by):
        turn["with"] = self.fragments  # kept so that a correction can put them back
        self.notes[turn["q"]]["answer"] = " ".join(self.fragments + [turn["text"]])
        self.fragments, self.unfinished_run = [], 0
        turn.update(read="answer", chip=f"{WHO[by]}: {READ['answer']}")
        self.last = turn
        self.step["did"] = "record"
        self._next_question()

    def _clarify(self, turn, by):
        question = self._question()
        entries = question["sheet"] + self.script["common"]
        choice = self.reader.pick_entry(question["ask"], entries, turn["text"])
        self.step["calls"].append(choice)
        entry = next((e for e in entries if e["id"] == choice["entry"]), None)  # an id not on this sheet is no entry
        notes = self.notes[question["id"]]
        turn.update(read="question", chip=f"{WHO[by]}: {READ['question']}")
        self.last = turn
        if entry is None:
            notes["declined"].append(turn["text"])
            self.step["did"] = "decline"
            why = "the model gave no reply" if choice["entry"] is None else "no prepared reply fits"
            self._say("decline", self.say["decline"], tag=f"{why} · declined")
            return
        notes["entries"].append(entry["id"])
        kind = "decline" if entry.get("decline") else "clarify"
        text = f"{self.say['repeat']} {question['ask']}" if entry.get("repeat") else entry["say"]
        self.step["did"] = kind
        self._say(kind, text, tag=f"sheet entry {entry['id']} · same for everyone who asks")

    def _wait(self, turn, by):
        self.fragments.append(turn["text"])
        self.notes[turn["q"]]["waits"] += 1
        turn.update(read="unfinished", chip=f"{WHO[by]}: {READ['unfinished']}")
        self.last = turn
        self.step["did"] = "wait"
        if by == "you":               # the candidate said so: no need to ask whether they are stuck
            self.unfinished_run = 0
            return
        self.unfinished_run += 1
        self.step["edge"] = "unfinished"
        if self.unfinished_run >= WAITS_BEFORE_ASKING:
            self.step.update(edge="unfinished-twice", did="ask")
            self.open, self.state = ("stuck", turn), "asking"
            self._say("ask", self.say["stuck"])

    def _ask_which(self, turn, edge):
        self.step.update(edge=edge, did="ask")
        self.notes[turn["q"]]["asks"] += 1
        turn.update(read=None, chip=ASKED)
        self.open, self.state = ("which", turn), "asking"
        self._say("ask", self.say["ask" if edge == "disagree" else "ask_no_model"])

    def _next_question(self, thanks=True):
        if self.at + 1 == len(self.questions):
            self.state = "done"
            self._say("note", self.say["end"])
            return
        self.at += 1
        if thanks:
            self._say("note", self.say["next"])
        self._ask_question()

    def _ask_question(self):
        self._say("question", self._question()["ask"], n=self.at + 1, of=len(self.questions))

    # ---- small helpers -------------------------------------------------------------------

    def _question(self):
        return self.questions[self.at]

    def _index(self, question_id):
        return next(i for i, q in enumerate(self.questions) if q["id"] == question_id)

    def _say(self, kind, text, **more):
        self.items.append({"who": "interviewer", "kind": kind, "text": text, **more})

    def _begin(self, action):
        self.step = {"n": len(self.trace) + 1, "action": action, "question": self._question()["id"],
                     "calls": [], "wording_says_question": None, "edge": None, "did": None}
        self.trace.append(self.step)

    # ---- what the page and the assessor see ----------------------------------------------

    def view(self):
        """Everything the screen shows, built from what happened, not from a model's summary."""
        buttons = []
        if self.state == "asking":
            names = WHICH if self.open[0] == "which" else STUCK
            buttons = [{"id": name, "label": self.script["buttons"][name]} for name in names]
        items = []
        for item in self.items:
            shown = {key: value for key, value in item.items() if key != "with"}
            if item is self.last and not item.get("corrected"):
                shown["fix"] = [{"to": to, "label": label} for to, label in FIX[item["read"]].items()]
            items.append(shown)
        asking = self.state in ("listening", "asking")
        return {
            "title": self.script["title"],
            "intro": self.script["intro"],
            "state": self.state,
            "progress": f"Question {self.at + 1} of {len(self.questions)}" if asking else "",
            "question": self._question()["ask"] if asking else "",
            "indicator": INDICATOR[self.state],
            "banner": "" if self.model_ok else "The model is not responding, so I will ask you how to read each turn.",
            "items": items,
            "buttons": buttons,
            "record": self.record() if self.state == "done" else None,
        }

    def record(self):
        """What the human assessor receives: the answers and every help given. No score."""
        return [{"n": n, "question": q["ask"], **self.notes[q["id"]]} for n, q in enumerate(self.questions, 1)]


def apply(interview, action):
    """Run one candidate action. Returns the action, the trace it produced and the screen afterwards."""
    before = len(interview.trace)
    if "start" in action:
        interview.start()
    elif "turn" in action:
        interview.turn(action["turn"])
    elif "choose" in action:
        interview.choose(action["choose"])
    elif "correct" in action:
        last = interview.last["id"] if interview.last else None
        interview.correct(last if action["correct"] == "last" else action["correct"], action.get("to"))
    return {"action": action, "trace": interview.trace[before:], "view": interview.view()}
