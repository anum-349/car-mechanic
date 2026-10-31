import { Fragment, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import { Empty, ErrorBox, Field, Spinner } from "../../components/ui.jsx";

/* ---------- shared styles ---------- */
const page = "mx-auto grid max-w-3xl gap-6";
const card = "rounded-lg border border-line bg-panel p-5";
const title = "m-0 font-body text-2xl font-semibold tracking-tight";
const heading = "m-0 font-body text-base font-semibold";
const back = "w-fit text-sm text-ink-soft";
const form = "mt-4 grid gap-4";
const cols = "grid gap-4 sm:grid-cols-2";
const actions = "flex flex-wrap justify-end gap-2";
const summaryCls = "cursor-pointer list-none font-semibold [&::-webkit-details-marker]:hidden";

const pkr = (value, t) => (value == null ? t("not_recorded") : `PKR ${Number(value).toLocaleString()}`);

function Facts({ rows }) {
  return <dl className="m-0 grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 text-sm">
    {rows.filter(([, value]) => value).map(([label, value]) => <Fragment key={label}>
      <dt className="text-ink-soft">{label}</dt>
      <dd className="m-0">{value}</dd>
    </Fragment>)}
  </dl>;
}

/* ---------- list ---------- */
function RecordList() {
  const { t } = useAuth();
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const [page_, setPage] = useState(1);
  const records = useQuery({
    queryKey: ["mechanic-records", term, page_],
    queryFn: () => api(`/mechanic/records/?q=${encodeURIComponent(term)}&page=${page_}`),
  });

  return <main className={page}>
    <header className="flex flex-wrap items-center justify-between gap-3">
      <h1 className={title}>{t("mechanic_records_title")}</h1>
      <Link className="btn" to="/mechanic/records/new">{t("mechanic_record_new")}</Link>
    </header>

    <form className="flex items-end gap-2" onSubmit={(event) => {
      event.preventDefault();
      setPage(1);
      setTerm(search.trim());
    }}>
      <div className="flex-1"><Field label={t("mechanic_records_search")}>
        <input value={search} onChange={(event) => setSearch(event.target.value)} />
      </Field></div>
      <button className="btn ghost">{t("mechanic_search")}</button>
    </form>

    {records.isLoading && <Spinner />}
    {records.isError && <>
      <ErrorBox>{records.error.message}</ErrorBox>
      <button className="btn ghost w-fit" onClick={() => records.refetch()}>{t("retry")}</button>
    </>}
    {records.data && (records.data.results.length ? <>
      <div className="divide-y divide-line border-y border-line">
        {records.data.results.map((record) => <Link
          key={record.id}
          to={`/mechanic/records/${record.id}`}
          className="flex items-center justify-between gap-4 px-2 py-3.5 text-inherit no-underline hover:bg-hover-surface">
          <div className="min-w-0">
            <div className="font-semibold">{record.car.label}</div>
            <div className="truncate text-sm text-ink-soft">
              {record.diagnosis_type === "obd" ? `${record.obd_context?.code || ""} · ${record.obd_context?.description || ""}` : record.free_text}
            </div>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <span className="chip m-0">{t(`mechanic_record_status_${record.status}`)}</span>
            <span className="text-xs text-ink-soft">{new Date(record.started_at).toLocaleDateString()}</span>
          </div>
        </Link>)}
      </div>
      <div className="flex items-center justify-between text-sm">
        <button className="btn ghost" disabled={!records.data.previous || page_ <= 1} onClick={() => setPage((value) => Math.max(1, value - 1))}>{t("history_previous")}</button>
        <span className="text-ink-soft">{t("mechanic_page", { page: page_ })}</span>
        <button className="btn ghost" disabled={!records.data.next} onClick={() => setPage((value) => value + 1)}>{t("history_next")}</button>
      </div>
    </> : <Empty action={<Link className="btn" to="/mechanic/records/new">{t("mechanic_record_new")}</Link>}>{t("mechanic_records_empty")}</Empty>)}
  </main>;
}

/* ---------- new ---------- */
function NewRecord() {
  const { t } = useAuth();
  const navigate = useNavigate();
  const [error, setError] = useState("");
  const vehicles = useQuery({
    queryKey: ["mechanic-record-vehicles"],
    queryFn: () => api("/mechanic/records/vehicles/"),
  });
  const create = useMutation({
    mutationFn: (body) => api("/sessions/", { method: "POST", body }),
    onSuccess: (session) => navigate(`/mechanic/records/${session.id}`),
    onError: (requestError) => setError(requestError.message),
  });

  function submit(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const problem = String(data.get("problem") || "").trim();
    if (!problem) {
      setError(t("mechanic_problem_required"));
      return;
    }
    setError("");
    create.mutate({ car: Number(data.get("car")), free_text: problem });
  }

  return <main className={page}>
    <Link className={back} to="/mechanic/records">{t("mechanic_records_back")}</Link>
    <h1 className={title}>{t("mechanic_record_new")}</h1>
    {vehicles.isLoading && <Spinner />}
    {vehicles.isError && <ErrorBox>{vehicles.error.message}</ErrorBox>}
    {vehicles.data && !vehicles.data.length && <Empty action={<Link className="btn" to="/garage">{t("garage_add")}</Link>}>{t("mechanic_record_no_vehicles")}</Empty>}
    {vehicles.data?.length > 0 && <form className={`${card} grid gap-4`} onSubmit={submit}>
      <Field label={t("mechanic_record_vehicle")}>
        <select name="car" required defaultValue="">
          <option value="" disabled>{t("mechanic_record_vehicle_pick")}</option>
          {vehicles.data.map((car) => <option value={car.id} key={car.id}>{car.label} · {car.model}, {car.year}</option>)}
        </select>
      </Field>
      <Field label={t("mechanic_record_problem")}>
        <textarea name="problem" rows={5} maxLength={2000} required />
      </Field>
      <ErrorBox>{error}</ErrorBox>
      <button className="btn" disabled={create.isPending}>{create.isPending ? t("mechanic_record_creating") : t("mechanic_record_create")}</button>
    </form>}
  </main>;
}

/* ---------- inspection ---------- */
function InspectionForm({ record, onSaved }) {
  const { t, user } = useAuth();
  const draft = record.inspections.find((item) => item.status === "draft" && item.mechanic === user?.id);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [selectedCause, setSelectedCause] = useState(
    draft?.suspected_cause ? String(draft.suspected_cause)
      : draft?.suspected_cause_text ? "other" : "");

  async function submit(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const suspected = String(data.get("suspected_cause") || "");
    const body = {
      inspection_date: data.get("inspection_date") || null,
      mileage_km: data.get("mileage_km") ? Number(data.get("mileage_km")) : null,
      findings: String(data.get("findings") || "").trim(),
      tests_performed: String(data.get("tests_performed") || "").trim(),
      tools_used: String(data.get("tools_used") || "").trim(),
      additional_obd_codes: String(data.get("additional_obd_codes") || "")
        .split(/[\s,]+/).map((code) => code.trim()).filter(Boolean),
      suspected_cause: suspected && suspected !== "other" ? Number(suspected) : null,
      suspected_cause_text: suspected === "other" ? String(data.get("suspected_cause_text") || "").trim() : "",
      safety_concerns: String(data.get("safety_concerns") || "").trim(),
      further_testing_required: data.get("further_testing_required") === "on",
    };
    const shouldSubmit = event.nativeEvent.submitter?.value === "submit";
    setSaving(true);
    setError("");
    try {
      const path = `/mechanic/records/${record.id}/inspections/`;
      const saved = await api(draft ? `${path}${draft.id}/` : path, { method: draft ? "PATCH" : "POST", body });
      if (shouldSubmit) await api(`${path}${saved.id}/submit/`, { method: "POST", body: {} });
      await onSaved();
    } catch (requestError) {
      setError(requestError.message);
      await onSaved();
    } finally {
      setSaving(false);
    }
  }

  return <details className={card} open={Boolean(draft)}>
    <summary className={summaryCls}>{draft ? t("mechanic_inspection_draft") : t("mechanic_inspection_add")}</summary>
    <form className={form} onSubmit={submit}>
      <div className={cols}>
        <Field label={t("mechanic_inspection_date")}><input type="date" name="inspection_date" defaultValue={draft?.inspection_date || ""} /></Field>
        <Field label={t("mechanic_inspection_mileage")}><input type="number" min="0" max="2000000" name="mileage_km" defaultValue={draft?.mileage_km ?? ""} /></Field>
      </div>
      <Field label={t("mechanic_inspection_findings")}><textarea rows={3} name="findings" maxLength={5000} defaultValue={draft?.findings || ""} required /></Field>
      <Field label={t("mechanic_inspection_tests")}><textarea rows={3} name="tests_performed" maxLength={5000} defaultValue={draft?.tests_performed || ""} required /></Field>
      <div className={cols}>
        <Field label={t("mechanic_inspection_tools")}><input name="tools_used" maxLength={1000} defaultValue={draft?.tools_used || ""} /></Field>
        <Field label={t("mechanic_inspection_codes")}><input name="additional_obd_codes" placeholder="P0301, C1234" defaultValue={(draft?.additional_obd_codes || []).join(", ")} /></Field>
      </div>
      <Field label={t("mechanic_inspection_cause")}>
        <select name="suspected_cause" value={selectedCause} onChange={(event) => setSelectedCause(event.target.value)}>
          <option value="">{t("mechanic_cause_unspecified")}</option>
          {record.results.map((result) => <option key={result.cause} value={result.cause}>{result.cause_name}</option>)}
          <option value="other">{t("mechanic_cause_other")}</option>
        </select>
      </Field>
      {selectedCause === "other" && <Field label={t("mechanic_inspection_cause_text")}><input name="suspected_cause_text" maxLength={200} defaultValue={draft?.suspected_cause_text || ""} /></Field>}
      <Field label={t("mechanic_inspection_safety")}><textarea rows={2} name="safety_concerns" maxLength={2000} defaultValue={draft?.safety_concerns || ""} /></Field>
      <label className="flex items-center gap-2 text-sm">
        <input className="size-5 min-h-0 w-5 p-0" type="checkbox" name="further_testing_required" defaultChecked={draft?.further_testing_required || false} />
        {t("mechanic_inspection_follow_up")}
      </label>
      <ErrorBox>{error}</ErrorBox>
      <div className={actions}>
        <button className="btn ghost" value="draft" disabled={saving}>{t("mechanic_save_draft")}</button>
        <button className="btn" value="submit" disabled={saving}>{t("mechanic_submit_inspection")}</button>
      </div>
    </form>
  </details>;
}

/* ---------- outcome ---------- */
function OutcomeForm({ record, onSaved }) {
  const { t, user } = useAuth();
  const outcome = record.outcome;
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const currentCause = outcome?.actual_cause ? String(outcome.actual_cause) : outcome?.actual_cause_text ? "other" : "";
  const [selectedCause, setSelectedCause] = useState(currentCause);

  if (outcome && outcome.mechanic !== user?.id) {
    return <section className={card}>
      <h2 className={`${heading} mb-3`}>{t("mechanic_outcome_title")}</h2>
      <p className="mb-3 text-sm text-ink-soft">{t("mechanic_outcome_recorded_by", { name: outcome.mechanic_name })}</p>
      <Facts rows={[
        [t("mechanic_outcome_cause"), outcome.actual_cause_text || outcome.actual_cause_name || t("not_recorded")],
        [t("mechanic_repair_status"), t(`mechanic_repair_${outcome.repair_status}`) || outcome.repair_status || t("not_recorded")],
        [t("mechanic_result_status"), t(`mechanic_result_${outcome.result_status}`) || outcome.result_status || t("not_recorded")],
        [t("mechanic_repair_actions"), outcome.repair_actions || t("not_recorded")],
        [t("mechanic_cost_total"), pkr(outcome.actual_cost, t)],
      ]} />
    </section>;
  }

  async function submit(event) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const cause = String(data.get("actual_cause") || "");
    const number = (name) => (data.get(name) ? Number(data.get(name)) : null);
    const text = (name) => String(data.get(name) || "").trim();
    const body = {
      actual_cause: cause && cause !== "other" ? Number(cause) : null,
      actual_cause_text: cause === "other" ? text("actual_cause_text") : "",
      repair_status: String(data.get("repair_status") || ""),
      result_status: String(data.get("result_status") || ""),
      repair_actions: text("repair_actions"),
      parts_replaced: text("parts_replaced"),
      follow_up_notes: text("follow_up_notes"),
      actual_cost: number("actual_cost"),
      parts_cost: number("parts_cost"),
      labor_cost: number("labor_cost"),
      other_cost: number("other_cost"),
      notes: text("notes"),
      repaired_at: data.get("repaired_at") || null,
    };
    const shouldSubmit = event.nativeEvent.submitter?.value === "submit";
    setSaving(true);
    setError("");
    try {
      const path = `/mechanic/records/${record.id}/outcome/`;
      await api(path, { method: outcome ? "PATCH" : "POST", body });
      if (shouldSubmit) await api(`${path}submit/`, { method: "POST", body: {} });
      await onSaved();
    } catch (requestError) {
      setError(requestError.message);
      await onSaved();
    } finally {
      setSaving(false);
    }
  }

  return <details className={card} open={Boolean(outcome)}>
    <summary className={summaryCls}>
      {t("mechanic_outcome_title")}
      {outcome?.submitted_at && <span className="chip">{t("mechanic_outcome_submitted")}</span>}
    </summary>
    <form className={form} onSubmit={submit}>
      <Field label={t("mechanic_outcome_cause")}>
        <select name="actual_cause" value={selectedCause} onChange={(event) => setSelectedCause(event.target.value)}>
          <option value="">{t("mechanic_cause_choose")}</option>
          {record.results.map((result) => <option key={result.cause} value={result.cause}>{result.cause_name}</option>)}
          <option value="other">{t("mechanic_cause_other")}</option>
        </select>
      </Field>
      {selectedCause === "other" && <Field label={t("mechanic_outcome_cause_text")}><input name="actual_cause_text" maxLength={200} defaultValue={outcome?.actual_cause_text || ""} /></Field>}
      <div className={cols}>
        <Field label={t("mechanic_repair_status")}>
          <select name="repair_status" defaultValue={outcome?.repair_status || ""}>
            <option value="">{t("select")}</option>
            <option value="not_started">{t("mechanic_repair_not_started")}</option>
            <option value="in_progress">{t("mechanic_repair_in_progress")}</option>
            <option value="completed">{t("mechanic_repair_completed")}</option>
          </select>
        </Field>
        <Field label={t("mechanic_result_status")}>
          <select name="result_status" defaultValue={outcome?.result_status || ""}>
            <option value="">{t("select")}</option>
            <option value="resolved">{t("mechanic_result_resolved")}</option>
            <option value="partially_resolved">{t("mechanic_result_partial")}</option>
            <option value="not_resolved">{t("mechanic_result_unresolved")}</option>
            <option value="unable_to_verify">{t("mechanic_result_unverified")}</option>
            <option value="further_diagnosis">{t("mechanic_result_further")}</option>
          </select>
        </Field>
      </div>
      <Field label={t("mechanic_repair_actions")}><textarea name="repair_actions" rows={3} maxLength={5000} defaultValue={outcome?.repair_actions || ""} /></Field>
      <Field label={t("mechanic_parts_replaced")}><textarea name="parts_replaced" rows={2} maxLength={3000} defaultValue={outcome?.parts_replaced || ""} /></Field>
      <div className={cols}>
        <Field label={t("mechanic_cost_total")}><input type="number" min="0" max="100000000" name="actual_cost" defaultValue={outcome?.actual_cost ?? ""} /></Field>
        <Field label={t("mechanic_parts_cost")}><input type="number" min="0" max="100000000" name="parts_cost" defaultValue={outcome?.parts_cost ?? ""} /></Field>
        <Field label={t("mechanic_labor_cost")}><input type="number" min="0" max="100000000" name="labor_cost" defaultValue={outcome?.labor_cost ?? ""} /></Field>
        <Field label={t("mechanic_other_cost")}><input type="number" min="0" max="100000000" name="other_cost" defaultValue={outcome?.other_cost ?? ""} /></Field>
        <Field label={t("mechanic_repaired_at")}><input type="date" name="repaired_at" defaultValue={outcome?.repaired_at || ""} /></Field>
      </div>
      <Field label={t("mechanic_follow_up")}><textarea name="follow_up_notes" rows={2} maxLength={3000} defaultValue={outcome?.follow_up_notes || ""} /></Field>
      <Field label={t("mechanic_outcome_notes")}><textarea name="notes" rows={3} maxLength={5000} defaultValue={outcome?.notes || ""} /></Field>
      <ErrorBox>{error}</ErrorBox>
      <div className={actions}>
        <button className="btn ghost" value="draft" disabled={saving}>{t("mechanic_save_draft")}</button>
        <button className="btn" value="submit" disabled={saving}>{t("mechanic_submit_outcome")}</button>
      </div>
    </form>
  </details>;
}

