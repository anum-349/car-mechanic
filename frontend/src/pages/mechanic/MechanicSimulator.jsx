import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, getAll } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import { QuestionCard } from "../DiagnosisChat.jsx";
import StopDriving from "../../components/StopDriving.jsx";
import { Empty, ErrorBox, Field, Spinner } from "../../components/ui.jsx";

export default function MechanicSimulator() {
  const { t, user } = useAuth();
  const [carModel, setCarModel] = useState("");
  const [category, setCategory] = useState("");
  const [answers, setAnswers] = useState([]);
  const [showLinkEditor, setShowLinkEditor] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const lock = useRef(false);
  const options = useQuery({
    queryKey: ["mechanic-simulator-options"],
    queryFn: async () => {
      const [models, makes, categories] = await Promise.all([getAll("/garage/models/"), getAll("/garage/makes/"), getAll("/categories/")]);
      return { models, makes, categories };
    },
  });
  const simulation = useMutation({ mutationFn: (payload) => api("/mechanic/simulator/", { method: "POST", body: payload }) });

  function start() {
    if (!carModel || !category || lock.current) return;
    setAnswers([]); setErrorMessage(""); setShowLinkEditor(false);
    simulation.mutate({ car_model_id: Number(carModel), category_id: Number(category), answers: [], include_drafts: true });
  }
  async function answer(option) {
    if (lock.current || !simulation.data?.next_question) return;
    lock.current = true;
    setErrorMessage("");
    const nextAnswers = [...answers, { question: simulation.data.next_question.id, option: option.id }];
    setAnswers(nextAnswers);
    try {
      await simulation.mutateAsync({ car_model_id: Number(carModel), category_id: Number(category), answers: nextAnswers, include_drafts: true });
    } catch (error) {
      setAnswers(answers);
      setErrorMessage(error.message);
    } finally { lock.current = false; }
  }

  if (options.isLoading) return <Spinner />;
  if (options.isError) return <section><ErrorBox>{options.error.message}</ErrorBox><button className="btn" onClick={() => options.refetch()}>{t("retry")}</button></section>;
  const model = options.data.models.find((item) => String(item.id) === carModel);
  const selectedCategory = options.data.categories.find((item) => String(item.id) === category);
  const topCause = simulation.data?.ranked_causes?.[0];
  if (simulation.data?.stop) return <StopDriving message={t("mechanic_simulator_safety", { symptom: simulation.data.safety_symptom?.text || "" })} />;

  return <main className="mechanic-area">
    <Link to="/mechanic">← {t("mechanic_dashboard_title")}</Link>
    <h1>{t("mechanic_simulator_title")}</h1>
    <p>{t("mechanic_simulator_intro")}</p>
    <div className="panel mechanic-step">
      <Field label={t("mechanic_simulator_car")}><select value={carModel} onChange={(e) => setCarModel(e.target.value)}><option value="">{t("mechanic_simulator_choose_car")}</option>{options.data.models.map((item) => <option key={item.id} value={item.id}>{options.data.makes?.find((make) => make.id === item.car_make)?.name} {item.name} {item.generation}</option>)}</select></Field>
      <Field label={t("mechanic_simulator_problem")}><select value={category} onChange={(e) => setCategory(e.target.value)}><option value="">{t("mechanic_simulator_choose_problem")}</option>{options.data.categories.map((item) => <option key={item.id} value={item.id}>{item.name_en}</option>)}</select></Field>
      <button className="btn" type="button" disabled={!carModel || !category || simulation.isPending} onClick={start}>{simulation.isPending ? t("mechanic_simulator_running") : t("mechanic_simulator_start")}</button>
    </div>
    {simulation.isError && <><ErrorBox>{simulation.error.message}</ErrorBox><button className="btn ghost" disabled={simulation.isPending} onClick={start}>{t("retry")}</button></>}
    {simulation.data && <>
      <p className="chip">{t("mechanic_simulated_label")}: {model?.name}, {selectedCategory?.name_en}</p>
      {simulation.data.evidence?.present?.length > 0 && <section className="panel"><h2>{t("mechanic_sim_evidence")}</h2><ul>{simulation.data.evidence.present.map((item) => <li key={item.id}>{item.symptom}</li>)}</ul></section>}
      {simulation.data.ranked_causes.length === 0 ? <Empty>{t("mechanic_sim_no_causes")}</Empty> : <section className="mechanic-sim-results"><h2>{t("mechanic_sim_ranked")}</h2>
        {simulation.data.ranked_causes.map((item) => <article className="panel" key={item.cause.id}><p className="small muted">{t("mechanic_sim_rank", { rank: item.rank })}</p><h3>{item.cause.name}</h3><p>{item.explanation}</p>
          {item.supporting_symptoms.length > 0 && <p><strong>{t("mechanic_sim_supported_by")}</strong> {item.supporting_symptoms.map((x) => x.symptom).join(", ")}</p>}
          {item.contradicting_symptoms.length > 0 && <p><strong>{t("mechanic_sim_not_supported_by")}</strong> {item.contradicting_symptoms.map((x) => x.symptom).join(", ")}</p>}
          {item.contributing_links.length > 0 && <p className="muted small">{item.contributing_links.map((link) => `${link.symptom}: ${t(`mechanic_strength_${link.strength}`)} (${t(`mechanic_sim_${link.contribution}`)})`).join(" · ")}</p>}
        </article>)}
      </section>}
      {simulation.data.next_question ? <QuestionCard question={simulation.data.next_question} onAnswer={answer} disabled={simulation.isPending} answered={answers.length} /> : <p className="panel">{t("mechanic_sim_questions_done")}</p>}
      {errorMessage && <><ErrorBox>{errorMessage}</ErrorBox><button className="btn ghost" disabled={simulation.isPending} onClick={() => answer({ id: answers.at(-1)?.option })}>{t("retry")}</button></>}
      {topCause && <section className="mechanic-wrong-panel"><button type="button" className="btn danger-option" onClick={() => setShowLinkEditor((value) => !value)}>{t("mechanic_sim_wrong")}</button>
        {showLinkEditor && <SymptomLinkEditor key={`${topCause.cause.id}-${topCause.cause.status}`} result={topCause} symptoms={simulation.data.editable_symptoms} userId={user?.id} />}
      </section>}
    </>}
  </main>;
}

