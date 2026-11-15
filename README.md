# TurnCheck

A prototype AI interviewer that reads each candidate turn before it counts: is it an answer, a question, or still thinking?
When it is not sure it asks. It replies to questions only from a prepared sheet, and it never scores.

Built for Intelligent Interactive Systems, Assignment 2 (University of Birmingham).
*README prose: about 1,050 words. Code and commands are not counted.*

<p>
  <img src="docs/screenshots/1b-question.png" width="230" alt="A question about dbt is read as a question, answered from the sheet and not recorded">
  <img src="docs/screenshots/2b-asked.png" width="230" alt="The two readings disagree, so TurnCheck asks the candidate">
  <img src="docs/screenshots/3c-record.png" width="230" alt="The record for the assessor, with no score">
</p>

## Project status

**Made, and working on my laptop**
- The interview screen, one page in the browser: the question, a label under every turn saying how it was read, one-tap correction, a state line, and the record at the end.
- The controller (`turncheck/controller.py`): a fixed workflow that acts, asks or waits. Every edge has a test.
- Two readings of each turn: a local model's label and a check of the wording. When they disagree, TurnCheck asks instead of recording.
- Clarifications from a prepared sheet. The model only names a sheet entry; every word the candidate reads is in `interview/data-engineer.json`.
- A trace of every model call, and a replay harness that runs scripted turns, or a whole scripted interview, through the same controller.

**Simulated**
- Speech. Turns are typed, and question marks are removed because a transcript may not have them.

**Not finished**
- No result yet on turns I wrote without the AI seeing them (`replay/heldout.tsv`). Everything in `results/` so far uses dev turns the AI wrote, so it shows the system runs, not how well it reads.
- A reading can only be corrected until the next turn.
- One role, five questions, one interview at a time.

**Planned**
- Speech recognition and spoken replies.
- A view for the human assessor.
- A comparison with a fixed script and with an "ask" button (Phase 3).

## Technology stack

