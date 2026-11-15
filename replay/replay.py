"""Replay scripted turns, or a scripted interview, through the same controller the screen uses.

    python3 replay/replay.py turns replay/dev-turns.tsv
        Reads each turn on its own, at its question. Writes one line per turn and a
        summary to results/, so every decision can be checked by hand.
        Each line of the file:  question number | answer, question, thinking or unsure | the turn
        A question may add a fourth part: the sheet entry it should get (or none).

    python3 replay/replay.py interview replay/storyboard-interview.json
        Runs the listed actions in order and saves every step and screen to
        results/traces/. View a step at http://localhost:8000/?trace=NAME&step=N

Needs Ollama running with the model (default qwen2.5:7b).
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from turncheck.controller import Interview, apply  # noqa: E402
from turncheck.readings import OllamaReader  # noqa: E402

MEANT = ("answer", "question", "thinking", "unsure")
TREATED_AS = {"record": "answer", "clarify": "question", "decline": "question", "wait": "thinking", "ask": "unsure"}
MODEL_LABEL = {"answer": "answer", "question": "question", "thinking": "unfinished"}


def read_turns(path):
    turns = []
    for number, line in enumerate(path.read_text().splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = [part.strip() for part in line.split("|")]
        if len(parts) not in (3, 4) or not parts[0].isdigit() or parts[1] not in MEANT or not parts[2]:
            sys.exit(f"{path.name} line {number}: expected  question number | {' / '.join(MEANT)} | the turn")
        turns.append((int(parts[0]), parts[1], parts[2], parts[3] if len(parts) == 4 else None))
    return turns


def verdict(meant, treated):
    if treated == meant:
        return "ok"
    if treated == "unsure":
        return "asked"
    if meant == "question" and treated == "answer":
        return "MISS"
    if meant == "answer" and treated == "question":
        return "FALSE ALARM"
    return "other"


def fresh_path(folder, stem, suffix):
    """Never overwrite an earlier run: a second run on the same day gets -run2, and so on."""
    path, run = folder / f"{stem}{suffix}", 1
    while path.exists():
        run += 1
        path = folder / f"{stem}-run{run}{suffix}"
    return path


def replay_turns(path, script, script_name, reader):
    turns, rows, saved = read_turns(path), [], []
    if not turns:
        sys.exit(f"{path.name} has no turns yet.")
    for question, meant, text, wanted in turns:
        interview = Interview(script, reader, start_at=question)
        interview.start()
        entry = apply(interview, {"turn": text})["trace"][0]
        label_call = entry["calls"][0]
        treated = TREATED_AS[entry["did"]]
        steps, tap = [entry], ""
        # A question that was not treated as one: make the single tap the candidate would make, to see the reply.
        if meant == "question" and treated == "unsure":
            tap, steps = "A question", steps + apply(interview, {"choose": "question"})["trace"]
        elif meant == "question" and treated in ("thinking", "answer"):
            tap, steps = "That was a question", steps + apply(interview, {"correct": "last", "to": "question"})["trace"]
        picks = [call["entry"] or "none" for step in steps for call in step["calls"] if call["purpose"] == "entry"]
        rows.append({"question": question, "meant": meant, "text": entry["action"]["turn"], "did": entry["did"],
                     "treated": treated, "verdict": verdict(meant, treated), "label": label_call["label"],
                     "p": label_call["p"], "wording": entry["wording_says_question"],
                     "entry": picks[-1] if picks else None, "tap": tap, "wanted": wanted,
                     "seconds": sum(call["ms"] for call in entry["calls"]) / 1000,
                     "label_seconds": label_call["ms"] / 1000})
        saved.append({"question": question, "meant": meant, "wanted_entry": wanted, "steps": steps})

    lines = [f"{len(rows)} turns from {path.name} · model {reader.model} · script {script_name} · "
             f"{time.strftime('%Y-%m-%d %H:%M')}", "Question marks are removed before reading, as a transcript may not have them.", ""]
    for row in rows:
        did = row["did"] + (f" {row['entry']}" if row["treated"] == "question" else "")
        p = "p=?" if row["p"] is None else f"p={row['p']:.2f}"
        lines.append(f"{row['verdict']:11} | Q{row['question']} meant {row['meant']:8} | did {did:16} | "
                     f"model {str(row['label']):10} {p} | wording {'question' if row['wording'] else '-':8} | "
                     f"{row['seconds']:.2f}s | {row['text']}")

    count = lambda test: sum(1 for row in rows if test(row))
    lines += ["", f"Handled as meant: {count(lambda r: r['verdict'] == 'ok')} of {len(rows)}"]
    lines.append("  " + " · ".join(
        f"{meant} {count(lambda r: r['meant'] == meant and r['verdict'] == 'ok')}/{count(lambda r: r['meant'] == meant)}"
        for meant in MEANT if count(lambda r: r["meant"] == meant)))
    lines.append("Not as meant:")
    lines.append(f"  asked instead (one extra tap; the candidate decides): {count(lambda r: r['verdict'] == 'asked')}")
    lines.append(f"  MISS (a question recorded as an answer): {count(lambda r: r['verdict'] == 'MISS')}")
    lines.append(f"  FALSE ALARM (an answer treated as a question): {count(lambda r: r['verdict'] == 'FALSE ALARM')}")
    for row in rows:
        if row["verdict"] == "other":
            lines.append(f"  other: meant {row['meant']}, treated as {row['treated']}: {row['text']}")
    lines.append(f"A fixed script would have recorded all {count(lambda r: r['meant'] == 'question')} question turns "
                 f"and {count(lambda r: r['meant'] == 'thinking')} thinking turns as answers.")

    clear = [row for row in rows if row["meant"] in MODEL_LABEL and row["label"]]
    wrong = [row for row in clear if row["label"] != MODEL_LABEL[row["meant"]]]
    sure = [row for row in clear if row["p"] is not None and row["p"] >= 0.95]
    lines += ["", f"The model alone, against what was meant (unsure turns left out): "
                  f"{len(clear) - len(wrong)} of {len(clear)} labels right"]
    lines.append(f"Its probability for its own label was 0.95 or higher on {len(sure)} of {len(clear)} turns"
                 + (f"; on the {len(wrong)} it got wrong: " + ", ".join("?" if r["p"] is None else f"{r['p']:.2f}" for r in wrong)
                    if wrong else ""))
    label_times = [row["label_seconds"] for row in rows]
    lines.append(f"Label call: median {statistics.median(label_times):.2f}s, slowest {max(label_times):.2f}s. "
                 f"A turn read as a question needs a second call.")
    questions = [row for row in rows if row["entry"]]
    if questions:
        named = [row for row in questions if row["wanted"]]
        lines += ["", "Sheet entry given to each question (check these by hand). Where one tap was needed first, it is shown."]
        if named:
            lines.append(f"Entry as the file expects: {sum(row['entry'] == row['wanted'] for row in named)} of {len(named)} "
                         f"questions that name one")
        for row in questions:
            mark = "" if not row["wanted"] else ("ok " if row["entry"] == row["wanted"] else f"NO, expected {row['wanted']} ")
            lines.append(f"  Q{row['question']} {row['entry']:9} {mark:22}| {row['text']}"
                         + (f"   [after tapping '{row['tap']}']" if row["tap"] else ""))

    out = fresh_path(ROOT / "results", f"{time.strftime('%Y-%m-%d')}-{path.stem}", ".txt")
    out.write_text("\n".join(lines) + "\n")
    out.with_suffix(".json").write_text(json.dumps(saved, indent=1, ensure_ascii=False))
    print("\n".join(lines))
    print(f"\nSaved to {out.relative_to(ROOT)} (and .json with what was sent to the model and what came back)")


def replay_interview(path, script, script_name, reader):
    plan = json.loads(path.read_text())
    interview = Interview(script, reader, start_at=plan.get("start_at", 1))
    steps = [apply(interview, {"open": True}), apply(interview, {"start": True})]  # the start screen, then question 1
    steps += [apply(interview, action) for action in plan["actions"]]
    for number, step in enumerate(steps):
        for entry in step["trace"]:
            print(f"step {number}: {entry['action']}  ->  {entry['edge']}  ->  {entry['did']}")
    out = ROOT / "results" / "traces" / path.name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"name": path.stem, "about": plan.get("about", ""), "script": script_name,
                               "model": reader.model, "start_at": plan.get("start_at", 1),
                               "made": time.strftime("%Y-%m-%d"), "steps": steps}, indent=1, ensure_ascii=False))
    print(f"Saved to {out.relative_to(ROOT)}: view a step at http://localhost:8000/?trace={path.stem}&step=N")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("mode", choices=("turns", "interview"))
    parser.add_argument("file", type=Path)
    parser.add_argument("--model", default="qwen2.5:7b")
    parser.add_argument("--script", type=Path, default=ROOT / "interview" / "data-engineer.json")
    args = parser.parse_args()

    reader = OllamaReader(args.model)
    if not reader.warm_up():
        sys.exit("Ollama is not answering. Start it, and check the model with: ollama list")
    script = json.loads(args.script.read_text())
    (replay_turns if args.mode == "turns" else replay_interview)(args.file, script, args.script.name, reader)


if __name__ == "__main__":
    main()
