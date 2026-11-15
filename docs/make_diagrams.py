"""Builds the two diagrams (architecture, turn graph) from one description each.

For every diagram it writes, next to this file,
  NAME.drawio   to open and edit in draw.io (app.diagrams.net)
  NAME.svg      the same boxes, lines and words, drawn directly, for the README and the report
and it checks the geometry first: no two lines cross, no line runs through a box
or a label, no two boxes or labels overlap, and every line of text fits its box.

    python3 docs/make_diagrams.py       (standard library only)

Style: black on white, one line weight. Line style carries the status:
solid = implemented, dashed = simulated, dotted = planned.
"""
from html import escape
from pathlib import Path

HERE = Path(__file__).resolve().parent
TITLE, SUB, SMALL = 15, 13, 12          # font sizes in px
DASH = {"implemented": None, "simulated": "6 4", "planned": "1 4"}

# Helvetica advance widths per 1000 units, enough to check that text fits its box.
W = {" ": 278, ",": 278, ".": 278, ":": 278, ";": 278, "'": 191, "-": 333, "(": 333, ")": 333, "/": 278, "?": 556,
     "+": 584, "·": 278, "i": 222, "j": 222, "l": 222, "f": 278, "t": 278, "r": 333, "c": 500, "k": 500, "s": 500,
     "v": 500, "x": 500, "y": 500, "z": 500, "m": 833, "w": 722, "I": 278, "J": 500, "L": 556, "F": 611, "T": 611,
     "Z": 611, "M": 833, "W": 944, "C": 722, "D": 722, "H": 722, "N": 722, "R": 722, "U": 722, "G": 778, "O": 778,
     "Q": 778}


def text_width(text, size, bold=False):
    units = sum(W.get(ch, 667 if ch.isupper() else 556) for ch in text)
    return units / 1000 * size * (1.08 if bold else 1.0)


