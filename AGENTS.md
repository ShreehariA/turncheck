# AGENTS.md

Rules for any coding agent working in this repository.

## What this is
TurnCheck is a prototype AI interviewer that reads each candidate turn (answer, question or unfinished) before it counts.
Coursework for Intelligent Interactive Systems, University of Birmingham.

## Rules
- Python standard library only. Ask before adding any dependency.
- No paid APIs and no keys. The model runs locally through Ollama.
- The model never writes text the candidate reads. It returns a label or a sheet entry id. The controller checks it and uses the fixed text in `interview/*.json`.
- Every edge of the turn graph in `turncheck/controller.py` has a test in `tests/`. Add the test with the edge.
- The rule (prompts, wording check, turn graph, sheets) is frozen at the tag `frozen-v1`. Never tune it on `replay/stress-turns.tsv` or on held-out turns. Debug with `replay/dev-turns.tsv`, and report any later change next to the old result.
- Never state a result in the README or anywhere else unless it is in a file under `results/`.
- Say what is implemented, simulated and planned. Never round a result up.
- Keep documents short and plain.
- Commit and push only when the author asks. Never write that a person did something the agent did.

## Checks before handing work back
```bash
python3 -m unittest discover tests
python3 replay/replay.py turns replay/dev-turns.tsv   # needs Ollama
```