| Part | What it does | Status |
|---|---|---|
| Python, standard library only (run on 3.13) | server, controller, replay, tests | in use |
| [Ollama](https://ollama.com) 0.40.13 | runs the model on the laptop: no key, no paid service, nothing sent out | in use |
| `qwen2.5:7b` (4.7 GB) | labels a turn, and names a sheet entry for a question, each as fixed-schema JSON | in use |
| Wording check (regular expressions) | the second reading: is the turn phrased as a question? | in use |
| HTML, CSS and JavaScript, no framework | the screen; it only draws what the controller sends | in use |
| draw.io | the two diagrams in `docs/` | in use |
| Speech-to-text | spoken turns | planned, tool undecided |

## Running or inspecting the work

**Without running anything**
- `docs/screenshots/`: the screens.
- `results/traces/storyboard-interview.json`: one whole interview, with every screen, every model call and every edge taken.
- `results/*.txt`: one line per replayed turn.
- `docs/architecture.svg` and `docs/turn-graph.svg`: the diagrams (the `.drawio` files open in draw.io).

**Running it**

```bash
ollama pull qwen2.5:7b        # once; about 4.7 GB
python3 app.py                # then open http://localhost:8000
```

Without Ollama the screen still runs: TurnCheck then asks how to read every turn instead of guessing.

**Stepping through the saved interview, with no model**

```bash
python3 app.py                # then open http://localhost:8000/?trace=storyboard-interview&step=3
```

Change `step` from 0 to 12.

**Tests and replay**

```bash
python3 -m unittest discover tests                        # no model needed
python3 replay/replay.py turns replay/dev-turns.tsv       # needs Ollama
python3 replay/replay.py interview replay/storyboard-interview.json
```

## Development record

Commits: <https://github.com/ShreehariA/turncheck/commits/main>. I made the first eight together on 15 Nov, once the build worked, one commit per part. The steps below came before those commits, so the evidence for each step is the file it names, not the commit time.

| When | Change | Why | What was checked | Commit |
|---|---|---|---|---|
| 23 Oct | Spike: a local model labels 13 turns | to see if a free local model can do the one inference the design needs | 11 of 11 clear turns right, about 0.3 s each (`spike/results-2026-10-23.txt`) | [a606088](https://github.com/ShreehariA/turncheck/commit/a6060888ffe15e9e1d4f78685c9875a0cc8abc59) |
| 23 Oct | A second reading decides when to ask, not the model's probability | the model gave its label 0.97 or more even on the two turns written to be ambiguous | "ask when the readings disagree" handled 13 of 13; the same author wrote the turns and the rule, so this is a sanity check | [a606088](https://github.com/ShreehariA/turncheck/commit/a6060888ffe15e9e1d4f78685c9875a0cc8abc59) |
| 14 Nov | Controller as a fixed workflow; the model returns only a label or an entry id | a wrong model reply can then, at worst, pick the wrong prepared reply | a test per edge, including "an id from another sheet is declined" and "every word said comes from the script" | [a777892](https://github.com/ShreehariA/turncheck/commit/a7778922bedc8aa0dd101b510f9debf4bc210e18) |
| 14 Nov | The screen shows how each turn was read, with a one-tap fix and a state line | the candidate should see what counted and correct it at once | `docs/screenshots/`: real screens from the saved interview, not mock-ups | [5483d42](https://github.com/ShreehariA/turncheck/commit/5483d4270000c75f2ac9ae3bfe0192a0d968f8a3) |
| 14 Nov | "Still thinking" can be corrected too; a thinking-aloud label that disagrees with the wording now asks | first dev replay: 4 of 19 questions were read as thinking aloud, and TurnCheck waited in silence | `results/2026-11-14-dev-turns.txt` against `-run2.txt` | [a777892](https://github.com/ShreehariA/turncheck/commit/a7778922bedc8aa0dd101b510f9debf4bc210e18), [ccb888d](https://github.com/ShreehariA/turncheck/commit/ccb888d784848eabf04b7968ea3fd34e1c828c2b) |
| 14 Nov | Reworded one sheet entry; left the prompt alone | a hint leak: "would ROW_NUMBER over the event id work" got a clarification, not the no-hints reply. Two prompt changes made it worse. The entry's description named the answer, not a term | `results/2026-11-14-entry-picker-notes.txt`; then 30 of 31 dev questions got the expected entry (`-run3.txt`) | [d3e4f8d](https://github.com/ShreehariA/turncheck/commit/d3e4f8d859e09e3a1c844f194634c32d9d233a97), [ccb888d](https://github.com/ShreehariA/turncheck/commit/ccb888d784848eabf04b7968ea3fd34e1c828c2b) |
| 14 Nov | Saved interviews must replay to the same screens | so the screenshots cannot drift from the code | `tests/test_traces.py` | [ccb888d](https://github.com/ShreehariA/turncheck/commit/ccb888d784848eabf04b7968ea3fd34e1c828c2b) |

Dev replay so far (42 turns the AI wrote, `results/2026-11-14-dev-turns-run3.txt`): 31 handled as meant, 8 asked about (one extra tap), 3 questions read as thinking aloud (one tap to correct), no question recorded as an answer. This is not evidence of accuracy.

## AI assistance

- **Tool:** Claude Code in the terminal: Claude Opus 5.5 for the October draft, Claude Fable 5.2 for the build on 14 November, and Claude Opus 5.5 again from 15 November.
- **What I asked it for:** the spike; the controller, screen, replay harness and tests; the dev turns; first drafts of the interview questions and sheets; the diagrams; this README.
- **What I set:** the problem, from my own AI interview; no paid service and no key; a local model; that the AI never scores; diagrams in draw.io, black and white, with no crossing lines; and that I make every commit myself.
- **What it proposed and I accepted:** the two readings and "ask when they disagree"; the fixed sheet; standard library only.
- **What I changed:** TODO, after editing the questions and sheets.
- **How I checked:** TODO. Planned: write the held-out turns without showing them to the AI until the rule is frozen, run an interview by hand, and read every line of the replay results.
- The agent's standing rules are in `AGENTS.md`.

## Additional files

- `docs/design-notes.md`: contracts for each action, the pattern and the case against it, the numbers, sensors and privacy.
- `spike/`: the October spike, its two runs, and the README as it was then.
- The project report is submitted on Canvas. There is no ZIP.
