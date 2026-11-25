# Design notes

Short answers to what the module's lectures ask of a Phase 2 project. The report argues the main choices; this page holds the rest.

## A contract for every action (Lecture 13)

A contract says how much TurnCheck may do on its own. *Execute and report*: it acts, shows what it did, and the candidate can undo it. *Assist*: it prepares the options and the candidate picks one.

| Action | Contract | Why |
|---|---|---|
| Record a turn as the answer, when both readings agree | Execute and report | The label shows at once and one tap takes it back until the next turn. Asking about every turn would turn the candidate's approval into a reflex. |
| Decide how to read a turn, when the readings disagree or the model fails | Assist | TurnCheck prepares the options and the candidate picks one. A wrong guess here could cost the candidate an answer. |
| Reply from the sheet, or decline | Execute and report | Every reply is prepared text that any candidate can get. The label and the entry id report it, and "That was my answer" undoes the reading. |
| Wait on thinking aloud | No action, and it is shown | Doing nothing is also a decision, so the label says so. |
| Ask what next, after two thinking-aloud turns in a row | Assist | The candidate chooses: keep thinking, repeat the question, or move on. |
| Score the candidate | Not automated; the record only advises | A score cannot be undone by the candidate and they cannot see it. A person scores. |

## One pattern, and the case against it (Lecture 14)

**Pattern:** a fixed workflow that makes at most two model calls per turn, with a person in the loop where the readings disagree. There is no agent loop, because every step is known in advance.

**The case against it:**
- It cannot answer a fair question the sheet did not foresee. It declines. That is the price of every candidate getting the same help.
- The second reading only looks at the wording, not the meaning. When both readings are wrong together, nothing catches it but the candidate's tap. The stress turns found two: "I'm assuming the duplicates are exact copies" and "I don't know how much detail you want" were recorded as answers.
- A turn that is an answer and a question at once ("I'd filter on the updated timestamp, does that make sense") gets one label. All 6 such stress turns were recorded as plain answers, so the check got no reply.

## The graph, and the edge still missing (Lecture 15)

The graph is `turn-graph.drawio` (and `.svg`). The code is `turncheck/controller.py`, and every edge (an arrow in the graph) has a test in `tests/test_controller.py`.

**Not handled yet:** a correction after the candidate's next turn. The misread stays in the record: visible at the end, but no longer fixable. Planned: let the candidate flag a line on the final record.

`AGENTS.md` at the top of the repository holds the rules given to the AI coding assistant.

## The numbers for one inference (Lecture 18)

The inference, in the candidate's words: "Was that my answer?"

- **No confidence threshold.** On the dev turns the model's probability for its own label was 0.95 or higher on 36 of 41 turns, including 8 of the 9 labels it got wrong (`results/2026-11-14-dev-turns-run3.txt`). A number that barely moves cannot set a threshold. So the bands are: both readings agree, act; they disagree, ask; thinking aloud, wait.
- **What the stress turns add.** There the probability was below 0.95 on 4 of the 5 wrong labels (0.74, 0.76, 0.87, 0.94), but 0.97 or more on all 6 answer-and-check turns (`results/2026-11-15-stress-turns.txt`). So a threshold might catch some questions phrased as statements and would miss the rest. It is not used. Trying it as a third reading is a next step.
- **2:** thinking-aloud turns in a row before TurnCheck offers a way out.
- **10 seconds:** the longest TurnCheck waits for the model before it asks the candidate instead.
- **Until the next turn:** how long a reading can be corrected.
- **Asymmetry:** TurnCheck leans towards asking. A question recorded as an answer can cost the candidate that answer; an extra question costs one tap.
- **What the candidate sees:** the label under each turn, with both readings. **How they overrule it:** one tap on that label. **What the log keeps:** both readings, the path taken through the graph and every model call.

None of these numbers has been tested with people, and every test turn so far was written by the AI assistant.

## Sensors and their privacy cost (Lecture 16)

| What is sensed | The claim it supports | Privacy cost |
|---|---|---|
| The words of each turn (typed now, speech planned) | "this turn is an answer, a question, or thinking aloud" | The full text of a job interview. It is read by a model on the same computer, saved to one file there, and sent nowhere. |
| Taps on the buttons | "that reading was wrong", "this is what I meant" | Low. They go into the record, which the candidate sees. |
| A microphone (planned) | the same claims, from speech | Higher. A voice identifies a person, and recognition errors fall unevenly across accents. |

Not collected: keystroke timing, camera, or anything about the candidate beyond the turns.

## Why each input channel is there (Lecture 17)

- **Typed turns** (spoken later): the main channel.
- **Buttons:** recoverability. They are the way out when the first channel is misread.

The two readings are not two channels, because both read the same words. They usually fail in different places, which is what makes a disagreement worth asking about. When they fail together, only the candidate can fix it.

## World layer (Lectures 19 and 20)

None. TurnCheck does not need to know what is where.
