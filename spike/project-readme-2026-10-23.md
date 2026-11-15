> Snapshot: the project README as it stood on 23 October 2026, when only this spike existed. Kept unchanged below. The current README is at the top of the repository.

# TurnCheck

A prototype AI interviewer that reads each candidate turn before it counts: is it an answer, a question, or unfinished?
Built for Intelligent Interactive Systems, Assignment 2 (University of Birmingham).

*README prose: about 540 words (code and commands not counted).*

> **Draft, 23 October 2026.** Only the spike exists so far. The sections below say what is real now and what is planned.

## Project status

- **Made:** a spike (`spike/spike.py`). It sends 13 interview turns I wrote to a local model and to a simple question-form check, then prints what the controller would do: act, ask or wait.
- **Works:**
  - the model call, a JSON label in about 0.3 s per turn on my laptop (Apple M4 Pro);
  - the form check;
  - the rule "ask when the two readings disagree", on those 13 turns.
- **Simulated:** speech. Turns are typed, and question marks are removed, because a speech transcript may not have them.
- **Not built yet:**
  - the interview screen;
  - the controller, with clarification sheets;
  - the interview record;
  - the replay harness and a test set that isn't tuned.
- **Planned after Phase 2:** speech-to-text, voice output, and a view for the human assessor.

## Technology stack

| Part | What it does | Status |
|---|---|---|
| Python 3.13, standard library only | the spike; later the controller | in use |
| Ollama 0.40.6 | runs the model on my laptop, so no key and no paid API | in use |
| `qwen2.5:7b` (4.7 GB download) | labels a turn as answer, question or unfinished, in a fixed JSON schema | in use; may compare with a second local model |
| Question-form check (regular expressions) | a second, independent reading of the turn | in use |
| Web screen | question card, turn chips, one-tap corrections | undecided; plan is FastAPI with one HTML page |
| Speech-to-text | turns spoken answers into text | planned; tool undecided |

## Running or inspecting the work

Needs [Ollama](https://ollama.com) running, and the model (about 4.7 GB):

```bash
ollama pull qwen2.5:7b
python3 spike/spike.py        # prints each turn, both readings and the decision
```

My run from 23 October is saved in `spike/results-2026-10-23.txt`, so you can inspect it without running anything.

## Development record

| Date | Change | Why | What I checked |
|---|---|---|---|
| 23 Oct | Spike: local model labels each turn | to see if a free local model can do the one inference the design needs | 11 of 11 clear turns labelled right; about 0.3 s each |
| 23 Oct | Confidence comes from a second reading, not the model's probability | the model gave its label a probability of 0.97 or more even on the two turns I wrote to be ambiguous | with "ask when the readings disagree", 13 of 13 turns were handled as I intended (I wrote both the turns and the rule, so this is a sanity check, not evidence) |
| 23 Oct | Labels changed from answer / question / unclear to answer / question / unfinished | "unclear" became the controller's decision; "unfinished" catches thinking aloud, which should make the system wait | the two thinking-aloud turns led to "wait" |

Commit links will go here once the repository is public.

## AI assistance

- **Tool:** Claude Code (Claude Opus 5.5), in the terminal.
- **What I asked for:**
  - a spike script and test turns, to check the idea with a local model;
  - first drafts of the report's rationale table, system diagram and storyboards (LaTeX);
  - this README.
- **What I changed or decided:** TODO, in my own words.
- **How I checked:** TODO, in my own words. For example: re-ran the spike myself, read every label, and checked each lecture claim against the slides.

## Additional files

None yet. The report is submitted separately on Canvas.
