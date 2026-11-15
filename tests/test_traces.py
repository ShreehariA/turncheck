"""Saved interviews must still replay to exactly the same screens.

Each file in results/traces/ holds the candidate's actions, the model's replies and
the screen after every step. Re-running the actions with the saved replies (no model)
must give the same screens, so the storyboards cannot drift away from the code.
"""
import json
import unittest
from pathlib import Path

from turncheck.controller import Interview, apply
from turncheck.readings import RecordedReader

ROOT = Path(__file__).resolve().parent.parent


class SavedInterviews(unittest.TestCase):
    def test_every_saved_interview_replays_to_the_same_screens(self):
        traces = sorted((ROOT / "results" / "traces").glob("*.json"))
        self.assertTrue(traces, "no saved interviews to check")
        for path in traces:
            saved = json.loads(path.read_text())
            script = json.loads((ROOT / "interview" / saved["script"]).read_text())
            calls = [call for step in saved["steps"] for entry in step["trace"] for call in entry["calls"]]
            interview = Interview(script, RecordedReader(calls), start_at=saved["start_at"])
            for number, step in enumerate(saved["steps"]):
                again = apply(interview, step["action"])
                self.assertEqual(again["view"], step["view"], f"{path.name}, step {number}")


if __name__ == "__main__":
    unittest.main()
