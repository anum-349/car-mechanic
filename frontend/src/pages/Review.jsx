import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Empty, ErrorBox, Field, Spinner } from "../components/ui.jsx";

export function ReviewQueue() {
  const { t } = useAuth();
  const queue = useQuery({ queryKey: ["review-queue"], queryFn: () => api("/review/queue/") });
  if (queue.isLoading) return <Spinner />;
  if (queue.isError) return <section><ErrorBox>{queue.error.message}</ErrorBox><button className="btn" onClick={() => queue.refetch()}>{t("retry")}</button></section>;
  return <section className="page-review">
    <h1>{t("review_title")}</h1><p>{t("review_intro")}</p>
    <Link className="btn" to="/review/launch-gate">{t("launch_gate_title")}</Link>
    {!queue.data.length && <Empty>{t("review_empty")}</Empty>}
    {queue.data.map((item) => <Link className="panel review-queue-item" key={`${item.type}-${item.id}-${item.revision_id || "live"}`}
      to={`/review/items/${item.type}/${item.id}${item.revision_id ? `?revision_id=${item.revision_id}` : ""}`}>
      {item.safety_critical && <span className="review-safety">⚠ {t("review_safety")}</span>}
      <strong>{item.label || t(`review_type_${item.type}`)}</strong>
      <span>{t(`review_type_${item.type}`)} · {t(`review_status_${item.status}`)}</span>
      <span>{t("review_author", { name: item.author || t("review_unknown") })}</span>
    </Link>)}
  </section>;
}

export function LaunchGate() {
  const { t } = useAuth();
  const gate = useQuery({ queryKey: ["review-launch-gate"], queryFn: () => api("/review/launch-gate/") });
  if (gate.isLoading) return <Spinner />;
  if (gate.isError) return <section><ErrorBox>{gate.error.message}</ErrorBox><button className="btn" onClick={() => gate.refetch()}>{t("retry")}</button></section>;
  return <section className="page-review">
    <h1>{t("launch_gate_title")}</h1><p>{t("launch_gate_intro")}</p>
    {Object.entries(gate.data).map(([name, result]) => <article className="panel" key={name}>
      <h2>{t(`launch_gate_${name}`)}</h2><strong>{result.passed ? t("launch_gate_pass") : t("launch_gate_fail")}</strong>
      {!!result.offenders.length && <ul>{result.offenders.map((item, i) => <li key={`${item.type || item.setting || "item"}-${item.id || i}`}>
        {item.label || item.type || item.setting || JSON.stringify(item)}{item.count !== undefined ? ` (${item.count}/${item.minimum})` : ""}
      </li>)}</ul>}
    </article>)}
  </section>;
}

