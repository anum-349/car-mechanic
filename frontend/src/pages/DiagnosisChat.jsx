import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, trackEvent } from "../api.js";
import { useAuth } from "../auth.jsx";
import { ObdPanel, Skeleton } from "../components/DiagnosisBits.jsx";
import Results from "../components/Results.jsx";
import StopDriving from "../components/StopDriving.jsx";
import { ErrorBox, Field } from "../components/ui.jsx";
import { checkDetail, detailMessage, errMsg, useTr } from "../helpers.js";
import { sessionsKey } from "../api/quries.js";

// One place that turns the server's conversation into thread messages (it was duplicated before).
const toTranscript = (conversation = []) =>
  conversation.map((entry, index) => ({
    id: `${entry.question.id ?? "q"}-${index}`,
    question: entry.question.text,
    answer: entry.answer.label,
  }));

/* ------------------------------------------------------------------ */
/* Pieces                                                              */
/* ------------------------------------------------------------------ */
export function QuestionCard({ question, onAnswer, disabled, answered }) {
  const { t } = useAuth();
  const headingRef = useRef(null);
  const unsure = question.options?.find((option) => option.is_unsure);
  const regular = (question.options ?? []).filter((option) => !option.is_unsure);

  // After the first answer, move focus to each new question so keyboard and screen-reader users land on it.
  useEffect(() => {
    if (answered > 0) headingRef.current?.focus();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question.id]);

  return (
    <section className="question-card" aria-labelledby="question-heading">
      <p className="progress-hint">{t("diagnosis_progress", { number: answered + 1 })}</p>
      <h2 id="question-heading" ref={headingRef} tabIndex={-1}>{question.text}</h2>
      {question.media_url && <img className="question-media" src={question.media_url} alt={question.text} loading="lazy" />}
      <div className="answers" role="group" aria-label={t("your_answer")}>
        {regular.map((option) => (
          <button className="option" type="button" key={option.id} disabled={disabled} onClick={() => onAnswer(option)}>
            {option.label}
          </button>
        ))}
        {/* Only rendered when the question really has a "not sure" option; a permanently disabled button looks broken. */}
        {unsure && (
          <button className="option unsure-option" type="button" disabled={disabled} onClick={() => onAnswer(unsure)}>
            {t("diagnosis_not_sure")}
          </button>
        )}
      </div>
    </section>
  );
}

function Thread({ messages, children }) {
  return (
    <div className="thread" aria-live="polite">
      {messages.map((message) => (
        <div key={message.id}>
          <p className="bot">{message.question}</p>
          <p className="me">{message.answer}</p>
        </div>
      ))}
      {children}
    </div>
  );
}

function UnderstoodSymptoms({ symptoms, onRemove, pending, error }) {
  const { t } = useAuth();
  if (!symptoms.length) return null;
  return (
    <section className="understood-symptoms" aria-label={t("diagnosis_understood_title")}>
      <h2>{t("diagnosis_understood_title")}</h2>
      <ul>
        {symptoms.map((item) => (
          <li key={item.id}>
            <span>{item.text}</span>
            <button
              className="link-btn"
              type="button"
              disabled={pending}
              onClick={() => onRemove(item.id)}
              aria-label={t("diagnosis_remove_symptom", { symptom: item.text })}
            >
              {t("remove")}
            </button>
          </li>
        ))}
      </ul>
      {error && <ErrorBox>{errMsg(error)}</ErrorBox>}
    </section>
  );
}