class Diagram:
    def __init__(self, name, width, height):
        self.name, self.width, self.height = name, width, height
        self.boxes, self.edges, self.texts, self.problems = {}, [], [], []

    # ---- describing the diagram ----------------------------------------------------------

    def box(self, key, x, y, w, h, title, lines=(), kind="process", status="implemented", tag=None):
        """kind: process, person, store, decision or terminal. tag: a last line in italics."""
        self.boxes[key] = dict(key=key, x=x, y=y, w=w, h=h, title=title, lines=list(lines), kind=kind,
                               status=status, tag=tag)

    def edge(self, points, src=None, dst=None, status="implemented", arrows="end"):
        """points: every corner, from the border of src to the border of dst. arrows: end, both or none."""
        self.edges.append(dict(points=points, src=src, dst=dst, status=status, arrows=arrows))

    def text(self, x, y, w, h, lines, align="center", italic=False, size=SMALL):
        self.texts.append(dict(x=x, y=y, w=w, h=h, lines=list(lines), align=align, italic=italic, size=size))

    # ---- checking it ---------------------------------------------------------------------

    def check(self):
        def segments(edge):
            return list(zip(edge["points"], edge["points"][1:]))

        def inside(rect, seg, shrink=1.0):
            """Does an axis-parallel segment pass through the inside of a rectangle?"""
            (x1, y1), (x2, y2) = seg
            left, top = rect["x"] + shrink, rect["y"] + shrink
            right, bottom = rect["x"] + rect["w"] - shrink, rect["y"] + rect["h"] - shrink
            return max(x1, x2) > left and min(x1, x2) < right and max(y1, y2) > top and min(y1, y2) < bottom

        def overlap(a, b):
            return (a["x"] < b["x"] + b["w"] and b["x"] < a["x"] + a["w"]
                    and a["y"] < b["y"] + b["h"] and b["y"] < a["y"] + a["h"])

        def cross(s, t):
            (ax, ay), (bx, by) = s
            (cx, cy), (dx, dy) = t
            if ax == bx and cx == dx:      # both vertical
                return ax == cx and max(min(ay, by), min(cy, dy)) < min(max(ay, by), max(cy, dy))
            if ay == by and cy == dy:      # both horizontal
                return ay == cy and max(min(ax, bx), min(cx, dx)) < min(max(ax, bx), max(cx, dx))
            if ay == by:                   # make s the vertical one
                (ax, ay), (bx, by), (cx, cy), (dx, dy) = (cx, cy), (dx, dy), (ax, ay), (bx, by)
            return min(cx, dx) < ax < max(cx, dx) and min(ay, by) < cy < max(ay, by)

        for edge in self.edges:
            for (x1, y1), (x2, y2) in segments(edge):
                if x1 != x2 and y1 != y2:
                    self.problems.append(f"a line is not horizontal or vertical: {(x1, y1)} to {(x2, y2)}")
        for i, a in enumerate(self.edges):
            for b in self.edges[i + 1:]:
                related = (a["src"] and a["src"] == b["src"]) or (a["dst"] and a["dst"] == b["dst"])
                for s in segments(a):
                    for t in segments(b):
                        if cross(s, t) and not (related and (s[0][0] == s[1][0]) == (t[0][0] == t[1][0])):
                            self.problems.append(f"lines cross or overlap: {s} and {t}")
        for edge in self.edges:
            for seg in segments(edge):
                for box in self.boxes.values():
                    if inside(box, seg):
                        self.problems.append(f"a line runs through the box '{box['title']}': {seg}")
                for label in self.texts:
                    if inside(label, seg, shrink=0):
                        self.problems.append(f"a line runs through the label {label['lines']}: {seg}")
        things = list(self.boxes.values()) + self.texts
        for i, a in enumerate(things):
            for b in things[i + 1:]:
                if overlap(a, b):
                    self.problems.append(f"overlap: {a.get('title', a.get('lines'))} and {b.get('title', b.get('lines'))}")
        for thing in things:
            if thing["x"] < 0 or thing["y"] < 0 or thing["x"] + thing["w"] > self.width or thing["y"] + thing["h"] > self.height:
                self.problems.append(f"outside the drawing: {thing.get('title', thing.get('lines'))}")
        for box in self.boxes.values():
            room = box["w"] * (0.56 if box["kind"] == "decision" else 1.0) - (10 if box["kind"] != "decision" else 0)
            rows = [(box["title"], TITLE, True)] + [(line, SUB, False) for line in box["lines"]]
            rows += [(box["tag"], SMALL, False)] if box["tag"] else []
            for words, size, bold in rows:
                if text_width(words, size, bold) > room:
                    self.problems.append(f"text too wide for '{box['title']}': '{words}' "
                                         f"({text_width(words, size, bold):.0f} px in {room:.0f})")
            if sum(size * 1.25 for _, size, _ in rows) > box["h"] * (0.62 if box["kind"] == "decision" else 1.0) - 6:
                self.problems.append(f"text too tall for '{box['title']}'")
        for label in self.texts:
            for words in label["lines"]:
                if text_width(words, label["size"]) > label["w"]:
                    self.problems.append(f"label too wide: '{words}' ({text_width(words, label['size']):.0f} px in {label['w']})")
        return self.problems

    # ---- draw.io -------------------------------------------------------------------------

    def drawio(self):
        # Every line break is explicit. Without whiteSpace=wrap draw.io keeps them and never re-wraps a line.
        common = "html=1;strokeColor=#000000;strokeWidth=1.5;fontColor=#000000;fontFamily=Helvetica;"
        shapes = {"process": "rounded=0;fillColor=#FFFFFF;", "person": "rounded=1;arcSize=50;fillColor=#F2F2F2;",
                  "terminal": "rounded=1;arcSize=50;fillColor=#FFFFFF;", "decision": "rhombus;fillColor=#FFFFFF;",
                  "store": "shape=cylinder3;boundedLbl=1;backgroundOutline=1;size=9;fillColor=#FFFFFF;"}
        dash = lambda status: f"dashed=1;dashPattern={DASH[status]};" if DASH[status] else ""
        cells = []
        for box in self.boxes.values():
            value = f"<b>{escape(box['title'])}</b>"
            if box["lines"]:
                value += f'<br><font style="font-size:{SUB}px">' + "<br>".join(escape(line) for line in box["lines"]) + "</font>"
            if box["tag"]:
                value += f'<br><i style="font-size:{SMALL}px">{escape(box["tag"])}</i>'
            cells.append(f'        <mxCell id="{box["key"]}" value="{escape(value, quote=True)}" '
                         f'style="{shapes[box["kind"]]}{common}fontSize={TITLE};{dash(box["status"])}" vertex="1" parent="1">\n'
                         f'          <mxGeometry x="{box["x"]}" y="{box["y"]}" width="{box["w"]}" height="{box["h"]}" as="geometry" />\n'
                         f'        </mxCell>')
        for number, edge in enumerate(self.edges, 1):
            style = ("edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;strokeColor=#000000;strokeWidth=1.5;"
                     + {"end": "endArrow=block;endFill=1;", "both": "endArrow=block;endFill=1;startArrow=block;startFill=1;",
                        "none": "endArrow=none;"}[edge["arrows"]] + dash(edge["status"]))
            ends, attach = "", ""
            for role, key, point in (("source", edge["src"], edge["points"][0]), ("target", edge["dst"], edge["points"][-1])):
                word = "exit" if role == "source" else "entry"
                if key:
                    box = self.boxes[key]
                    fx, fy = (point[0] - box["x"]) / box["w"], (point[1] - box["y"]) / box["h"]
                    style += f"{word}X={fx:.4g};{word}Y={fy:.4g};{word}Dx=0;{word}Dy=0;"
                    attach += f' {role}="{key}"'
                else:
                    ends += f'            <mxPoint x="{point[0]}" y="{point[1]}" as="{role}Point" />\n'
            corners = "".join(f'<mxPoint x="{x}" y="{y}" />' for x, y in edge["points"][1:-1])
            corners = f'            <Array as="points">{corners}</Array>\n' if corners else ""
            cells.append(f'        <mxCell id="line{number}" style="{style}" edge="1" parent="1"{attach}>\n'
                         f'          <mxGeometry relative="1" as="geometry">\n{ends}{corners}          </mxGeometry>\n        </mxCell>')
        for number, label in enumerate(self.texts, 1):
            words = "<br>".join(escape(line) for line in label["lines"])
            words = f"<i>{words}</i>" if label["italic"] else words
            cells.append(f'        <mxCell id="label{number}" value="{escape(words, quote=True)}" '
                         f'style="text;html=1;strokeColor=none;fillColor=none;align={label["align"]};verticalAlign=middle;'
                         f'fontSize={label["size"]};fontColor=#000000;fontFamily=Helvetica;" vertex="1" parent="1">\n'
                         f'          <mxGeometry x="{label["x"]}" y="{label["y"]}" width="{label["w"]}" height="{label["h"]}" as="geometry" />\n'
                         f'        </mxCell>')
        return (f'<mxfile host="app.diagrams.net">\n  <diagram name="{escape(self.name)}" id="{self.name.lower().replace(" ", "-")}">\n'
                f'    <mxGraphModel dx="1200" dy="800" grid="1" gridSize="5" guides="1" tooltips="1" connect="1" arrows="1" '
                f'fold="1" page="1" pageScale="1" pageWidth="{self.width}" pageHeight="{self.height}" math="0" shadow="0">\n'
                f'      <root>\n        <mxCell id="0" />\n        <mxCell id="1" parent="0" />\n'
                + "\n".join(cells) + "\n      </root>\n    </mxGraphModel>\n  </diagram>\n</mxfile>\n")

    # ---- svg -----------------------------------------------------------------------------

    def svg(self):
        out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" height="{self.height}" '
               f'viewBox="0 0 {self.width} {self.height}" font-family="Helvetica, Arial, sans-serif" fill="#000">',
               f'<rect width="{self.width}" height="{self.height}" fill="#fff"/>']
        pen = lambda status: ('stroke="#000" stroke-width="1.5"'
                              + (f' stroke-dasharray="{DASH[status]}"' if DASH[status] else "")
                              + (' stroke-linecap="round"' if status == "planned" else ""))
        for edge in self.edges:
            points = [list(p) for p in edge["points"]]
            heads = []
            for at, toward, wanted in ((-1, -2, edge["arrows"] in ("end", "both")), (0, 1, edge["arrows"] == "both")):
                if not wanted:
                    continue
                (x, y), (px, py) = points[at], points[toward]
                ux, uy = (x - px) / (abs(x - px) + abs(y - py)), (y - py) / (abs(x - px) + abs(y - py))
                heads.append(f'<path d="M{x},{y} L{x - 9 * ux - 4 * uy},{y - 9 * uy - 4 * ux} '
                             f'L{x - 9 * ux + 4 * uy},{y - 9 * uy + 4 * ux} Z"/>')
                points[at] = [x - 8 * ux, y - 8 * uy]  # the line stops inside the arrowhead
            path = " ".join(f"{x},{y}" for x, y in points)
            out.append(f'<polyline points="{path}" fill="none" {pen(edge["status"])}/>' + "".join(heads))
        for box in self.boxes.values():
            x, y, w, h = box["x"], box["y"], box["w"], box["h"]
            if box["kind"] == "store":
                s = 9
                out.append(f'<path d="M{x},{y + s} A{w / 2},{s} 0 0 1 {x + w},{y + s} L{x + w},{y + h - s} '
                           f'A{w / 2},{s} 0 0 1 {x},{y + h - s} Z" fill="#fff" {pen(box["status"])}/>'
                           f'<path d="M{x},{y + s} A{w / 2},{s} 0 0 0 {x + w},{y + s}" fill="none" {pen(box["status"])}/>')
            elif box["kind"] == "decision":
                out.append(f'<polygon points="{x + w / 2},{y} {x + w},{y + h / 2} {x + w / 2},{y + h} {x},{y + h / 2}" '
                           f'fill="#fff" {pen(box["status"])}/>')
            else:
                radius = h / 2 if box["kind"] in ("person", "terminal") else 0
                fill = "#f2f2f2" if box["kind"] == "person" else "#fff"
                out.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{fill}" {pen(box["status"])}/>')
            rows = [(box["title"], TITLE, ' font-weight="bold"')] + [(line, SUB, "") for line in box["lines"]]
            rows += [(box["tag"], SMALL, ' font-style="italic"')] if box["tag"] else []
            total = sum(size * 1.25 for _, size, _ in rows)
            top = y + (h - total) / 2 + (9 if box["kind"] == "store" else 0)
            for words, size, style in rows:
                out.append(f'<text x="{x + w / 2}" y="{top + size * 0.95:.1f}" font-size="{size}" text-anchor="middle"{style}>'
                           f'{escape(words)}</text>')
                top += size * 1.25
        for label in self.texts:
            anchor = {"center": "middle", "left": "start", "right": "end"}[label["align"]]
            x = label["x"] + {"center": label["w"] / 2, "left": 0, "right": label["w"]}[label["align"]]
            top = label["y"] + (label["h"] - len(label["lines"]) * label["size"] * 1.25) / 2
            for words in label["lines"]:
                out.append(f'<text x="{x}" y="{top + label["size"] * 0.95:.1f}" font-size="{label["size"]}" text-anchor="{anchor}"'
                           + (' font-style="italic"' if label["italic"] else "") + f'>{escape(words)}</text>')
                top += label["size"] * 1.25
        return "\n".join(out) + "\n</svg>\n"

    def write(self, stem):
        problems = self.check()
        for problem in problems:
            print(f"  {stem}: {problem}")
        (HERE / f"{stem}.drawio").write_text(self.drawio())
        (HERE / f"{stem}.svg").write_text(self.svg())
        print(f"{stem}: {len(self.boxes)} boxes, {len(self.edges)} lines, {len(self.texts)} labels, "
              f"{self.width} x {self.height} px, {len(problems)} problems")
        return not problems