export default function ReviewDetail() {
  const { t } = useAuth();
  const { type, id } = useParams();
  const [search] = useSearchParams();
  const revisionId = search.get("revision_id");
  const [comment, setComment] = useState("");
  const [resolution, setResolution] = useState("");
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const client = useQueryClient();
  const key = ["review-item", type, id, revisionId];
  const detail = useQuery({ queryKey: key, queryFn: () => api(`/review/items/${type}/${id}/${revisionId ? `?revision_id=${revisionId}` : ""}`) });
  const action = useMutation({ mutationFn: ({ name, body }) => api(`/review/items/${type}/${id}/${name}/`, { method: "POST", body }),
    onSuccess: async (_, variables) => {
      setError(""); await client.invalidateQueries({ queryKey: ["review-queue"] });
      if (variables.name === "return" || variables.name === "reject" || variables.name === "publish") navigate("/review");
      else await client.invalidateQueries({ queryKey: key });
    }, onError: (e) => setError(e.message) });
  if (detail.isLoading) return <Spinner />;
  if (detail.isError) return <section><ErrorBox>{detail.error.message}</ErrorBox><button className="btn" onClick={() => detail.refetch()}>{t("retry")}</button></section>;
  const data = detail.data;
  const needsResolution = data.conflicts?.length > 0;
  const status = data.status;
  const run = (name) => {
    setError("");
    action.mutate({ name, body: { revision_id: data.revision_id, comment,
      ...(name === "approve" && needsResolution ? { conflict_resolution: resolution } : {}) } });
  };
  return <main className="page-review">
    <Link to="/review">← {t("review_title")}</Link>
    <h1>{data.current?.name || data.current?.text_en || data.current?.steps || t(`review_type_${type}`)}</h1>
    {data.safety_critical && <p className="review-safety">⚠ {t("review_safety")}</p>}
    {error && <ErrorBox>{error}</ErrorBox>}
    <h2>{t("review_changes")}</h2>
    <div className="review-diff">
      <section className="panel"><h3>{t("review_current")}</h3><Payload value={data.current} /></section>
      <section className="panel"><h3>{t("review_proposed")}</h3><Payload value={data.proposed} /></section>
    </div>
    <div className="panel"><h2>{t("review_field_diff")}</h2>
      {!data.diff.length && <p>{t("review_no_diff")}</p>}
      {data.diff.map((change) => <div className="review-field" key={change.field}><strong>{change.field}</strong>
        <div><b>{t("review_current")}: </b><Value value={change.current} /></div><div><b>{t("review_proposed")}: </b><Value value={change.proposed} /></div></div>)}
    </div>
    {needsResolution && <section className="panel review-conflicts"><h2>{t("review_conflict_title")}</h2><p>{t("review_conflict_help")}</p>
      {data.conflicts.map((conflict) => <div className="review-diff" key={conflict.revision_id}>
        <div className="panel"><h3>{t("review_selected_proposal")}</h3><Payload value={data.proposed} /></div>
        <div className="panel"><h3>{t("review_other_proposal")}</h3><Payload value={conflict.payload} /><small>{t("review_author", { name: conflict.author || t("review_unknown") })}</small></div>
      </div>)}
      <Field label={t("review_resolution_choice")}><select value={resolution} onChange={(e) => setResolution(e.target.value)}><option value="">{t("review_choose_resolution")}</option><option value="keep_both">{t("review_keep_both")}</option><option value="ask_third">{t("review_ask_third")}</option><option value="cautious_option">{t("review_cautious")}</option></select></Field>
    </section>}
    <Field label={needsResolution ? t("review_resolution_comment") : t("review_comment")}><textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} /></Field>
    <div className="row review-actions">
      {status === "submitted" && <button className="btn ghost" disabled={action.isPending} onClick={() => run("start")}>{t("review_start")}</button>}
      {(["submitted", "under_review"].includes(status)) && <>
        <button className="btn" disabled={action.isPending || (needsResolution && (!resolution || !comment.trim()))} onClick={() => run("approve")}>{t("review_approve")}</button>
        <button className="btn ghost" disabled={action.isPending || !comment.trim()} onClick={() => run("return")}>{t("review_return")}</button>
        <button className="btn ghost" disabled={action.isPending || !comment.trim()} onClick={() => run("reject")}>{t("review_reject")}</button>
      </>}
      {status === "approved" && <button className="btn" disabled={action.isPending} onClick={() => run("publish")}>{t("review_publish")}</button>}
    </div>
    {action.isPending && <p role="status">{t("review_saving")}</p>}
    <section><h2>{t("review_history")}</h2><ol className="review-timeline">{data.history.map((event, index) => <li key={`${event.status}-${event.created_at}-${index}`}>
      <strong>{t(`review_status_${event.status}`)}</strong><span>{t("review_actor", { name: event.actor })}</span><time dateTime={event.created_at}>{new Date(event.created_at).toLocaleString()}</time>
      {event.comment && <p>{event.comment}</p>}</li>)}</ol></section>
  </main>;
}

function Payload({ value }) {
  if (value == null) return null;
  return <dl className="review-payload">{Object.entries(value).map(([key, val]) => <div key={key}><dt>{key}</dt><dd><Value value={val} /></dd></div>)}</dl>;
}
function Value({ value }) { return <span>{value == null ? "" : typeof value === "object" ? JSON.stringify(value) : String(value)}</span>; }
