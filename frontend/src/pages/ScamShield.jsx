import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api, getAll, trackEvent } from "../api.js";
import { useAuth } from "../auth.jsx";
import ConfidenceBar from "../components/ConfidenceBar.jsx";
import CostRange from "../components/CostRange.jsx";
import MechanicScript from "../components/MechanicScript.jsx";
import ShareCard from "../components/ShareCard.jsx";
import { Empty, ErrorBox, Field, Spinner, formatDate, pkr } from "../components/ui.jsx";
import { errMsg, useTr } from "../helpers.js";
import { useCars, useCategories } from "../api/quries.js";

const ALT_PREVIEW = 3; // how many alternative causes to show before "Show all"

const VERDICTS = {
  plausible: { key: "scam_verdict_plausible", icon: "✓", className: "ok" },
  doubtful: { key: "scam_verdict_doubtful", icon: "?", className: "warn" },
  suspicious: { key: "scam_verdict_suspicious", icon: "!", className: "bad" },
};

// Plain function, not a component, so it is camelCase.
function likelihoodBand(confidence) {
  const value = Number(confidence);
  if (value >= 0.8) return "very likely";
  if (value >= 0.5) return "likely";
  if (value >= 0.2) return "possible";
  return "unlikely";
}

/* ------------------------------------------------------------------ */
/* Result panel                                                        */
/* ------------------------------------------------------------------ */
function VerdictResult({ data, verdict, quotedPrice, recommended, shareTopCause, busy, onRecheck, onReset, headingRef }) {
  const { t } = useAuth();
  const tr = useTr();
  const [showAllAlternatives, setShowAllAlternatives] = useState(false);
  const cost = data.cost;
  const reasons = data.reasons ?? [];
  const proofs = data.proof_suggestions ?? [];
  const verdictKey = verdict?.key || "scam_verdict_doubtful";

  // Alternatives = every matched cause except the one that was just checked, most likely first.
  const alternatives = useMemo(
    () =>
      [...(data.candidate_causes ?? [])]
        .filter((candidate) => candidate.id !== data.claimed_cause)
        .sort((a, b) => (Number(b.confidence) || 0) - (Number(a.confidence) || 0)),
    [data]
  );
  const shownAlternatives = showAllAlternatives ? alternatives : alternatives.slice(0, ALT_PREVIEW);

  return (
    <section className={`scam-verdict verdict ${verdict?.className || "warn"}`}>
      <h2 ref={headingRef} tabIndex={-1}>
        <span aria-hidden="true" className="scam-verdict-icon">{verdict?.icon || "?"}</span> {t(verdictKey)}
      </h2>
      {data.limited && <p className="scam-limited">{t("scam_limited")}</p>}

      {/* 1. The price: the core of the verdict */}
      <p>
        {tr("scam_you_were_quoted", "You were quoted")} <strong>{pkr(Number(quotedPrice))}</strong>
      </p>
      {data.price_basis === "other_city" && cost?.city && (
        <p className="muted small">{t("scam_fallback_city", { city: cost.city })}</p>
      )}
      {cost?.total_max != null && (
        <p>
          {t("scam_price_range", { city: cost.city, min: pkr(cost.total_min), max: pkr(cost.total_max) })}
        </p>
      )}

      {/* 2. Why */}
      {reasons.length > 0 && (
        <>
          <h3>{t("scam_reasons")}</h3>
          <ul>
            {reasons.map((reason, index) => (
              <li key={`${index}-${reason}`}>{reason}</li>
            ))}
          </ul>
        </>
      )}

      {/* 3. What our own diagnosis says */}
      {recommended && (
        <section className="scam-recommendation panel">
          <h3>{t("scam_recommendation_title")}</h3>
          <p>{t("scam_recommendation_intro")}</p>
          {data.claimed_cause && Number(data.claimed_cause) !== Number(recommended.cause) && (
            <p className="scam-limited">{t("scam_recommendation_mismatch")}</p>
          )}
          <h4>{recommended.cause_name}</h4>
          <ConfidenceBar confidence={recommended.confidence} band={recommended.band} />
          <CostRange cost={recommended.cost} />
          <MechanicScript text={recommended.ask_your_mechanic} />
        </section>
      )}

      {/* 4. What to ask for */}
      {proofs.length > 0 && (
        <>
          <h3>{t("scam_proof_title")}</h3>
          <ul>
            {proofs.map((suggestion, index) => (
              <li key={`${index}-${suggestion}`}>{suggestion}</li>
            ))}
          </ul>
        </>
      )}

      {/* 5. Alternatives: top few only, with likelihood. Clicking one re-checks immediately. */}
      {alternatives.length > 0 && (
        <div className="scam-candidates">
          <h3>{t("scam_candidate_list")}</h3>
          <div className="row">
            {shownAlternatives.map((candidate) => {
              const pct = Number.isFinite(Number(candidate.confidence))
                ? Math.round(Number(candidate.confidence) * 100)
                : null;
              return (
                <button
                  className="btn ghost"
                  key={candidate.id}
                  type="button"
                  disabled={busy}
                  onClick={() => onRecheck(candidate)}
                >
                  {candidate.name}
                  {pct != null && <span className="muted small"> {pct}%</span>}
                </button>
              );
            })}
          </div>
          {alternatives.length > ALT_PREVIEW && (
            <button
              type="button"
              className="link-btn"
              aria-expanded={showAllAlternatives}
              onClick={() => setShowAllAlternatives((value) => !value)}
            >
              {showAllAlternatives
                ? tr("show_less", "Show less")
                : `${tr("show_all", "Show all")} (${alternatives.length})`}
            </button>
          )}
        </div>
      )}

      <ShareCard result={{ verdict: t(verdictKey) }} topCause={shareTopCause} heading={t("scam_share_heading")} />

      <div className="row">
        <button type="button" className="btn ghost" onClick={onReset}>
          {tr("scam_check_another", "Check another quote")}
        </button>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */
export default function ScamShield() {
  const { t, pick } = useAuth();
  const tr = useTr();
  const [sessionId, setSessionId] = useState("");
  const [claimedCause, setClaimedCause] = useState("");
  const [claimText, setClaimText] = useState("");
  const [quotedPrice, setQuotedPrice] = useState("");
  const headingRef = useRef(null);

  // `?status=completed` is a hint to the backend; the client-side filter below is the safety net.
  const sessions = useQuery({
    queryKey: ["scam-check-sessions"],
    queryFn: () => getAll("/sessions/?status=completed"),
    retry: false,
  });
  const causes = useQuery({
    queryKey: ["scam-check-causes"],
    queryFn: () => getAll("/knowledge/causes/"),
    retry: false,
  });
  // Shared with Home/History; only used to make the session dropdown readable.
  const carsQuery = useCars();
  const categoriesQuery = useCategories();
  const sessionResult = useQuery({
    queryKey: ["scam-check-session-result", sessionId],
    queryFn: () => api(`/sessions/${sessionId}/result/`),
    enabled: Boolean(sessionId),
    retry: false,
  });
  const check = useMutation({
    mutationFn: (body) => api("/scam-check/", { method: "POST", body }),
    onSuccess: (_data, variables) => trackEvent("scam_check_run", variables.session),
  });

  const completedSessions = useMemo(
    () => (sessions.data || []).filter((session) => session.status === "completed"),
    [sessions.data]
  );
  const causeList = useMemo(
    () => [...(causes.data || [])].sort((a, b) => String(a.name).localeCompare(String(b.name))),
    [causes.data]
  );

  const sessionLabel = (session) => {
    const category = (categoriesQuery.data || []).find((item) => item.id === session.category);
    const car = (carsQuery.data || []).find((item) => item.id === session.car);
    const title = session.obd_code || (category ? pick(category, "name") : t("history_diagnosis"));
    return [title, car && (car.nickname || car.car_model_label), formatDate(session.started_at)]
      .filter(Boolean)
      .join(" · ");
  };

  const ourTop = sessionResult.data?.results?.[0];
  const recommendedSolution = ourTop;
  const selectedCause = causeList.find((cause) => String(cause.id) === claimedCause);
  const responseCause = check.data?.claimed_cause
    ? causeList.find((cause) => cause.id === check.data.claimed_cause)
    : null;
  const topCandidate = check.data?.candidate_causes?.find((cause) => cause.id === check.data.claimed_cause);
  const shareCause = selectedCause || responseCause || (topCandidate && { name: topCandidate.name });
  const shareTopCause = shareCause
    ? {
        cause_name: shareCause.name,
        band: topCandidate ? likelihoodBand(topCandidate.confidence) : "unlikely",
        cost: check.data?.cost,
      }
    : null;
  const verdict = check.data && VERDICTS[check.data.verdict];
  const priceNumber = Number(quotedPrice);

  // Move focus to the verdict when it arrives: scrolls it into view and announces it to screen readers.
  useEffect(() => {
    if (check.data) headingRef.current?.focus();
  }, [check.data]);

  // Editing any input invalidates the previous verdict.
  const edit = (setter) => (event) => {
    setter(event.target.value);
    check.reset();
  };

  function run(overrides = {}) {
    const cause = overrides.claimedCause ?? claimedCause;
    const text = (overrides.claimText ?? claimText).trim();
    check.mutate({
      session: Number(sessionId),
      ...(cause ? { claimed_cause: Number(cause) } : {}),
      claim_text: text,
      quoted_price: Number(quotedPrice),
    });
  }

  function submit(event) {
    event.preventDefault();
    run();
  }

  function recheckWith(candidate) {
    const text = claimText.trim() || candidate.name;
    setClaimedCause(String(candidate.id));
    setClaimText(text);
    run({ claimedCause: String(candidate.id), claimText: text });
  }

  function startOver() {
    setSessionId("");
    setClaimedCause("");
    setClaimText("");
    setQuotedPrice("");
    check.reset();
    window.scrollTo({ top: 0 });
  }

  if (sessions.isLoading) return <Spinner />;
  if (sessions.isError) {
    return (
      <section className="diagnosis-error">
        <ErrorBox>{errMsg(sessions.error)}</ErrorBox>
        <button className="btn" type="button" onClick={() => sessions.refetch()}>{t("retry")}</button>
      </section>
    );
  }

  return (
    <>
      <h1>{t("scam_title")}</h1>
      <p className="muted">{t("scam_intro")}</p>

      {!completedSessions.length ? (
        <Empty action={<Link className="btn" to="/diagnose">{t("start_diag")}</Link>}>{t("scam_no_sessions")}</Empty>
      ) : (
        <form className="stack" onSubmit={submit}>
          <section className="panel stack">
            <h2>{tr("scam_step_diagnosis", "1. Your diagnosis")}</h2>
            <Field label={t("scam_session_label")}>
              <select
                required
                value={sessionId}
                onChange={(event) => {
                  setSessionId(event.target.value);
                  setClaimedCause("");
                  check.reset();
                }}
              >
                <option value="">{t("scam_session_placeholder")}</option>
                {completedSessions.map((session) => (
                  <option key={session.id} value={session.id}>{sessionLabel(session)}</option>
                ))}
              </select>
            </Field>
            {sessionResult.isLoading && <Spinner />}
            {ourTop && (
              <p className="muted small">
                {tr("scam_our_diagnosis", "Our top diagnosis")}: <strong>{ourTop.cause_name}</strong>
                {Number.isFinite(Number(ourTop.confidence)) &&
                  `, ${Math.round(Number(ourTop.confidence) * 100)}% ${t("likelihood")}`}
              </p>
            )}
            {sessionResult.isError && <ErrorBox>{errMsg(sessionResult.error)}</ErrorBox>}
          </section>

          <section className="panel stack">
            <h2>{tr("scam_step_claim", "2. What the mechanic said")}</h2>
            <Field label={t("scam_cause_label")} hint={t("scam_cause_hint")}>
              <select value={claimedCause} onChange={edit(setClaimedCause)} disabled={causes.isLoading}>
                <option value="">{causes.isLoading ? t("loading") : t("scam_cause_unknown")}</option>
                {causeList.map((cause) => (
                  <option key={cause.id} value={cause.id}>{cause.name}</option>
                ))}
              </select>
            </Field>
            {/* Causes are optional input, so a failed load must not block the page. */}
            {causes.isError && (
              <p className="muted small">
                {tr("scam_causes_failed", "Couldn't load the list of causes. Describe the claim below instead.")}{" "}
                <button type="button" className="link-btn" onClick={() => causes.refetch()}>{t("retry")}</button>
              </p>
            )}
            <Field label={t("scam_claim_label")}>
              <input value={claimText} onChange={edit(setClaimText)} maxLength={300} required={!claimedCause} />
            </Field>
          </section>

          <section className="panel stack">
            <h2>{tr("scam_step_quote", "3. The quote")}</h2>
            <Field label={t("scam_price_label")}>
              <input
                type="number"
                min="1"
                max="100000000"
                step="1"
                inputMode="numeric"
                value={quotedPrice}
                onChange={edit(setQuotedPrice)}
                required
              />
            </Field>
            {priceNumber > 0 && <p className="muted small" aria-live="polite">{pkr(priceNumber)}</p>}
          </section>

          <ErrorBox>{errMsg(check.error)}</ErrorBox>
          <button className="btn" type="submit" disabled={check.isPending || sessionResult.isLoading || !sessionId}>
            {check.isPending ? t("scam_checking") : t("scam_submit")}
          </button>
        </form>
      )}

      {/* Always-mounted live region so assistive tech reliably announces what appears inside it. */}
      <div aria-live="polite">
        {check.data && (
          <VerdictResult
            data={check.data}
            verdict={verdict}
            quotedPrice={quotedPrice}
            recommended={recommendedSolution}
            shareTopCause={shareTopCause}
            busy={check.isPending}
            onRecheck={recheckWith}
            onReset={startOver}
            headingRef={headingRef}
          />
        )}
      </div>
    </>
  );
}