function SymptomLinkEditor({ result, symptoms, userId }) {
  const { t } = useAuth();
  const [strengths, setStrengths] = useState(() => Object.fromEntries(result.all_links.map((link) => [link.symptom_id, link.strength])));
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const save = useMutation({
    mutationFn: async () => {
      if (result.cause.created_by && result.cause.created_by !== userId) throw new Error(t("mechanic_sim_not_owner"));
      if (!["draft", "ai_draft"].includes(result.cause.status)) throw new Error(t("mechanic_sim_published_readonly"));
      if (result.cause.status === "ai_draft" && !result.cause.created_by) {
        await api(`/mechanic/items/causes/${result.cause.id}/claim/`, { method: "POST", body: {} });
      }
      const existing = new Map(result.all_links.map((link) => [link.symptom_id, link]));
      for (const symptom of symptoms) {
        const value = strengths[symptom.id];
        if (!value) continue;
        const link = existing.get(symptom.id);
        if (link) await api(`/mechanic/items/links/${link.id}/`, { method: "PATCH", body: { strength: value } });
        else await api("/mechanic/items/links/", { method: "POST", body: { cause: result.cause.id, symptom: symptom.id, strength: value } });
      }
    },
    onSuccess: () => { setError(""); setMessage(t("mechanic_sim_links_saved")); },
    onError: (err) => { setMessage(""); setError(err.message); },
  });
  return <section className="panel mechanic-link-editor" aria-label={t("mechanic_sim_link_editor")}>
    <h2>{t("mechanic_sim_edit_links", { cause: result.cause.name })}</h2>
    <p>{t("mechanic_sim_link_editor_help")}</p>
    {symptoms.map((symptom) => <div className="mechanic-link-row" key={symptom.id}><strong>{symptom.text}</strong><div className="mechanic-strength">
      {["always", "often", "sometimes", "rarely"].map((strength) => <button key={strength} type="button" className={`btn ghost${strengths[symptom.id] === strength ? " on" : ""}`} aria-pressed={strengths[symptom.id] === strength} onClick={() => setStrengths((current) => ({ ...current, [symptom.id]: strength }))}>{t(`mechanic_strength_${strength}`)}</button>)}
    </div></div>)}
    {error && <ErrorBox>{error}</ErrorBox>}{message && <p role="status" className="ok-text">{message}</p>}
    <button type="button" className="btn" disabled={save.isPending} onClick={() => save.mutate()}>{save.isPending ? t("mechanic_saving") : t("mechanic_sim_save_links")}</button>
  </section>;
}
