# AGENTS.md

Rules for any coding agent working in this repository. Kept short because it is loaded on every call.

## What this is
TurnCheck is a prototype AI interviewer that reads each candidate turn (answer, question or unfinished) before it counts.
Coursework for Intelligent Interactive Systems, University of Birmingham.

## Rules
- Python standard library only. Ask before adding any dependency.
- No paid APIs and no keys. The model runs locally through Ollama.
- The model never writes text the candidate reads. It returns a label or a sheet entry id. The controller checks it and uses the fixed text in `interview/*.json`.
- Every edge of the turn graph in `turncheck/controller.py` has a test in `tests/`. Add the test with the edge.
- Never tune the prompt or the wording rule on `replay/heldout.tsv`. Debug with `replay/dev-turns.tsv`.
- Never state a result in the README or anywhere else unless it is in a file under `results/`.
- Say what is implemented, simulated and planned. Never round a result up.
- Keep documents short and plain.
- Do not commit or push. The author does that.

## Checks before handing work back
```bash
python3 -m unittest discover tests
python3 replay/replay.py turns replay/dev-turns.tsv   # needs Ollama
```
