import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getAll, trackEvent } from "../api.js";
import { useAuth } from "../auth.jsx";
import { ErrorBox, Field, Spinner } from "../components/ui.jsx";

export default function Outcome() {
  const { t } = useAuth();
  const { sessionId } = useParams();
  const result = useQuery({ queryKey: ["diagnosis-result", sessionId], queryFn: () => api(`/sessions/${sessionId}/result/`) });
  const saved = useQuery({ queryKey: ["diagnosis-outcome", sessionId], queryFn: () => api(`/sessions/${sessionId}/outcome/`), retry: false });
  if (result.isLoading || saved.isLoading) return <Spinner />;
  if (result.isError) return <ErrorBox>{result.error.message}</ErrorBox>;
  if (result.data.status !== "completed") return <ErrorBox>{t("outcome_complete_first")}</ErrorBox>;
  return <OutcomeForm key={`${sessionId}-${saved.data?.id || "new"}`} sessionId={sessionId}
    result={result.data} initial={saved.data?.id ? saved.data : null} />;
}

function OutcomeForm({ sessionId, result, initial }) {
  const { t } = useAuth();
  const navigate = useNavigate();
  const client = useQueryClient();
  const [cause, setCause] = useState(initial?.actual_cause ? String(initial.actual_cause) : initial?.actual_cause_text ? "other" : "");
  const [causeText, setCauseText] = useState(initial?.actual_cause_text || "");
  const [cost, setCost] = useState(initial?.actual_cost == null ? "" : String(initial.actual_cost));
  const [mechanic, setMechanic] = useState(initial?.mechanic ? String(initial.mechanic) : "");
  const [mechanicType, setMechanicType] = useState(initial?.mechanic_type || "");
  const [helpful, setHelpful] = useState(initial?.was_helpful == null ? "" : initial.was_helpful ? "yes" : "no");
  const [notes, setNotes] = useState(initial?.notes || "");
  const [error, setError] = useState("");
  const mechanics = useQuery({
    queryKey: ["mechanics-list"],
    queryFn: () => getAll("/accounts/mechanics/"),
  });
  const submit = useMutation({
    mutationFn: (body) => api(`/sessions/${sessionId}/outcome/`, { method: "POST", body }),
    onSuccess: async () => {
      trackEvent("outcome_submitted", sessionId);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["diagnosis-outcome", sessionId] }),
        client.invalidateQueries({ queryKey: ["history-sessions"] }),
      ]);
      navigate(`/result/${sessionId}`);
    },
    onError: (e) => setError(e.message),
  });
  const ranked = result.results || [];
  const send = (event) => {
    event.preventDefault();
    setError("");
    if (helpful === "") { setError(t("outcome_helpful_required")); return; }
    if (!cause && !causeText.trim()) { setError(t("outcome_cause_required")); return; }
    submit.mutate({
      actual_cause: cause && cause !== "other" ? Number(cause) : null,
      actual_cause_text: cause === "other" ? causeText.trim() : "",
      actual_cost: cost !== "" ? Number(cost) : null,
      mechanic: mechanic ? Number(mechanic) : null,
      mechanic_type: mechanicType.trim(),
      was_helpful: helpful === "yes",
      notes: notes.trim(),
    });
  };
  return <section className="page-review outcome-page">
    <h1>{t("outcome_title")}</h1>
    <p>{t("outcome_intro")}</p>
    {initial && <p className="chip">{t("outcome_update_existing")}</p>}
    {error && <ErrorBox>{error}</ErrorBox>}
    <form className="stack" onSubmit={send}>
      <Field label={t("outcome_cause_label")}>
        <select required value={cause} onChange={(event) => { setCause(event.target.value); setCauseText(""); }}>
          <option value="">{t("outcome_cause_placeholder")}</option>
          {ranked.map((item) => <option key={item.cause} value={item.cause}>{item.rank}. {item.cause_name}</option>)}
          <option value="other">{t("outcome_other")}</option>
        </select>
      </Field>
      {!ranked.length && <p className="muted">{t("outcome_no_ranked_causes")}</p>}
      {cause === "other" && <Field label={t("outcome_other_label")}><input maxLength={200} required value={causeText} onChange={(event) => setCauseText(event.target.value)} /></Field>}
      <Field label={t("outcome_cost_label")}><input type="number" min="0" step="1" inputMode="numeric" placeholder="PKR" value={cost} onChange={(event) => setCost(event.target.value)} /></Field>
      <Field label={t("outcome_mechanic_type_label")}><input maxLength={120} value={mechanicType} onChange={(event) => setMechanicType(event.target.value)} /></Field>
      <Field label={t("outcome_mechanic_assign")} hint={t("outcome_mechanic_access_help")}>
        <select value={mechanic} onChange={(event) => setMechanic(event.target.value)}>
          <option value="">{t("outcome_mechanic_unassigned")}</option>
          {(mechanics.data || []).map((item) => <option key={item.user} value={item.user}>{item.workshop_name}</option>)}
        </select>
      </Field>
      {mechanics.isError && <p className="muted">{t("outcome_mechanics_unavailable")}</p>}
      <fieldset className="stack-tight"><legend>{t("outcome_helpful_label")}</legend>
        <label className="choice-row"><input type="radio" name="helpful" value="yes" checked={helpful === "yes"} onChange={() => setHelpful("yes")} />{t("outcome_yes")}</label>
        <label className="choice-row"><input type="radio" name="helpful" value="no" checked={helpful === "no"} onChange={() => setHelpful("no")} />{t("outcome_no")}</label>
      </fieldset>
      <Field label={t("outcome_notes_label")}><textarea rows={4} maxLength={2000} value={notes} onChange={(event) => setNotes(event.target.value)} /></Field>
      <button className="btn" type="submit" disabled={submit.isPending}>{submit.isPending ? t("outcome_saving") : t("outcome_submit")}</button>
    </form>
  </section>;
}
