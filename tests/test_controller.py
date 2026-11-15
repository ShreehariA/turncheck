"""One test per edge of the turn graph in turncheck/controller.py.

The readings are scripted (FakeReader), so these run without a model:
    python3 -m unittest discover tests
"""
import json
import unittest
from pathlib import Path

from turncheck.controller import Interview, apply
from turncheck.readings import to_transcript, wording_says_question

SCRIPT = {
    "title": "Test interview", "intro": ["rules"],
    "phrases": {"next": "Thanks.", "ask": "Answer or question?", "ask_no_model": "Could not read. Answer or question?",
                "stuck": "Keep thinking, repeat, or move on?", "repeat": "Again:", "decline": "No prepared reply.",
                "back": "Back to question {n}.", "moved_on": "Moving on.", "end": "The end."},
    "buttons": {"answer": "My answer", "question": "A question", "thinking": "Still thinking", "keep": "Keep thinking",
                "repeat": "Repeat the question", "move_on": "Move on"},
    "common": [{"id": "c.repeat", "repeat": True, "when": "asks to repeat"},
               {"id": "c.check", "decline": True, "when": "asks if they are right", "say": "No hints."}],
    "questions": [{"id": 1, "ask": "Question one?", "sheet": [{"id": "1.1", "when": "asks about a term", "say": "Term one."}]},
                  {"id": 2, "ask": "Question two?", "sheet": [{"id": "2.1", "when": "asks about a term", "say": "Term two."}]}],
}


class FakeReader:
    """Gives the labels and sheet entries a test lists, in order."""

    def __init__(self, labels=(), entries=()):
        self.labels, self.entries, self.offered = list(labels), list(entries), []

    def label(self, question, turn):
        return {"purpose": "label", "label": self.labels.pop(0), "error": None}

    def pick_entry(self, question, entries, turn):
        self.offered.append([entry["id"] for entry in entries])
        return {"purpose": "entry", "entry": self.entries.pop(0), "error": None}


def interview(labels=(), entries=(), start_at=1):
    it = Interview(SCRIPT, FakeReader(labels, entries), start_at)
    it.start()
    return it


def said(it):
    return [item["text"] for item in it.items if item["who"] == "interviewer"]