// Owns its own text state: when the server accepts it the page switches view and this unmounts.
function ClarificationForm({ onSubmit, pending, error }) {
  const { t } = useAuth();
  const tr = useTr();
  const [text, setText] = useState("");
  const [localError, setLocalError] = useState("");
  return (
    <form
      className="stack"
      noValidate
      onSubmit={(event) => {
        event.preventDefault();
        if (pending) return;
        // Same check as the start page, so a session resumed from Home/History gets the same guidance.
        const check = checkDetail(text);
        if (!check.ok) {
          setLocalError(detailMessage(check.code, tr));
          return;
        }
        onSubmit(text.trim());
      }}
    >
      <Field label={t("diagnosis_clarification_label")}>
        <textarea
          rows={4}
          maxLength={2000}
          required
          value={text}
          aria-invalid={Boolean(localError)}
          onChange={(event) => {
            setText(event.target.value);
            setLocalError("");
          }}
        />
      </Field>
      <p className="muted small" aria-live="polite">{text.length}/2000</p>
      {localError && <p className="field-error" role="alert">{localError}</p>}
      {error && <ErrorBox>{errMsg(error)}</ErrorBox>}
      <button className="btn" disabled={!text.trim() || pending}>
        {pending ? t("diagnosis_processing") : t("diagnosis_clarify_submit")}
      </button>
    </form>
  );
}

