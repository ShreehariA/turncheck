// The page only draws what the server sends. All decisions are made in turncheck/controller.py.
const $ = (id) => document.getElementById(id);
const params = new URLSearchParams(location.search);
let current = null;
let busy = false;

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function candidate(item) {
  const li = el("li", "candidate");
  li.append(el("div", "bubble", item.text));
  if (item.chip) li.append(el("div", "", ""), el("span", "chip", item.chip));
  if (item.why) li.append(el("div", "why", item.why));
  if (item.fix) {
    const row = el("div", "fixes");
    for (const fix of item.fix) {
      const button = el("button", "fix", fix.label);
      button.onclick = () => send("api/correct", { id: item.id, to: fix.to });
      row.append(button);
    }
    li.append(row);
  }
  return li;
}

function interviewer(item) {
  if (item.kind === "question") return el("li", "divider", `Question ${item.n} of ${item.of}`);
  const li = el("li", "interviewer");
  li.append(el("div", "bubble", item.text));
  if (item.tag) li.append(el("div", "tag", item.tag));
  return li;
}

function record(rows) {
  const li = el("li", "record");
  const head = el("div", "head");
  head.append(el("h2", "", "Record for the assessor"), el("div", "why", "TurnCheck has not scored anything."));
  li.append(head);
  for (const row of rows) {
    const box = el("div", "row");
    box.append(el("div", "q", `${row.n}. ${row.question}`));
    box.append(row.answer ? el("div", "", `Answer: ${row.answer}`)
                          : el("div", "none", row.moved_on ? "No answer: the candidate moved on." : "No answer recorded."));
    const facts = [];
    if (row.entries.length) facts.push(`sheet entries given: ${row.entries.join(", ")}`);
    if (row.declined.length) facts.push(`questions declined: ${row.declined.length}`);
    if (row.asks) facts.push(`asked how to read a turn: ${row.asks}`);
    if (row.waits) facts.push(`waited: ${row.waits}`);
    if (row.corrections) facts.push(`corrections by the candidate: ${row.corrections}`);
    if (row.left_unfinished) facts.push(`said while thinking: ${row.left_unfinished}`);
    if (facts.length) box.append(el("div", "why", facts.join(" · ")));
    li.append(box);
  }
  return li;
}

// pending: a turn that has been sent but not read yet. It is shown at once, before the model replies.
function render(view, pending) {
  $("progress").textContent = view.progress;
  $("indicator").textContent = pending ? "reading your turn…" : view.indicator;
  $("indicator").hidden = !$("indicator").textContent;
  $("banner").textContent = view.banner;
  $("banner").hidden = !view.banner;

  $("intro").hidden = view.state !== "start";
  $("title").textContent = view.title;
  $("rules").replaceChildren(...view.intro.map((rule) => el("li", "", rule)));

  $("question").textContent = view.question;
  $("question").hidden = !view.question;

  const list = $("items");
  list.hidden = view.state === "start";
  list.replaceChildren(...view.items.map((item) => (item.who === "candidate" ? candidate(item) : interviewer(item))));
  if (pending) list.append(candidate({ text: pending }));
  if (view.record) list.append(record(view.record));

  $("buttons").replaceChildren(...view.buttons.map((button) => {
    const node = el("button", "", button.label);
    node.onclick = () => send("api/choose", { option: button.id });
    return node;
  }));

  $("say").hidden = view.state !== "listening";
  $("text").disabled = Boolean(pending);
  if (!$("say").hidden && !pending) $("text").focus();
  list.scrollTop = list.scrollHeight;
}

async function send(path, body, pending) {
  if (busy || params.get("trace")) return;
  busy = true;
  if (pending) render(current, pending);
  try {
    const reply = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    current = await reply.json();
  } catch (problem) {
    current = { ...current, banner: "TurnCheck is not responding. Is app.py still running?" };
  }
  busy = false;
  render(current);
}

$("start").onclick = () => send("api/start", {});
$("say").onsubmit = (event) => {
  event.preventDefault();
  const text = $("text").value.trim();
  if (!text) return;
  $("text").value = "";
  send("api/turn", { text }, text);
};

// ?trace=NAME&step=N shows one step of a saved interview (results/traces/NAME.json) without a model.
// Adding &pending=1 shows the moment after the turn was sent and before it was read.
// &w=300 narrows the page to a phone's width, for screenshots.
async function boot() {
  if (params.get("w")) $("app").style.maxWidth = `${Number(params.get("w"))}px`;
  if (!params.get("trace")) {
    current = await (await fetch("api/view")).json();
    return render(current);
  }
  const trace = await (await fetch(`traces/${params.get("trace")}.json`)).json();
  const n = Number(params.get("step") || 0);
  if (params.get("pending")) render(trace.steps[n - 1].view, trace.steps[n].action.turn);
  else render(trace.steps[n].view);
  // What is at the top of the frame: &top=turn (the last turn), &top=divider (the last "Question n of N"),
  // or &row=2 (the second question of the end-of-interview record). Without these, the newest item shows.
  const list = $("items");
  const pick = { turn: ".candidate", divider: ".divider" }[params.get("top")];
  const target = params.get("row") ? list.querySelectorAll(".record .row")[Number(params.get("row")) - 1]
                                    : pick && [...list.querySelectorAll(pick)].pop();
  if (!target) return;
  const heading = list.querySelector(".record .head");
  list.style.paddingBottom = `${list.clientHeight}px`;  // room to bring a late item to the top
  list.scrollTop = target.offsetTop - list.offsetTop - (params.get("row") && heading ? heading.offsetHeight + 4 : 8);
}
boot();