class ReadingATurn(unittest.TestCase):
    def test_start_asks_the_first_question(self):
        it = interview()
        self.assertEqual(it.state, "listening")
        self.assertEqual(it.view()["question"], "Question one?")
        self.assertEqual(it.view()["progress"], "Question 1 of 2")

    def test_agree_answer_is_recorded_and_the_next_question_asked(self):
        it = interview(["answer"])
        it.turn("I would use a merge")                      # not phrased as a question: both readings say answer
        self.assertEqual(it.trace[-1]["edge"], "agree-answer")
        self.assertEqual(it.notes[1]["answer"], "I would use a merge")
        self.assertEqual(it.view()["question"], "Question two?")
        self.assertEqual(it.items[1]["chip"], "Read as: answer · recorded")

    def test_agree_question_is_answered_from_the_sheet_and_not_recorded(self):
        it = interview(["question"], ["1.1"])
        it.turn("what does that term mean")
        self.assertEqual(it.trace[-1]["edge"], "agree-question")
        self.assertEqual(it.trace[-1]["did"], "clarify")
        self.assertIsNone(it.notes[1]["answer"])
        self.assertEqual(it.notes[1]["entries"], ["1.1"])
        self.assertEqual(said(it)[-1], "Term one.")
        self.assertEqual(it.view()["question"], "Question one?")  # still on the same question

    def test_only_the_current_sheet_and_the_common_entries_are_offered(self):
        it = interview(["question"], ["1.1"])
        it.turn("what does that term mean")
        self.assertEqual(it.reader.offered, [["1.1", "c.repeat", "c.check"]])

    def test_question_with_no_fitting_entry_is_declined(self):
        it = interview(["question"], ["none"])
        it.turn("what is the salary")
        self.assertEqual(it.trace[-1]["did"], "decline")
        self.assertEqual(it.notes[1]["declined"], ["what is the salary"])
        self.assertEqual(said(it)[-1], "No prepared reply.")
        self.assertEqual(it.items[-1]["tag"], "no prepared reply fits · declined")

    def test_entry_id_from_another_sheet_counts_as_no_entry(self):
        it = interview(["question"], ["2.1"])                # the model proposes an id that is not on this sheet
        it.turn("what does that term mean")
        self.assertEqual(it.trace[-1]["did"], "decline")
        self.assertEqual(it.notes[1]["entries"], [])

    def test_failed_entry_call_is_declined_not_guessed(self):
        it = interview(["question"], [None])
        it.turn("what does that term mean")
        self.assertEqual(it.trace[-1]["did"], "decline")
        self.assertEqual(it.items[-1]["tag"], "the model gave no reply · declined")   # it says which kind of "no"

    def test_prepared_no_hints_reply(self):
        it = interview(["question"], ["c.check"])
        it.turn("is that the right approach")
        self.assertEqual(it.trace[-1]["did"], "decline")
        self.assertEqual(said(it)[-1], "No hints.")
        self.assertEqual(it.notes[1]["entries"], ["c.check"])

    def test_repeat_entry_repeats_the_question(self):
        it = interview(["question"], ["c.repeat"])
        it.turn("could you repeat that")
        self.assertEqual(said(it)[-1], "Again: Question one?")

    def test_disagreement_asks_and_records_nothing(self):
        it = interview(["answer"])
        it.turn("would a merge work")                        # the model says answer, the wording says question
        self.assertEqual(it.trace[-1]["edge"], "disagree")
        self.assertEqual(it.state, "asking")
        self.assertIsNone(it.notes[1]["answer"])
        self.assertEqual(it.notes[1]["asks"], 1)
        self.assertEqual([b["id"] for b in it.view()["buttons"]], ["answer", "question", "thinking"])

    def test_thinking_aloud_that_is_worded_as_a_question_is_also_a_disagreement(self):
        it = interview(["unfinished"])
        it.turn("should I fix it or just find out why")       # the model says unfinished, the wording says question
        self.assertEqual(it.trace[-1]["edge"], "disagree")
        self.assertEqual(it.state, "asking")
        self.assertEqual(it.notes[1]["waits"], 0)

    def test_no_model_reading_asks_instead_of_guessing(self):
        it = interview([None])
        it.turn("I would use a merge")
        self.assertEqual(it.trace[-1]["edge"], "no-reading")
        self.assertEqual(it.state, "asking")
        self.assertEqual(said(it)[-1], "Could not read. Answer or question?")
        self.assertTrue(it.view()["banner"])

    def test_unfinished_waits_and_the_words_join_the_answer(self):
        it = interview(["unfinished", "answer"])
        it.turn("hmm let me think")
        self.assertEqual(it.trace[-1]["edge"], "unfinished")
        self.assertEqual(it.state, "listening")
        self.assertEqual(len(said(it)), 1)                    # TurnCheck says nothing: it waits
        it.turn("I would use a merge")
        self.assertEqual(it.notes[1]["answer"], "hmm let me think I would use a merge")
        self.assertEqual(it.notes[1]["waits"], 1)

    def test_two_unfinished_turns_in_a_row_offer_a_way_out(self):
        it = interview(["unfinished", "unfinished"])
        it.turn("hmm")
        it.turn("so")
        self.assertEqual(it.trace[-1]["edge"], "unfinished-twice")
        self.assertEqual(it.state, "asking")
        self.assertEqual([b["id"] for b in it.view()["buttons"]], ["keep", "repeat", "move_on"])


