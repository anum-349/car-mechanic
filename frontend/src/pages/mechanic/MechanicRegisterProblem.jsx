import { useMemo, useState } from "react";
import { Field } from "../../components/ui.jsx";

/*
  Data model (what onSave receives):
  {
    id, title,
    questions: [{ id, text, answers: [{ id, text, next: "q:<id>" | "o:<id>", note }] }],   // first question = start
    outcomes:  [{ id, cause, solution, checks: ["what to ask / check", ...],
                  cost: { parts: {min,max}, labor: {min,max}, other: {min,max} } }]
  }
*/

const uid = () => Math.random().toString(36).slice(2, 8);
const answer = () => ({ id: uid(), text: "", next: "", note: "" });
const question = () => ({ id: uid(), text: "", answers: [answer(), answer()] });
const line = () => ({ min: "", max: "" });
const outcome = () => ({ id: uid(), cause: "", solution: "", checks: "", cost: { parts: line(), labor: line(), other: line() } });
const blank = () => ({ id: null, title: "", questions: [question()], outcomes: [outcome()] });

const COSTS = [["parts", "Parts"], ["labor", "Labour"], ["other", "Other"]];
const num = (v) => Number(v) || 0;
const pkr = (v) => `PKR ${Number(v).toLocaleString()}`;
const lines = (text) => String(text || "").split("\n").map((s) => s.trim()).filter(Boolean);
const totals = (cost) => COSTS.reduce((sum, [key]) => ({ min: sum.min + num(cost[key].min), max: sum.max + num(cost[key].max) }), { min: 0, max: 0 });

const card = "rounded-lg border border-line bg-panel p-5";
const h2 = "m-0 font-body text-base font-semibold";
const cols = "grid gap-4 sm:grid-cols-2";

function validate(p) {
  const issues = [];
  const targets = new Set([...p.questions.map((q) => `q:${q.id}`), ...p.outcomes.map((o) => `o:${o.id}`)]);
  if (!p.title.trim()) issues.push("Give the problem a title.");
  p.questions.forEach((q, i) => {
    if (!q.text.trim()) issues.push(`Question ${i + 1} needs text.`);
    if (q.answers.length < 2) issues.push(`Question ${i + 1} needs at least two answers.`);
    q.answers.forEach((a, j) => {
      if (!a.text.trim()) issues.push(`Question ${i + 1}, answer ${j + 1} needs text.`);
      if (!targets.has(a.next)) issues.push(`Question ${i + 1}, answer ${j + 1} needs a next step.`);
    });
  });
  p.outcomes.forEach((o, i) => {
    if (!o.cause.trim() || !o.solution.trim()) issues.push(`Result ${i + 1} needs a cause and a solution.`);
    COSTS.forEach(([key, label]) => {
      if (num(o.cost[key].min) > num(o.cost[key].max)) issues.push(`Result ${i + 1}: ${label} minimum is above maximum.`);
    });
  });
  return issues;
}

function Preview({ problem }) {
  const [node, setNode] = useState(`q:${problem.questions[0]?.id}`);
  const [kind, id] = node.split(":");
  const q = kind === "q" && problem.questions.find((item) => item.id === id);
  const o = kind === "o" && problem.outcomes.find((item) => item.id === id);
  const total = o ? totals(o.cost) : null;
  return <section className={`${card} grid gap-3`}>
    <div className="flex items-center justify-between">
      <h2 className={h2}>Preview</h2>
      <button type="button" className="link-btn text-sm" onClick={() => setNode(`q:${problem.questions[0]?.id}`)}>Restart</button>
    </div>
    {q && <>
      <p className="m-0 font-semibold">{q.text || "Untitled question"}</p>
      <div className="grid gap-2">
        {q.answers.map((a) => <button key={a.id} type="button" className="option" disabled={!a.next} onClick={() => setNode(a.next)}>{a.text || "Untitled answer"}</button>)}
      </div>
    </>}
    {o && <div className="grid gap-3 text-sm">
      <div><div className="text-ink-soft">Likely cause</div><div className="font-semibold">{o.cause || "—"}</div></div>
      <div><div className="text-ink-soft">Solution</div><div>{o.solution || "—"}</div></div>
      {lines(o.checks).length > 0 && <div><div className="text-ink-soft">Ask / check</div><ul className="m-0 list-disc pl-5">{lines(o.checks).map((c) => <li key={c}>{c}</li>)}</ul></div>}
      <div><div className="text-ink-soft">Estimated cost</div><div className="font-semibold">{pkr(total.min)} – {pkr(total.max)}</div></div>
    </div>}
    {!q && !o && <p className="m-0 text-sm text-ink-soft">This step no longer exists. Restart the preview.</p>}
  </section>;
}