/* ---------- detail ---------- */
function RecordDetail({ id }) {
  const { t, user } = useAuth();
  const queryClient = useQueryClient();
  const record = useQuery({
    queryKey: ["mechanic-record", id],
    queryFn: () => api(`/mechanic/records/${id}/`),
  });

  async function refresh() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["mechanic-record", id] }),
      queryClient.invalidateQueries({ queryKey: ["mechanic-records"] }),
    ]);
  }

  if (record.isLoading) return <Spinner />;
  if (record.isError) return <main className={page}><ErrorBox>{record.error.message}</ErrorBox><Link className={back} to="/mechanic/records">{t("mechanic_records_back")}</Link></main>;

  const item = record.data;
  const causeName = (cause) => item.results.find((result) => String(result.cause) === String(cause))?.cause_name;
  const draftId = item.inspections.find((inspection) => inspection.status === "draft" && inspection.mechanic === user?.id)?.id || "new";

  return <main className={page}>
    <Link className={back} to="/mechanic/records">{t("mechanic_records_back")}</Link>

    <header className="grid gap-2">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className={title}>{item.car.label}</h1>
        <span className="chip m-0">{t(`mechanic_record_status_${item.status}`)}</span>
      </div>
      <p className="m-0 text-sm text-ink-soft">
        {item.car.model} ({item.car.year}) · {new Date(item.started_at).toLocaleDateString()}
      </p>
      <p className="m-0 max-w-none">
        {item.diagnosis_type === "obd"
          ? <><strong>{item.obd_context?.code}</strong> — {item.obd_context?.description}</>
          : item.free_text}
      </p>
      {item.safety_alert && <p className="error m-0" role="alert">{t("mechanic_safety_warning")}</p>}
      {item.status === "in_progress" && <Link className="btn ghost mt-2 w-fit" to={`/diagnose/${item.id}`}>{t("mechanic_continue_diagnosis")}</Link>}
    </header>

    {(item.category_label || item.symptoms.length > 0) && <details className={card}>
      <summary className={summaryCls}>{t("mechanic_reported_context")}</summary>
      <div className="mt-3 grid gap-2 text-sm">
        {item.category_label && <p className="m-0">{item.category_label}</p>}
        {item.symptoms.length > 0 && <ul className="m-0 list-disc pl-5">{item.symptoms.map((symptom) => <li key={symptom.id}>{symptom.text}</li>)}</ul>}
      </div>
    </details>}

    <details className={card} open>
      <summary className={summaryCls}>{t("mechanic_ai_diagnosis")}</summary>
      <div className="mt-3 grid gap-4">
        {item.results.length
          ? <ol className="m-0 grid list-none gap-3 p-0">{item.results.map((result) => <li key={`${result.cause}-${result.rank}`}>
            <div className="font-semibold">{result.rank}. {result.cause_name}</div>
            <p className="m-0 text-sm text-ink-soft">{result.explanation || t("mechanic_no_explanation")}</p>
          </li>)}</ol>
          : <p className="m-0 text-sm text-ink-soft">{t("mechanic_no_ai_result")}</p>}
        {item.answers.length > 0 && <details>
          <summary className="cursor-pointer text-sm text-ink-soft">{t("mechanic_answers_title")}</summary>
          <ul className="mt-2 grid list-none gap-1 p-0 text-sm">{item.answers.map((answer) => <li key={answer.id}>
            <strong>{answer.question_text}</strong>: {answer.answer_text}{answer.free_text ? ` — ${answer.free_text}` : ""}
          </li>)}</ul>
        </details>}
      </div>
    </details>

    {item.inspections.length > 0 && <section className={card}>
      <h2 className={`${heading} mb-3`}>{t("mechanic_inspections_title")}</h2>
      <div className="divide-y divide-line">
        {item.inspections.map((inspection) => <article className="grid gap-2 py-3 first:pt-0 last:pb-0" key={inspection.id}>
          <div className="flex flex-wrap items-center gap-2 text-sm text-ink-soft">
            <span className="chip m-0">{inspection.status === "submitted" ? t("mechanic_inspection_submitted") : t("mechanic_inspection_draft")}</span>
            <span>{inspection.mechanic_name} · {inspection.inspection_date || new Date(inspection.created_at).toLocaleDateString()}</span>
          </div>
          <Facts rows={[
            [t("mechanic_inspection_findings"), inspection.findings || t("not_recorded")],
            [t("mechanic_inspection_tests"), inspection.tests_performed || t("not_recorded")],
            [t("mechanic_inspection_tools"), inspection.tools_used],
            [t("mechanic_inspection_codes"), inspection.additional_obd_codes?.length > 0 && inspection.additional_obd_codes.join(", ")],
            [t("mechanic_inspection_cause"), (inspection.suspected_cause_text || inspection.suspected_cause) && (inspection.suspected_cause_text || inspection.suspected_cause_name || causeName(inspection.suspected_cause) || t("not_recorded"))],
            [t("mechanic_inspection_safety"), inspection.safety_concerns],
            [t("mechanic_inspection_follow_up"), inspection.further_testing_required && "✓"],
          ]} />
        </article>)}
      </div>
    </section>}

    <InspectionForm key={`inspection-${item.id}-${draftId}`} record={item} onSaved={refresh} />
    <OutcomeForm key={`outcome-${item.id}-${item.outcome?.id || "new"}-${item.outcome?.submitted_at || "draft"}`} record={item} onSaved={refresh} />

    {item.outcome_history.length > 0 && <details className={card}>
      <summary className={summaryCls}>{t("mechanic_outcome_history")}</summary>
      <div className="mt-3 divide-y divide-line">
        {item.outcome_history.map((entry) => <details className="py-3 first:pt-0 last:pb-0" key={entry.id}>
          <summary className="cursor-pointer text-sm">
            <span className="capitalize">{entry.action.replaceAll("_", " ")}</span>
            <span className="text-ink-soft"> · {entry.mechanic_name || t("mechanic_user_removed")} · {new Date(entry.created_at).toLocaleString()}</span>
          </summary>
          <div className="mt-3">
            <Facts rows={[
              [t("mechanic_audit_cause"), entry.snapshot.actual_cause_text || entry.snapshot.actual_cause_name || causeName(entry.snapshot.actual_cause) || t("not_recorded")],
              [t("mechanic_repair_status"), entry.snapshot.repair_status || t("not_recorded")],
              [t("mechanic_result_status"), entry.snapshot.result_status || t("not_recorded")],
              [t("mechanic_repair_actions"), entry.snapshot.repair_actions || t("not_recorded")],
              [t("mechanic_parts_replaced"), entry.snapshot.parts_replaced || t("not_recorded")],
              [t("mechanic_cost_total"), pkr(entry.snapshot.actual_cost, t)],
              [t("mechanic_outcome_notes"), entry.snapshot.notes || t("not_recorded")],
            ]} />
          </div>
        </details>)}
      </div>
    </details>}
  </main>;
}

export default function MechanicRecords() {
  const { id } = useParams();
  if (id === "new") return <NewRecord />;
  return id ? <RecordDetail id={id} /> : <RecordList />;
}