/* ------------------------------------------------------------------ */
/* Flow                                                                */
/* ------------------------------------------------------------------ */
function DiagnosisFlow({ id }) {
  const { t } = useAuth();
  const tr = useTr();
  const queryClient = useQueryClient();
  const [response, setResponse] = useState(null); // latest server reply after an answer / clarification
  const [messages, setMessages] = useState([]); // thread built locally while `response` is in use
  const [answered, setAnswered] = useState(null);
  const [answerError, setAnswerError] = useState("");
  const [lastOption, setLastOption] = useState(null);
  const [submitting, setSubmitting] = useState(false);
  const submitLock = useRef(false);

  const session = useQuery({
    queryKey: ["diagnosis-session", id],
    queryFn: () => api(`/sessions/${id}/`),
    retry: false,
    staleTime: 0,
  });

  const resetLocal = () => {
    setResponse(null);
    setMessages([]);
    setAnswered(null);
  };

  const answer = useMutation({
    mutationFn: ({ option, questionId }) =>
      api(`/sessions/${id}/answer/`, { method: "POST", body: { question: questionId, option: option.id } }),
  });

  const submitClarification = useMutation({
    mutationFn: (text) => api(`/sessions/${id}/free-text/`, { method: "POST", body: { text } }),
    onSuccess: (data) => {
      // Switching to `response` switches the thread to local state, so seed it or the history would vanish.
      setMessages((previous) => (previous.length ? previous : toTranscript(session.data?.conversation)));
      setResponse(data);
      queryClient.invalidateQueries({ queryKey: ["diagnosis-session", id] });
    },
  });

  const removeSymptom = useMutation({
    mutationFn: (symptomId) => api(`/sessions/${id}/free-text/`, { method: "DELETE", body: { symptom: symptomId } }),
    onSuccess: (_data, symptomId) => {
      resetLocal();
      queryClient.setQueryData(["diagnosis-session", id], (current) =>
        current
          ? { ...current, understood_symptoms: (current.understood_symptoms || []).filter((item) => item.id !== symptomId) }
          : current
      );
      queryClient.invalidateQueries({ queryKey: ["diagnosis-session", id] });
    },
  });

  const flow = response || session.data;
  const isDone = Boolean(flow?.done);

  // History / Home list a finished session as "completed", so refresh them once the result is in.
  useEffect(() => {
    if (isDone) queryClient.invalidateQueries({ queryKey: sessionsKey });
  }, [isDone, queryClient]);

  async function choose(option) {
    const current = response || session.data;
    if (!current?.question || submitLock.current || submitting) return;
    submitLock.current = true;
    setSubmitting(true);
    setLastOption(option);
    setAnswerError("");
    try {
      const next = await answer.mutateAsync({ option, questionId: current.question.id });
      trackEvent("question_answered", id, { question_id: current.question.id });
      setMessages((previous) => {
        const base = previous.length ? previous : toTranscript(session.data?.conversation);
        return [
          ...base,
          { id: `${current.question.id}-${base.length}`, question: current.question.text, answer: option.label },
        ];
      });
      setResponse(next);
      setAnswered((count) => (count ?? session.data?.answers?.length ?? 0) + 1);
    } catch (error) {
      if (error.status === 409) {
        // The session moved on elsewhere (another tab/device): drop local state and take the server's.
        resetLocal();
        queryClient.invalidateQueries({ queryKey: ["diagnosis-session", id] });
        return;
      }
      setAnswerError(errMsg(error));
    } finally {
      submitLock.current = false;
      setSubmitting(false);
    }
  }

  if (session.isLoading) return <Skeleton />;
  if (session.isError) {
    return (
      <section className="diagnosis-error">
        <ErrorBox>{errMsg(session.error)}</ErrorBox>
        <button className="btn" type="button" onClick={() => session.refetch()}>{t("retry")}</button>
      </section>
    );
  }

  const data = session.data;
  if (flow?.stop) return <StopDriving message={flow.message} />;

  const transcript = response ? messages : toTranscript(data.conversation);
  const answeredCount = answered ?? data.answers?.length ?? 0;
  const obdPanel = <ObdPanel context={data.obd_context} />;
  const understood = (
    <UnderstoodSymptoms
      symptoms={data.understood_symptoms || []}
      onRemove={(symptomId) => removeSymptom.mutate(symptomId)}
      pending={removeSymptom.isPending}
      error={removeSymptom.error}
    />
  );

  if (flow?.done) {
    const result = flow.result ? { ...flow.result, id: flow.result.id || flow.id } : { id: flow.id, results: [] };
    const showTranscript = !result.answers?.length && transcript.length > 0;
    return (
      <section>
        <h1>{t("diagnosis_result_title")}</h1>
        {/* <Results> already shows the OBD code, so no separate panel here (it was rendered twice). */}
        {/* The result is what the user came for, so it comes first. */}
        <Results session={result} />
        {/* The recap of their own input is reference material: collapsed by default. */}
        {(showTranscript || (data.understood_symptoms || []).length > 0) && (
          <details className="result-details">
            <summary>{tr("diagnosis_result_inputs", "What you told us")}</summary>
            {understood}
            {showTranscript && <Thread messages={transcript} />}
          </details>
        )}
      </section>
    );
  }

  if (flow?.clarification_required) {
    return (
      <section className="diagnosis-chat">
        {obdPanel}
        <h1>{t("diagnosis_clarification_title")}</h1>
        <p>{t("diagnosis_clarification_prompt")}</p>
        <ClarificationForm
          onSubmit={(text) => submitClarification.mutate(text)}
          pending={submitClarification.isPending}
          error={submitClarification.error}
        />
      </section>
    );
  }

  if (!flow?.question) {
    return (
      <section className="diagnosis-error">
        <ErrorBox>{t("diagnosis_no_question")}</ErrorBox>
        <button className="btn" type="button" onClick={() => session.refetch()}>{t("retry")}</button>
      </section>
    );
  }

  return (
    <section className="diagnosis-chat">
      {obdPanel}
      {understood}
      <p><Link to="/history">{t("nav_history")}</Link></p>
      <p className="chat-intro">{t("chat_hello")}</p>
      <Thread messages={transcript} />
      <QuestionCard question={flow.question} onAnswer={choose} disabled={submitting} answered={answeredCount} />
      {submitting && <p className="muted" role="status">{t("diagnosis_processing")}</p>}
      {answerError && (
        <div className="diagnosis-error">
          <ErrorBox>{answerError}</ErrorBox>
          <button className="btn" type="button" disabled={submitting || !lastOption} onClick={() => choose(lastOption)}>
            {t("retry")}
          </button>
        </div>
      )}
    </section>
  );
}

// Keyed by id: going from /diagnose/1 to /diagnose/2 re-uses this route component, which would
// otherwise carry the previous session's answers and thread into the new one.
export default function DiagnosisChat() {
  const { id } = useParams();
  return <DiagnosisFlow key={id} id={id} />;
}