export default function MechanicRegisterProblem({ problems = [], onSave }) {
  const [mode, setMode] = useState("new");
  const [problem, setProblem] = useState(blank);
  const [issues, setIssues] = useState([]);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const targets = useMemo(() => [
    ["Questions", problem.questions.map((q, i) => [`q:${q.id}`, `Question ${i + 1}: ${q.text.slice(0, 40) || "untitled"}`])],
    ["Results", problem.outcomes.map((o, i) => [`o:${o.id}`, `Result ${i + 1}: ${o.cause.slice(0, 40) || "untitled"}`])],
  ], [problem]);

  const patch = (changes) => { setSaved(false); setProblem((p) => ({ ...p, ...changes })); };
  const patchQuestion = (id, changes) => patch({ questions: problem.questions.map((q) => (q.id === id ? { ...q, ...changes } : q)) });
  const patchAnswer = (qid, aid, changes) => {
    const q = problem.questions.find((item) => item.id === qid);
    patchQuestion(qid, { answers: q.answers.map((a) => (a.id === aid ? { ...a, ...changes } : a)) });
  };
  const patchOutcome = (id, changes) => patch({ outcomes: problem.outcomes.map((o) => (o.id === id ? { ...o, ...changes } : o)) });
  const patchCost = (id, key, side, value) => {
    const o = problem.outcomes.find((item) => item.id === id);
    patchOutcome(id, { cost: { ...o.cost, [key]: { ...o.cost[key], [side]: value } } });
  };

  function chooseMode(next) {
    setMode(next);
    setIssues([]);
    if (next === "new") setProblem(blank());
  }

  function loadExisting(id) {
    const found = problems.find((p) => String(p.id) === id);
    if (found) setProblem(structuredClone({ ...found, outcomes: found.outcomes.map((o) => ({ ...o, checks: Array.isArray(o.checks) ? o.checks.join("\n") : o.checks || "" })) }));
  }

  async function save() {
    const found = validate(problem);
    setIssues(found);
    if (found.length) return;
    setSaving(true);
    setError("");
    try {
      await onSave({
        ...problem,
        title: problem.title.trim(),
        outcomes: problem.outcomes.map((o) => ({ ...o, checks: lines(o.checks) })),
      });
      setSaved(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return <main className="mx-auto grid max-w-3xl gap-6">
    <header className="grid gap-3">
      <h1 className="m-0 font-body text-2xl font-semibold tracking-tight">Problem triage</h1>
      <div className="seg wide mb-0" role="group" aria-label="Mode">
        <button type="button" className={mode === "new" ? "on" : ""} onClick={() => chooseMode("new")}>Register new problem</button>
        <button type="button" className={mode === "update" ? "on" : ""} onClick={() => chooseMode("update")} disabled={!problems.length}>Update existing</button>
      </div>
      {mode === "update" && <Field label="Problem">
        <select value={problem.id ?? ""} onChange={(e) => loadExisting(e.target.value)}>
          <option value="" disabled>Select a problem</option>
          {problems.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}
        </select>
      </Field>}
    </header>

    {(mode === "new" || problem.id) && <>
      <section className={card}>
        <Field label="Problem title"><input value={problem.title} maxLength={120} onChange={(e) => patch({ title: e.target.value })} placeholder="e.g. Engine cranks but won't start" /></Field>
      </section>

      <section className="grid gap-3">
        <h2 className={h2}>Questions</h2>
        {problem.questions.map((q, i) => <div key={q.id} className={`${card} grid gap-3`}>
          <div className="flex items-center justify-between gap-3">
            <span className="text-sm font-semibold">Question {i + 1}{i === 0 && <span className="chip">Start</span>}</span>
            {problem.questions.length > 1 && <button type="button" className="link-btn danger text-sm" onClick={() => patch({ questions: problem.questions.filter((item) => item.id !== q.id) })}>Remove</button>}
          </div>
          <input value={q.text} maxLength={250} onChange={(e) => patchQuestion(q.id, { text: e.target.value })} placeholder="What should the user be asked?" aria-label={`Question ${i + 1}`} />
          <div className="grid gap-3">
            {q.answers.map((a, j) => <div key={a.id} className="grid gap-2 border-l-2 border-line pl-3">
              <div className="grid gap-2 sm:grid-cols-[1fr_1fr_auto]">
                <input value={a.text} maxLength={120} onChange={(e) => patchAnswer(q.id, a.id, { text: e.target.value })} placeholder={`Answer ${j + 1}`} aria-label={`Question ${i + 1} answer ${j + 1}`} />
                <select value={a.next} onChange={(e) => patchAnswer(q.id, a.id, { next: e.target.value })} aria-label="Next step">
                  <option value="">Then go to…</option>
                  {targets.map(([group, items]) => <optgroup key={group} label={group}>
                    {items.filter(([value]) => value !== `q:${q.id}`).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                  </optgroup>)}
                </select>
                {q.answers.length > 2 && <button type="button" className="link-btn danger text-sm" onClick={() => patchQuestion(q.id, { answers: q.answers.filter((item) => item.id !== a.id) })}>Remove</button>}
              </div>
              <input value={a.note} maxLength={250} onChange={(e) => patchAnswer(q.id, a.id, { note: e.target.value })} placeholder="Optional: what the mechanic should ask when the user picks this answer" aria-label="Mechanic note" className="min-h-10 text-sm" />
            </div>)}
          </div>
          <button type="button" className="link-btn w-fit text-sm" onClick={() => patchQuestion(q.id, { answers: [...q.answers, answer()] })}>Add answer</button>
        </div>)}
        <button type="button" className="btn ghost w-fit" onClick={() => patch({ questions: [...problem.questions, question()] })}>Add question</button>
      </section>

      <section className="grid gap-3">
        <h2 className={h2}>Results</h2>
        {problem.outcomes.map((o, i) => {
          const total = totals(o.cost);
          return <div key={o.id} className={`${card} grid gap-4`}>
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm font-semibold">Result {i + 1}</span>
              {problem.outcomes.length > 1 && <button type="button" className="link-btn danger text-sm" onClick={() => patch({ outcomes: problem.outcomes.filter((item) => item.id !== o.id) })}>Remove</button>}
            </div>
            <Field label="Likely cause"><input value={o.cause} maxLength={200} onChange={(e) => patchOutcome(o.id, { cause: e.target.value })} /></Field>
            <Field label="Solution"><textarea rows={3} value={o.solution} maxLength={2000} onChange={(e) => patchOutcome(o.id, { solution: e.target.value })} /></Field>
            <Field label="What to ask or check" hint="One per line"><textarea rows={3} value={o.checks} maxLength={2000} onChange={(e) => patchOutcome(o.id, { checks: e.target.value })} /></Field>
            <div className="grid gap-2">
              <span className="field-label">Cost estimate (PKR)</span>
              {COSTS.map(([key, label]) => <div key={key} className="grid grid-cols-[5rem_1fr_1fr] items-center gap-2">
                <span className="text-sm text-ink-soft">{label}</span>
                <input type="number" min="0" max="100000000" value={o.cost[key].min} onChange={(e) => patchCost(o.id, key, "min", e.target.value)} placeholder="Min" aria-label={`${label} minimum`} />
                <input type="number" min="0" max="100000000" value={o.cost[key].max} onChange={(e) => patchCost(o.id, key, "max", e.target.value)} placeholder="Max" aria-label={`${label} maximum`} />
              </div>)}
              <p className="m-0 text-sm text-ink-soft">Total: <strong className="text-ink">{pkr(total.min)} – {pkr(total.max)}</strong></p>
            </div>
          </div>;
        })}
        <button type="button" className="btn ghost w-fit" onClick={() => patch({ outcomes: [...problem.outcomes, outcome()] })}>Add result</button>
      </section>

      <Preview key={problem.questions[0]?.id} problem={problem} />

      {issues.length > 0 && <div className="error" role="alert">
        <ul className="m-0 pl-5">{issues.map((issue) => <li key={issue}>{issue}</li>)}</ul>
      </div>}
      {error && <div className="error" role="alert">{error}</div>}
      {saved && <p className="ok-text m-0" role="status">Saved.</p>}
      <div className="flex justify-end">
        <button type="button" className="btn" disabled={saving} onClick={save}>{saving ? "Saving…" : mode === "new" ? "Register problem" : "Save changes"}</button>
      </div>
    </>}
  </main>;
}