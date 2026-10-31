import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getAll } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import { Empty, ErrorBox, Field, Spinner } from "../../components/ui.jsx";

export default function MechanicAiDrafts() {
  const { t } = useAuth();
  const [carModel, setCarModel] = useState("");
  const [reasonId, setReasonId] = useState(null);
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const queryClient = useQueryClient();
  const options = useQuery({ queryKey: ["ai-draft-car-models"], queryFn: async () => {
    const [models, makes] = await Promise.all([getAll("/garage/models/"), getAll("/garage/makes/")]);
    return { models, makes };
  } });
  const drafts = useQuery({ queryKey: ["mechanic-ai-drafts", carModel], queryFn: () => api(`/mechanic/ai-drafts/${carModel ? `?car_model_id=${carModel}` : ""}`) });

  async function doAction(draft, action, body = {}) {
    setErrorMessage(""); setMessage("");
    try {
      if (action === "claim") await api(`/mechanic/items/${draft.type}/${draft.id}/claim/`, { method: "POST", body: {} });
      else await api(`/mechanic/ai-drafts/${draft.type}/${draft.id}/${action}/`, { method: "POST", body });
      setMessage(action === "claim" ? t("mechanic_ai_claimed") : action === "approve-as-is" ? t("mechanic_ai_submitted") : t("mechanic_ai_rejected"));
      setReasonId(null); setReason("");
      queryClient.invalidateQueries({ queryKey: ["mechanic-ai-drafts"] });
      queryClient.invalidateQueries({ queryKey: ["mechanic-dashboard"] });
    } catch (error) { setErrorMessage(error.message); }
  }

  if (options.isLoading) return <Spinner />;
  if (options.isError) return <section><ErrorBox>{options.error.message}</ErrorBox><button className="btn" onClick={() => options.refetch()}>{t("retry")}</button></section>;
  return <main className="mechanic-area">
    <Link to="/mechanic">← {t("mechanic_dashboard_title")}</Link>
    <h1>{t("mechanic_ai_drafts_title")}</h1>
    <p>{t("mechanic_ai_drafts_intro")}</p>
    <Field label={t("mechanic_simulator_car")}><select value={carModel} onChange={(event) => setCarModel(event.target.value)}><option value="">{t("mechanic_ai_all_models")}</option>{options.data.models.map((model) => <option key={model.id} value={model.id}>{options.data.makes.find((make) => make.id === model.car_make)?.name} {model.name} {model.generation}</option>)}</select></Field>
    {message && <p role="status" className="ok-text">{message}</p>}{errorMessage && <ErrorBox>{errorMessage}</ErrorBox>}
    {drafts.isLoading && <Spinner />}
    {drafts.isError && <><ErrorBox>{drafts.error.message}</ErrorBox><button className="btn" onClick={() => drafts.refetch()}>{t("retry")}</button></>}
    {drafts.data?.length === 0 && <Empty>{t("mechanic_ai_empty")}</Empty>}
    {(drafts.data || []).map((draft) => <AiDraftCard key={`${draft.type}-${draft.id}`} draft={draft} t={t}
      reasonOpen={reasonId === `${draft.type}-${draft.id}`} reason={reason} setReason={setReason}
      onApprove={() => doAction(draft, "approve-as-is")}
      onClaim={() => doAction(draft, "claim")}
      onRejectOpen={() => { setReasonId(`${draft.type}-${draft.id}`); setReason(""); }}
      onReject={() => doAction(draft, "reject", { reason })} />)}
  </main>;
}

function AiDraftCard({ draft, t, reasonOpen, reason, setReason, onApprove, onClaim, onRejectOpen, onReject }) {
  const [busy, setBusy] = useState(false);
  async function run(action) { setBusy(true); try { await action(); } finally { setBusy(false); } }
  const data = draft.data || {};
  const summary = data.text_en || data.name || data.steps || data.text || draft.label;
  return <article className="panel mechanic-ai-card">
    <p className="small muted">{t(`mechanic_ai_type_${draft.type}`)} · {t("mechanic_status_ai_draft")}</p>
    <h2>{summary}</h2>
    {data.system && <p>{data.system}</p>}{data.description && <p>{data.description}</p>}
    <div className="row">
      <button className="btn" type="button" disabled={busy} onClick={() => run(onApprove)}>{t("mechanic_ai_approve")}</button>
      <button className="btn ghost" type="button" disabled={busy} onClick={() => run(onClaim)}>{t("mechanic_ai_edit_claim")}</button>
      <button className="btn ghost" type="button" disabled={busy} onClick={onRejectOpen}>{t("mechanic_ai_reject")}</button>
    </div>
    {reasonOpen && <div className="mechanic-ai-reject-form"><Field label={t("mechanic_ai_reject_reason")}><textarea rows={3} value={reason} onChange={(e) => setReason(e.target.value)} /></Field><button className="btn danger-option" type="button" disabled={busy || !reason.trim()} onClick={() => run(onReject)}>{t("mechanic_ai_confirm_reject")}</button></div>}
  </article>;
}