class AfterBeingAsked(unittest.TestCase):
    def asked(self, *entries):
        it = interview(["answer"], entries)
        it.turn("would a merge work")
        return it

    def test_chose_answer_records_it(self):
        it = self.asked()
        it.choose("answer")
        self.assertEqual(it.trace[-1]["edge"], "chose-answer")
        self.assertEqual(it.notes[1]["answer"], "would a merge work")
        self.assertEqual(it.items[1]["chip"], "You said: answer · recorded")

    def test_chose_question_goes_to_the_sheet(self):
        it = self.asked("c.check")
        it.choose("question")
        self.assertEqual(it.trace[-1]["edge"], "chose-question")
        self.assertIsNone(it.notes[1]["answer"])
        self.assertEqual(said(it)[-1], "No hints.")

    def test_chose_still_thinking_waits_and_keeps_the_words(self):
        it = interview(["unfinished", "unfinished", "answer"])
        it.turn("what was it called again")                  # worded as a question, read as unfinished: asked
        it.choose("thinking")
        self.assertEqual(it.trace[-1]["edge"], "chose-thinking")
        self.assertEqual(it.state, "listening")
        self.assertEqual(it.items[1]["chip"], "You said: thinking · not recorded")
        it.turn("hmm")
        self.assertEqual(it.trace[-1]["edge"], "unfinished")  # saying so yourself does not count towards "stuck"
        it.turn("a merge")
        self.assertEqual(it.notes[1]["answer"], "what was it called again hmm a merge")

    def test_a_button_that_was_not_offered_does_nothing(self):
        it = self.asked()
        it.choose("move_on")
        self.assertEqual(it.state, "asking")

    def test_typing_while_asked_does_nothing(self):
        it = self.asked()
        it.turn("something else")
        self.assertEqual(len(it.trace), 1)

    def stuck(self, *labels):
        it = interview(["unfinished", "unfinished", *labels])
        it.turn("hmm")
        it.turn("so")
        return it

    def test_keep_thinking_goes_back_to_waiting(self):
        it = self.stuck("unfinished")
        it.choose("keep")
        self.assertEqual(it.state, "listening")
        it.turn("well")
        self.assertEqual(it.trace[-1]["edge"], "unfinished")   # the count starts again

    def test_repeat_says_the_question_again(self):
        it = self.stuck()
        it.choose("repeat")
        self.assertEqual(said(it)[-1], "Again: Question one?")

    def test_move_on_records_no_answer(self):
        it = self.stuck()
        it.choose("move_on")
        self.assertIsNone(it.notes[1]["answer"])
        self.assertTrue(it.notes[1]["moved_on"])
        self.assertEqual(it.notes[1]["left_unfinished"], "hmm so")
        self.assertEqual(it.view()["question"], "Question two?")
        self.assertIsNone(it.last)                            # the question is closed: nothing left to correct


class Correcting(unittest.TestCase):
    def test_answer_corrected_to_question_after_moving_on(self):
        it = interview(["unfinished", "answer", "answer"], ["1.1"])
        it.turn("hmm")
        it.turn("the term as in the warehouse sense")        # really a question, read as an answer
        self.assertEqual(it.view()["question"], "Question two?")
        self.assertEqual(it.view()["items"][2]["fix"], [{"to": "question", "label": "That was a question"}])
        it.correct(it.last["id"], "question")
        self.assertEqual(it.trace[-1]["edge"], "corrected-answer-to-question")
        self.assertIsNone(it.notes[1]["answer"])
        self.assertEqual(it.notes[1]["corrections"], 1)
        self.assertEqual(it.view()["question"], "Question one?")       # back on the question it belongs to
        self.assertEqual(said(it)[-2:], ["Back to question 1.", "Term one."])
        self.assertEqual(it.items[2]["chip"], "You corrected: question · not recorded")
        it.turn("a real answer")
        self.assertEqual(it.notes[1]["answer"], "hmm a real answer")  # the earlier thinking is still attached

    def test_correcting_the_last_answer_reopens_the_interview(self):
        it = interview(["answer"], ["2.1"], start_at=2)
        it.turn("the term as in the warehouse sense")
        self.assertEqual(it.state, "done")
        it.correct(it.last["id"], "question")
        self.assertEqual(it.state, "listening")
        self.assertIsNone(it.view()["record"])

    def test_question_corrected_to_answer_is_recorded(self):
        it = interview(["question"], ["1.1"])
        it.turn("what I would do is merge on the id")
        it.correct(it.last["id"], "answer")
        self.assertEqual(it.trace[-1]["edge"], "corrected-question-to-answer")
        self.assertEqual(it.notes[1]["answer"], "what I would do is merge on the id")
        self.assertEqual(it.notes[1]["entries"], ["1.1"])              # the reply already given stays on the record
        self.assertEqual(it.items[1]["chip"], "You corrected: answer · recorded")

    def test_still_thinking_corrected_to_question(self):
        it = interview(["unfinished", "unfinished", "answer"], ["1.1"])
        it.turn("hmm")
        it.turn("the term as in the warehouse sense")        # a question, read as thinking aloud: TurnCheck waits
        self.assertEqual(it.state, "asking")                  # and, being the second in a row, asks if they are stuck
        self.assertEqual([fix["to"] for fix in it.view()["items"][2]["fix"]], ["question", "answer"])
        it.correct(it.last["id"], "question")
        self.assertEqual(it.trace[-1]["edge"], "corrected-unfinished-to-question")
        self.assertEqual(it.state, "listening")               # the "are you stuck" question is dropped
        self.assertEqual(it.view()["buttons"], [])
        self.assertEqual(said(it)[-1], "Term one.")
        self.assertEqual(it.items[2]["chip"], "You corrected: question · not recorded")
        self.assertEqual(it.items[2]["why"], "model: thinking · wording: not a question")
        it.turn("a real answer")
        self.assertEqual(it.notes[1]["answer"], "hmm a real answer")  # only the real thinking stays attached

    def test_still_thinking_corrected_to_answer(self):
        it = interview(["unfinished"])
        it.turn("type two")                                   # a short answer, read as thinking aloud
        it.correct(it.last["id"], "answer")
        self.assertEqual(it.trace[-1]["edge"], "corrected-unfinished-to-answer")
        self.assertEqual(it.notes[1]["answer"], "type two")
        self.assertEqual(it.view()["question"], "Question two?")

    def test_correction_is_offered_once_only_until_the_next_turn_and_only_to_another_reading(self):
        it = interview(["answer", "unfinished"], ["1.1"])
        it.turn("an answer")
        first = it.last["id"]
        it.turn("hmm")                                        # a new turn closes the window
        self.assertNotIn("fix", it.view()["items"][1])
        it.correct(first, "question")
        self.assertEqual(it.notes[1]["answer"], "an answer")

        it = interview(["answer"], ["1.1"])
        it.turn("an answer")
        it.correct(it.last["id"], "answer")                   # it is already read as an answer
        self.assertEqual(len(it.trace), 1)
        it.correct(it.last["id"], "question")
        steps = len(it.trace)
        it.correct(it.last["id"], "answer")                   # a second correction does nothing
        self.assertEqual(len(it.trace), steps)


