import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, trackEvent } from "../api.js";
import { useAuth } from "../auth.jsx";
import CauseCard from "../components/CauseCard.jsx";
import { ObdPanel, Skeleton } from "../components/DiagnosisBits.jsx";
import ShareCard from "../components/ShareCard.jsx";
import StopDriving from "../components/StopDriving.jsx";
import { ErrorBox } from "../components/ui.jsx";
import { errMsg, useTr } from "../helpers.js";

export function DraftBanner() {
  const { t } = useAuth();
  return <p className="draft-banner" role="note">{t("draft_banner")}</p>;
}

export function ResultContent({ result, sessionId = result.id, serverTracked = false }) {
  const { t, lang } = useAuth();
  const tr = useTr();
  const queryClient = useQueryClient();
  const [showShare, setShowShare] = useState(false);
  const vote = useMutation({
    mutationFn: (wasHelpful) => api(`/sessions/${sessionId}/outcome/`, { method: "PATCH", body: { was_helpful: wasHelpful } }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["diagnosis-outcome", sessionId] }),
  });
  const outcome = useQuery({
    queryKey: ["diagnosis-outcome", sessionId],
    queryFn: async () => (await api(`/sessions/${sessionId}/outcome/`)) ?? null,
    enabled: Boolean(sessionId),
    retry: false,
  });
  useEffect(() => {
    if (!serverTracked && sessionId && result.status === "completed") {
      trackEvent("result_viewed", sessionId);
    }
  }, [result.status, serverTracked, sessionId]);

  const causes = result.results || [];
  const obdContext = result.obd_context;
  const answers = result.answers || [];
  const topCause = causes[0];
  const script = result.ask_your_mechanic?.[lang === "roman_ur" ? "roman_ur" : "en"] || "";
  const hasOutcome = Boolean(outcome.data?.id);
  if (result.stop) return <StopDriving message={result.message} />;

  const renderCause = (cause, index) => (
    <CauseCard key={cause.id || cause.cause || index} cause={cause} mechanicScript={cause.ask_your_mechanic || script} />
  );

  return (
    <section className="results result-page-content">
      <ObdPanel context={obdContext} />
      {result.draft_content && <DraftBanner />}

      {/* 1. The answer: the single most likely cause, in full. */}
      {topCause ? (
        <>
          <h2>{tr("result_top_cause", "Most likely cause")}</h2>
          {renderCause(topCause, 0)}
        </>
      ) : (
        <p className="panel">{result.message || t("no_results")}</p>
      )}

      {/* 3. One disclaimer, right under the answer. */}
      <p className="standing-disclaimer">{result.disclaimer || t("disclaimer")}</p>

      {/* 4. Actions. The outcome button says why it matters, because right after a diagnosis it can look premature. */}
      <div className="stack">
        {!hasOutcome && (
          <p className="muted small">
            {tr("outcome_cta_hint", "After your mechanic visit, tell us what they found. It helps us improve.")}
          </p>
        )}
        <div className="row">
          {hasOutcome ? (
            <Link className="btn ghost" to={`/outcome/${sessionId}`}>{t("outcome_edit_link")}</Link>
          ) : (
            <Link className="btn" to={`/outcome/${sessionId}`}>{t("outcome_cta")}</Link>
          )}
          {topCause && (
            <button
              type="button"
              className="btn ghost"
              aria-expanded={showShare}
              onClick={() => setShowShare((value) => !value)}
            >
              {tr("result_share", "Share result")}
            </button>
          )}
          <Link className="btn ghost" to="/history">{t("nav_history")}</Link>
        </div>
        {showShare && topCause && <ShareCard result={result} topCause={topCause} />}
      </div>

      {/* 5. Feedback: one compact row instead of a titled panel. */}
      <section className="result-vote" aria-label={t("result_feedback_title")}>
        <div className="row">
          <strong>{t("result_feedback_title")}</strong>
          <button
            className="btn ghost"
            type="button"
            disabled={vote.isPending || outcome.data?.was_helpful === true}
            onClick={() => vote.mutate(true)}
          >
            {t("result_helpful")}
          </button>
          <button
            className="btn ghost"
            type="button"
            disabled={vote.isPending || outcome.data?.was_helpful === false}
            onClick={() => vote.mutate(false)}
          >
            {t("result_not_helpful")}
          </button>
        </div>
        {outcome.data?.was_helpful != null && <p className="muted small" role="status">{t("result_vote_thanks")}</p>}
        {vote.isError && <ErrorBox>{errMsg(vote.error)}</ErrorBox>}
        {outcome.isError && outcome.error.status !== 404 && <ErrorBox>{errMsg(outcome.error)}</ErrorBox>}
      </section>

      {/* 6. What the user told us: reference only, collapsed. */}
      {(result.free_text || answers.length > 0) && (
        <details className="result-details">
          <summary>{t("diagnosis_evidence_title")}</summary>
          {result.free_text && (
            <p>
              <strong>{t("diagnosis_reported_problem")}:</strong> {result.free_text}
            </p>
          )}
          {answers.length > 0 && (
            <ul>
              {answers.map((answer, index) => (
                <li key={`${answer.question}-${index}`}>
                  <strong>{answer.question}</strong>: {answer.answer}
                </li>
              ))}
            </ul>
          )}
        </details>
      )}
    </section>
  );
}

export default function Result() {
  const { id } = useParams();
  const { t } = useAuth();
  const query = useQuery({ queryKey: ["diagnosis-result", id], queryFn: () => api(`/sessions/${id}/result/`), retry: false });
  if (query.isLoading) return <Skeleton />;
  if (query.isError) {
    return (
      <section className="diagnosis-error">
        <ErrorBox>{errMsg(query.error)}</ErrorBox>
        <button className="btn" type="button" onClick={() => query.refetch()}>{t("retry")}</button>
      </section>
    );
  }
  return (
    <>
      <h1>{t("diagnosis_result_title")}</h1>
      <ResultContent result={query.data} sessionId={id} serverTracked />
    </>
  );
}