import { useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import StopDriving from "../components/StopDriving.jsx";
import { Empty, ErrorBox, Field } from "../components/ui.jsx";
import { checkDetail, detailMessage, errMsg, useModal, useTr } from "../helpers.js";
import { sessionsKey, useCars } from "../api/quries.js";
import { Skeleton, ObdPanel } from "../components/DiagnosisBits.jsx";

const QUICK_SYMPTOMS = [
  ["diagnosis_quick_no_start", "Engine won't start"],
  ["diagnosis_quick_brake_noise", "Strange noise when braking"],
  ["diagnosis_quick_check_engine", "Check engine light is on"],
  ["diagnosis_quick_overheating", "Engine overheating"],
  ["diagnosis_quick_smoke", "Smoke from exhaust"],
  ["diagnosis_quick_vibration", "Vibration while driving"],
  ["diagnosis_quick_ac", "AC not cooling"],
  ["diagnosis_quick_battery", "Battery keeps dying"],
];

// 0 = empty, 1 = not enough yet, 2 = good enough, 3 = detailed
function detailLevel(text) {
  const trimmed = text.trim();
  if (!trimmed) return 0;
  if (!checkDetail(trimmed).ok) return 1;
  return trimmed.split(/\s+/).length >= 6 && trimmed.length >= 30 ? 3 : 2;
}

function DetailTips() {
  const tr = useTr();
  return (
    <ul className="detail-tips muted small">
      <li>{tr("diagnosis_tip_what", "What you notice: a noise, smell, warning light, vibration…")}</li>
      <li>{tr("diagnosis_tip_when", "When it happens: starting, braking, at speed, when the engine is cold…")}</li>
      <li>{tr("diagnosis_tip_long", "How long it has been happening")}</li>
    </ul>
  );
}

// Live feedback while typing, so the user knows whether it is enough BEFORE pressing Start.
function DetailMeter({ text }) {
  const tr = useTr();
  const level = detailLevel(text);
  const messages = [
    null,
    tr("diagnosis_detail_short", "Add a little more: what do you notice, and when does it happen?"),
    tr("diagnosis_detail_ok", "Good. When it happens and how long it has been going on make the result more accurate."),
    tr("diagnosis_detail_good", "Great, that is enough detail."),
  ];
  return (
    <div aria-live="polite">
      <meter min={0} max={3} low={1.5} high={2.5} optimum={3} value={level} aria-label={tr("diagnosis_detail_meter", "Detail level")} />
      {messages[level] && <p className="muted small">{messages[level]}</p>}
      <p className="muted small">{text.length}/2000</p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Shown when the server could not understand the description          */
/* ------------------------------------------------------------------ */
function DetailDialog({ initialText, serverMessage, attempts, pending, error, onSubmit, onClose }) {
  const { t } = useAuth();
  const tr = useTr();
  const [text, setText] = useState(initialText);
  const [localError, setLocalError] = useState("");
  const textRef = useRef(null);
  useModal(onClose, pending);

  function submit(event) {
    event.preventDefault();
    const check = checkDetail(text);
    if (!check.ok) {
      setLocalError(detailMessage(check.code, tr));
      textRef.current?.focus();
      return;
    }
    setLocalError("");
    onSubmit(text.trim());
  }

  return (
    <div
      className="records-backdrop"
      role="presentation"
      onClick={(event) => event.target === event.currentTarget && !pending && onClose()}
    >
      <form
        className="records-dialog panel stack"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="detail-dialog-title"
        aria-describedby="detail-dialog-body"
        onSubmit={submit}
      >
        <h2 id="detail-dialog-title">
          {tr("diagnosis_retry_title", "We couldn't understand that description")}
        </h2>
        <p id="detail-dialog-body">
          {serverMessage ||
            tr(
              "diagnosis_retry_body",
              "We couldn't match what you wrote to a car problem. Please describe what you notice in a bit more detail."
            )}
        </p>
        <DetailTips />

        <Field label={t("diagnosis_free_text")}>
          <textarea
            ref={textRef}
            rows={4}
            maxLength={2000}
            required
            autoFocus
            value={text}
            aria-invalid={Boolean(localError)}
            onChange={(event) => {
              setText(event.target.value);
              setLocalError("");
            }}
          />
        </Field>
        <DetailMeter text={text} />
        {localError && <p className="field-error" role="alert">{localError}</p>}
        {error && <ErrorBox>{errMsg(error)}</ErrorBox>}

        {/* Error recovery: after repeated failures, offer other ways to get an answer. */}
        {attempts >= 2 && (
          <p className="muted small">
            {tr("diagnosis_still_stuck", "Still stuck?")} <Link to="/obd">{t("nav_obd") || "OBD code lookup"}</Link>
            {" · "}
            <Link to="/lights">{t("nav_lights")}</Link>
          </p>
        )}

        <div className="row">
          <button className="btn" disabled={pending}>
            {pending ? t("diagnosis_processing") : tr("diagnosis_try_again", "Try again")}
          </button>
          <button type="button" className="btn ghost" onClick={onClose} disabled={pending}>
            {t("cancel")}
          </button>
        </div>
      </form>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */
export default function NewDiagnosis() {
  const { t } = useAuth();
  const tr = useTr();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [params] = useSearchParams();
  const [safeToContinue, setSafeToContinue] = useState(false);
  const [freeText, setFreeText] = useState("");
  const [detailError, setDetailError] = useState("");
  const [carChoice, setCarChoice] = useState(params.get("car") || "");
  const [skipObd, setSkipObd] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [dialogMessage, setDialogMessage] = useState("");
  const [attempts, setAttempts] = useState(0);
  // A session that was created but still needs a better description. Re-used on retry,
  // so a failed attempt never leaves a trail of empty "in progress" sessions behind.
  const [openSession, setOpenSession] = useState(null); // { id, car }
  const [stop, setStop] = useState(null);
  const textRef = useRef(null);

  // An unknown OBD code must not trap the user: they can drop it and describe the problem instead.
  const urlObd = params.get("obd")?.trim().toUpperCase() || "";
  const obdCode = skipObd ? "" : urlObd;

  const carsQuery = useCars(); // shared cache with Home / History / Garage
  const cars = carsQuery.data ?? [];
  // Only accept a car that really exists, and pre-select it when the user has exactly one.
  const car = cars.some((item) => String(item.id) === carChoice)
    ? carChoice
    : cars.length === 1
      ? String(cars[0].id)
      : "";

  const obd = useQuery({
    queryKey: ["diagnosis-obd-code", obdCode],
    queryFn: () => api(`/obd/${encodeURIComponent(obdCode)}/`),
    enabled: Boolean(obdCode),
    retry: false,
  });

  function needDetail(message) {
    setAttempts((count) => count + 1);
    setDialogMessage(message);
    setDialogOpen(true);
  }

  // Decides what a server reply means: stop, "need more detail", or go on to the questions.
  function handleFlow(flow, sessionId, carId) {
    queryClient.invalidateQueries({ queryKey: sessionsKey });
    if (flow.stop) {
      setDialogOpen(false);
      setStop({ message: flow.message });
      return;
    }
    if (!obdCode && flow.clarification_required) {
      setOpenSession({ id: sessionId, car: carId });
      needDetail("");
      return;
    }
    setDialogOpen(false);
    navigate(`/diagnose/${sessionId}`, { replace: true });
  }

  const isDetailError = (error) => !obdCode && error?.status === 400;

  const start = useMutation({
    mutationFn: (text) =>
      api("/sessions/", {
        method: "POST",
        body: { car: Number(car), ...(obdCode ? { obd_code: obdCode } : { free_text: text }) },
      }),
    onSuccess: (flow) => handleFlow(flow, flow.id, car),
    onError: (error) => isDetailError(error) && needDetail(errMsg(error)),
  });

  const refine = useMutation({
    mutationFn: ({ sessionId, text }) =>
      api(`/sessions/${sessionId}/free-text/`, { method: "POST", body: { text } }),
    onSuccess: (flow, { sessionId }) => handleFlow(flow, sessionId, openSession?.car ?? car),
    onError: (error) => isDetailError(error) && needDetail(errMsg(error)),
  });

  const pending = start.isPending || refine.isPending;
  // 400s about the description are shown in the dialog; anything else (network, 500) shows inline.
  const submitError = [start.error, refine.error].find((error) => error && !isDetailError(error));

  function send(text) {
    if (openSession && openSession.car === car) refine.mutate({ sessionId: openSession.id, text });
    else {
      setOpenSession(null); // different car: that old session can't be reused
      start.mutate(text);
    }
  }

  function submit(event) {
    event.preventDefault();
    if (!car || pending) return;
    if (!obdCode) {
      const check = checkDetail(freeText);
      if (!check.ok) {
        setDetailError(detailMessage(check.code, tr));
        textRef.current?.focus();
        return;
      }
    }
    send(freeText.trim());
  }

  function retryFromDialog(text) {
    setFreeText(text);
    setDetailError("");
    send(text);
  }

  function closeDialog() {
    setDialogOpen(false);
    if (openSession) {
      setDetailError(tr("diagnosis_detail_more", "We need a little more detail. Add it here and press Start again."));
    }
    requestAnimationFrame(() => textRef.current?.focus());
  }

  function addSymptom(label) {
    setFreeText((current) => (current.trim() ? `${current.trim()}. ${label}` : label));
    setDetailError("");
    textRef.current?.focus();
  }

  if (stop) return <StopDriving message={stop.message} />;

  const ready = Boolean(car) && (obdCode ? Boolean(obd.data) : Boolean(freeText.trim())) && !pending;

  return (
    <div className="start-diagnosis stack">
      {!safeToContinue ? (
        <section className="prescreen" aria-labelledby="prescreen-title">
          <h1 id="prescreen-title">{t("diagnosis_safety_question")}</h1>
          <p>{t("diagnosis_safety_detail")}</p>
          <div className="answers">
            <button type="button" className="option danger-option" onClick={() => navigate("/stop-driving")}>
              {t("diagnosis_safety_yes")}
            </button>
            <button type="button" className="option" onClick={() => setSafeToContinue(true)}>
              {t("diagnosis_safety_no")}
            </button>
          </div>
        </section>
      ) : (
        <>
          <h1>{t("diagnose_title")}</h1>

          {carsQuery.isLoading && <Skeleton />}
          {carsQuery.isError && (
            <>
              <ErrorBox>{errMsg(carsQuery.error)}</ErrorBox>
              <button type="button" className="btn" onClick={() => carsQuery.refetch()}>{t("retry")}</button>
            </>
          )}

          {obdCode && obd.isLoading && <Skeleton rows={1} />}
          {obdCode && obd.isError && (
            <>
              <ErrorBox>{errMsg(obd.error)}</ErrorBox>
              <button type="button" className="btn ghost" onClick={() => setSkipObd(true)}>
                {tr("diagnosis_describe_instead", "Describe the problem instead")}
              </button>
            </>
          )}
          {obdCode && obd.data && <ObdPanel context={obd.data} />}

          {carsQuery.isSuccess && cars.length === 0 && (
            <Empty action={<Link className="btn" to="/garage">{t("add_car_first")}</Link>}>
              {t("diagnosis_need_car")}
            </Empty>
          )}

          {cars.length > 0 && (!obdCode || obd.data) && (
            <form className="stack" onSubmit={submit} noValidate>
              <fieldset className="choices">
                <legend>{t("diagnosis_choose_car")}</legend>
                {cars.map((item) => (
                  <label key={item.id} className={`choice ${String(item.id) === car ? "on" : ""}`}>
                    <input
                      type="radio"
                      name="car"
                      value={item.id}
                      checked={String(item.id) === car}
                      onChange={() => setCarChoice(String(item.id))}
                    />
                    <span>
                      <strong>{item.nickname || item.car_model_label}</strong>
                      {item.nickname && <span className="muted small"> {item.car_model_label}</span>}
                      <span className="muted small"> · {item.year}</span>
                    </span>
                  </label>
                ))}
              </fieldset>

              {!obdCode && (
                <section className="stack">
                  <Field label={t("diagnosis_free_text")} hint={t("diagnosis_free_text_hint")}>
                    <textarea
                      ref={textRef}
                      rows={4}
                      maxLength={2000}
                      required
                      value={freeText}
                      placeholder={tr(
                        "diagnosis_free_placeholder",
                        "e.g. The engine shakes and the check-engine light comes on when I brake at speed"
                      )}
                      aria-invalid={Boolean(detailError)}
                      aria-describedby="detail-help"
                      onChange={(event) => {
                        setFreeText(event.target.value);
                        setDetailError("");
                      }}
                    />
                  </Field>
                  <div id="detail-help">
                    <DetailTips />
                    <DetailMeter text={freeText} />
                    {detailError && <p className="field-error" role="alert">{detailError}</p>}
                  </div>
                  <div className="chips" role="group" aria-label={tr("diagnosis_quick_symptoms", "Common problems: tap to add")}>
                    {QUICK_SYMPTOMS.map(([key, fallback]) => {
                      const label = tr(key, fallback);
                      return (
                        <button key={key} type="button" className="chip" onClick={() => addSymptom(label)}>
                          + {label}
                        </button>
                      );
                    })}
                  </div>
                </section>
              )}

              <ErrorBox>{errMsg(submitError)}</ErrorBox>
              <button className="btn" type="submit" disabled={!ready}>
                {pending ? t("diagnosis_starting") : submitError ? t("retry") : t("start_diag")}
              </button>
            </form>
          )}
        </>
      )}

      {dialogOpen && (
        <DetailDialog
          initialText={freeText}
          serverMessage={dialogMessage}
          attempts={attempts}
          pending={pending}
          error={submitError}
          onSubmit={retryFromDialog}
          onClose={closeDialog}
        />
      )}
    </div>
  );
}