def architecture():
    d = Diagram("Architecture", 860, 535)
    # People, and what is fixed before the interview starts.
    d.box("candidate", 55, 24, 120, 48, "Candidate", kind="person")
    d.box("script", 300, 6, 145, 86, "Interview script", ["5 questions, sheets,", "fixed wording"], kind="store")
    d.box("harness", 455, 12, 145, 74, "Replay harness", ["scripted turns,", "saved interviews"])
    d.box("assessor", 695, 18, 140, 58, "Human assessor", ["does the scoring"], kind="person")
    # The path of one turn.
    d.box("screen", 40, 170, 150, 100, "Screen", ["question, readings,", "buttons, state"])
    d.box("controller", 300, 170, 300, 100, "Controller", ["fixed workflow: act, ask or wait", "checks every model reply"])
    d.box("record", 690, 160, 150, 120, "Interview record", ["answers, replies,", "asks, corrections,", "no score"], kind="store")
    # The two readings, the trace, and speech.
    d.box("model", 300, 350, 145, 86, "Model reading", ["qwen2.5 7B, local:", "label or entry id"])
    d.box("wording", 455, 350, 145, 86, "Wording reading", ["rules: phrased", "as a question?"])
    d.box("trace", 690, 342, 150, 102, "Trace", ["sent, reply,", "edge taken"], kind="store")
    d.box("speech", 40, 350, 150, 86, "Speech input", ["simulated: typed,", "no question marks"], status="simulated")
    d.box("voice", 40, 462, 150, 66, "Real speech", ["recognition, voice"], status="planned")

    d.edge([(95, 72), (95, 170)], "candidate", "screen")
    d.text(46, 104, 42, 34, ["turns,", "taps"], align="right")
    d.edge([(135, 170), (135, 72)], "screen", "candidate")
    d.text(143, 96, 62, 50, ["question,", "readings,", "replies"], align="left")
    d.edge([(190, 200), (300, 200)], "screen", "controller")
    d.text(195, 164, 100, 32, ["turn, choice,", "correction"])
    d.edge([(300, 245), (190, 245)], "controller", "screen")
    d.text(195, 249, 100, 18, ["what to show"])
    d.edge([(372, 92), (372, 170)], "script", "controller")
    d.text(304, 114, 62, 34, ["read at", "the start"], align="right")
    d.edge([(527, 86), (527, 170)], "harness", "controller")
    d.text(535, 111, 90, 34, ["same actions", "as the screen"], align="left")
    d.edge([(372, 270), (372, 350)], "controller", "model", arrows="both")
    d.text(380, 286, 80, 50, ["turn in;", "label or", "entry id out"], align="left")
    d.edge([(527, 270), (527, 350)], "controller", "wording", arrows="both")
    d.text(535, 286, 80, 50, ["turn in;", "question", "or not out"], align="left")
    d.edge([(600, 205), (690, 205)], "controller", "record")
    d.text(603, 185, 84, 17, ["what happened"])
    d.edge([(600, 250), (645, 250), (645, 393), (690, 393)], "controller", "trace")
    d.text(605, 398, 80, 34, ["every call", "and edge"])
    d.edge([(765, 160), (765, 76)], "record", "assessor", status="planned")
    d.text(773, 98, 84, 34, ["assessor view", "planned"], align="left")
    d.edge([(115, 270), (115, 350)], "screen", "speech", status="simulated", arrows="none")
    d.edge([(115, 436), (115, 462)], "speech", "voice", status="planned", arrows="none")

    # Legend.
    d.box("k1", 262, 488, 112, 28, "implemented")
    d.box("k2", 384, 488, 100, 28, "simulated", status="simulated")
    d.box("k3", 494, 488, 100, 28, "planned", status="planned")
    d.box("k4", 604, 488, 100, 28, "person", kind="person")
    d.box("k5", 714, 480, 126, 44, "stored data", kind="store")
    return d.write("architecture")