class TheWholeInterview(unittest.TestCase):
    def test_last_answer_ends_with_the_record_and_no_score(self):
        it = interview(["answer", "answer"])
        it.turn("first")
        it.turn("second")
        self.assertEqual(it.state, "done")
        record = it.view()["record"]
        self.assertEqual([row["answer"] for row in record], ["first", "second"])
        self.assertFalse(any("score" in key for row in record for key in row))
        it.turn("more")                                       # nothing happens after the end
        self.assertEqual(len(it.trace), 2)

    def test_empty_turn_is_ignored(self):
        it = interview()
        it.turn("  ?  ")
        self.assertEqual(it.trace, [])

    def test_every_word_the_interviewer_says_comes_from_the_script(self):
        it = interview(["question", "question", "answer", "unfinished", "unfinished", "answer"], ["1.1", "none", "2.1"])
        for action in ({"turn": "what is a term"}, {"turn": "what is the salary"}, {"turn": "an answer"},
                       {"correct": "last", "to": "question"}, {"turn": "hmm"}, {"turn": "so"}, {"choose": "repeat"},
                       {"turn": "final"}):
            apply(it, action)
        fixed = set(SCRIPT["phrases"].values()) | {"Term one.", "Term two.", "No hints.", "Question one?",
                                                    "Question two?", "Again: Question one?", "Back to question 1."}
        self.assertLessEqual(set(said(it)), fixed)


class TheWordingReading(unittest.TestCase):
    def test_question_marks_are_removed_like_a_transcript(self):
        self.assertEqual(to_transcript("  is this about dbt?  I've used Airflow "), "is this about dbt I've used Airflow")

    def test_phrased_as_a_question(self):
        for turn in ("is this about dbt", "sorry, what does incremental mean here", "um, could you repeat that",
                     "would ROW_NUMBER over the event id work"):
            self.assertTrue(wording_says_question(turn), turn)

    def test_not_phrased_as_a_question(self):
        for turn in ("I'd filter on updated_at", "hmm okay, let me think", "star is flatter, I think"):
            self.assertFalse(wording_says_question(turn), turn)


class TheRealScript(unittest.TestCase):
    def test_every_interview_file_is_well_formed(self):
        for path in (Path(__file__).resolve().parent.parent / "interview").glob("*.json"):
            script = json.loads(path.read_text())
            self.assertLessEqual(set(SCRIPT["phrases"]), set(script["phrases"]), path.name)
            self.assertLessEqual(set(SCRIPT["buttons"]), set(script["buttons"]), path.name)
            entries = script["common"] + [e for q in script["questions"] for e in q["sheet"]]
            ids = [entry["id"] for entry in entries]
            self.assertEqual(len(ids), len(set(ids)), f"{path.name}: sheet entry ids must be unique")
            self.assertNotIn("none", ids)
            for entry in entries:
                self.assertTrue(entry["when"], entry["id"])
                self.assertTrue(entry.get("repeat") or entry.get("say"), f"{entry['id']} has nothing to say")


if __name__ == "__main__":
    unittest.main()