def turn_graph():
    d = Diagram("Turn graph", 830, 640)
    d.box("turn", 335, 8, 160, 38, "Candidate's turn", kind="terminal")
    d.box("read", 305, 70, 220, 50, "Read it twice", ["model label + wording rules"])
    d.box("agree", 300, 144, 230, 86, "Do the two", ["readings agree?"], kind="decision")
    d.box("ask", 600, 150, 200, 74, "Ask the candidate", ["answer, question", "or still thinking?"], tag="assist: the candidate decides")
    d.box("fix", 30, 258, 200, 70, "One-tap correction", ["of the last reading,", "until the next turn"], kind="terminal")
    d.box("as", 350, 258, 130, 70, "Read as?", kind="decision")

    d.edge([(415, 46), (415, 70)], "turn", "read")
    d.edge([(415, 120), (415, 144)], "read", "agree")
    d.edge([(525, 95), (700, 95), (700, 150)], "read", "ask")
    d.text(535, 76, 160, 17, ["no usable label"])
    d.edge([(530, 187), (600, 187)], "agree", "ask")
    d.text(545, 168, 40, 17, ["no"])
    d.edge([(415, 230), (415, 258)], "agree", "as")
    d.text(422, 235, 40, 17, ["yes"], align="left")
    d.edge([(700, 224), (700, 293), (480, 293)], "ask", "as")
    d.text(520, 273, 150, 17, ["as the candidate says"])
    d.edge([(230, 293), (350, 293)], "fix", "as")
    d.text(240, 273, 100, 17, ["as corrected"])

    # Three ways a turn can be read.
    d.box("wait", 30, 380, 200, 66, "Wait", ["say nothing, keep the words"], tag="no action, and it is shown")
    d.box("pick", 315, 380, 200, 66, "Pick a sheet entry", ["model names an id,", "code checks the sheet"])
    d.box("record", 600, 380, 200, 66, "Record the answer", ["undo until the next turn"], tag="execute and report")
    d.edge([(415, 328), (415, 354), (130, 354), (130, 380)], "as", "wait")
    d.text(140, 334, 100, 17, ["still thinking"], align="left")
    d.edge([(415, 328), (415, 380)], "as", "pick")
    d.text(422, 358, 70, 17, ["question"], align="left")
    d.edge([(415, 328), (415, 354), (700, 354), (700, 380)], "as", "record")
    d.text(640, 334, 55, 17, ["answer"], align="right")

    d.box("stuck", 30, 486, 200, 74, "Ask what next", ["keep thinking, repeat", "or move on?"], tag="assist: the candidate decides")
    d.box("say", 250, 486, 155, 74, "Say the entry", ["fixed text, logged"], tag="execute and report")
    d.box("decline", 425, 486, 155, 74, "Decline, say why", ["no hint is given"], tag="execute and report")
    d.box("next", 600, 486, 200, 74, "Next question", ["or, after the last one,", "the record for a person"], tag="advise: the person scores")
    d.edge([(130, 446), (130, 486)], "wait", "stuck")
    d.text(138, 457, 92, 17, ["second in a row"], align="left")
    d.edge([(350, 446), (350, 486)], "pick", "say")
    d.text(300, 457, 44, 17, ["found"], align="right")
    d.edge([(480, 446), (480, 486)], "pick", "decline")
    d.text(488, 457, 85, 17, ["none fits"], align="left")
    d.edge([(700, 446), (700, 486)], "record", "next")

    # Every path ends by waiting for the next turn.
    d.box("end", 320, 596, 190, 38, "Wait for the next turn", kind="terminal")
    d.edge([(30, 413), (14, 413), (14, 578), (415, 578), (415, 596)], "wait", "end")
    d.edge([(130, 560), (130, 578), (415, 578), (415, 596)], "stuck", "end")
    d.edge([(327, 560), (327, 578), (415, 578), (415, 596)], "say", "end")
    d.edge([(502, 560), (502, 578), (415, 578), (415, 596)], "decline", "end")
    d.edge([(700, 560), (700, 578), (415, 578), (415, 596)], "next", "end")
    d.text(540, 598, 280, 34, ["Italics: the interaction contract for", "that action. Scoring is never automated."],
           align="left", italic=True)
    return d.write("turn-graph")


if __name__ == "__main__":
    import sys
    sys.exit(0 if architecture() & turn_graph() else 1)
