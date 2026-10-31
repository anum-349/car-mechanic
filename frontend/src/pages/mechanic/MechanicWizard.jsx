import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, getAll } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import { Empty, ErrorBox, Field, Spinner } from "../../components/ui.jsx";
import StrengthSelector from "./StrengthSelector.jsx";
import { buildFlowPayload, newFlow, readDraft, validateStep, WIZARD_STEPS, writeDraft } from "./wizardModel.js";

function extractFieldErrors(error) {
  const payload = error?.data?.flow;
  const messages = Array.isArray(payload) ? payload : payload ? [payload] : [];
  const parsed = {};
  for (const message of messages) {
    const text = String(message);
    const symptom = text.match(/symptoms\[(\d+)\]\.([a-z_]+)/i);
    if (symptom) {
      const field = symptom[2].includes("roman") ? "roman" : "en";
      parsed[`symptom_${symptom[1]}_${field}`] = text;
    } else if (/car_models/i.test(text)) parsed.car_models = text;
    else if (/category/i.test(text)) parsed.name_en = text;
    else if (/cost|parts_min|labour_min/i.test(text)) parsed.costs = text;
    else if (/causes/i.test(text)) parsed.causes = text;
  }
  return parsed;
}

export default function MechanicWizard() {
  const { t, user, pick } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const flowId = params.get("flow");
  const localDraft = readDraft(user?.id);
  const matchesDraft = !params.get("flow") || String(localDraft?.flowId) === params.get("flow");
  const [step, setStep] = useState(() => Math.max(1, Math.min(WIZARD_STEPS, Number(params.get("step") || (matchesDraft && localDraft?.step) || 1))));
  const [flow, setFlow] = useState(() => matchesDraft && localDraft?.flow ? localDraft.flow : newFlow());
  const [errors, setErrors] = useState({});
  const [removingItem, setRemovingItem] = useState("");
  const [submitMessage, setSubmitMessage] = useState("");
  const [flowResponse, setFlowResponse] = useState(null);
  const options = useQuery({
    queryKey: ["mechanic-wizard-options"],
    queryFn: async () => {
      const [models, makes, categories] = await Promise.all([getAll("/garage/models/"), getAll("/garage/makes/"), getAll("/categories/")]);
      return { models, makes, categories };
    },
  });
  useEffect(() => { writeDraft(user?.id, { flow, flowId: flowId ? Number(flowId) : null, step }); }, [user?.id, flow, flowId, step]);

  const save = useMutation({
    mutationFn: (payload) => api(flowId ? `/mechanic/flows/${flowId}/` : "/mechanic/flows/", { method: flowId ? "PATCH" : "POST", body: payload }),
    onSuccess: (data) => {
      setFlowResponse(data);
      if (!flowId && data.id) navigate(`/mechanic/wizard?flow=${data.id}&step=${step}`, { replace: true });
      queryClient.invalidateQueries({ queryKey: ["mechanic-dashboard"] });
    },
    onError: (error) => setErrors((current) => ({ ...current, ...extractFieldErrors(error), server: error.message })),
  });
  const categories = options.data?.categories || [];
  const makes = useMemo(() => options.data?.makes || [], [options.data?.makes]);
  const update = (callback) => setFlow((current) => callback(structuredClone(current)));
  const setField = (key, value) => update((next) => { next[key] = value; return next; });
  const fieldError = (key) => errors[key] && <p className="field-error" role="alert">{errors[key] === "required" || errors[key] === "invalid" ? t("mechanic_required") : errors[key]}</p>;

  async function nextStep() {
    const validation = validateStep(step, flow);
    setErrors(validation);
    if (Object.keys(validation).length) return;
    if (flow.category.name_en.trim()) {
      try { await save.mutateAsync(buildFlowPayload(flow)); }
      catch { return; }
    }
    setStep((current) => Math.min(WIZARD_STEPS, current + 1));
    window.scrollTo?.(0, 0);
  }
  function previousStep() { setErrors({}); setStep((current) => Math.max(1, current - 1)); }
  function chooseCategory(id) {
    const category = categories.find((item) => String(item.id) === String(id));
    update((next) => { next.category = { name_en: category?.name_en || "", name_roman: category?.name_roman || "" }; return next; });
  }
  function addSymptom() { update((next) => { next.symptoms.push({ key: `symptom_${Date.now()}`, en: "", roman: "", safety: false, safety_explanation: "" }); return next; }); }
  function updateSymptom(index, key, value) { update((next) => { next.symptoms[index][key] = value; return next; }); }
  function addCause() { update((next) => { next.causes.push({ key: `cause_${Date.now()}`, name: "", system: "general", commonness: "medium", links: {}, self_check: { steps: "", tools_needed: "", difficulty: "easy" }, costs: [] }); return next; }); }
  function updateCause(index, key, value) { update((next) => { next.causes[index][key] = value; return next; }); }
  async function removeSymptom(index) {
    const symptom = flow.symptoms[index];
    setRemovingItem(symptom.key);
    setErrors((current) => ({ ...current, server: "" }));
    try {
      const currentResponse = flowResponse || (flowId ? await api(`/mechanic/flows/${flowId}/`) : null);
      const saved = currentResponse?.symptoms?.find((item) => item.key === symptom.key);
      if (saved?.id) {
        await api(`/mechanic/items/symptoms/${saved.id}/`, { method: "DELETE" });
      }
      update((next) => {
        next.symptoms = next.symptoms.filter((item) => item.key !== symptom.key);
        next.causes.forEach((cause) => { delete cause.links?.[symptom.key]; });
        return next;
      });
      setErrors({});
    } catch (error) {
      setErrors((current) => ({ ...current, server: error.message }));
    } finally {
      setRemovingItem("");
    }
  }
  async function removeCause(index) {
    const cause = flow.causes[index];
    setRemovingItem(cause.key);
    setErrors((current) => ({ ...current, server: "" }));
    try {
      const currentResponse = flowResponse || (flowId ? await api(`/mechanic/flows/${flowId}/`) : null);
      const saved = currentResponse?.causes?.find((item) => item.name === cause.name);
      if (saved?.id) {
        await api(`/mechanic/items/causes/${saved.id}/`, { method: "DELETE" });
      }
      update((next) => {
        next.causes = next.causes.filter((item) => item.key !== cause.key);
        return next;
      });
      setErrors({});
    } catch (error) {
      setErrors((current) => ({ ...current, server: error.message }));
    } finally {
      setRemovingItem("");
    }
  }
  function updateSelfCheck(index, key, value) { update((next) => { next.causes[index].self_check[key] = value; return next; }); }
  function updateLink(causeIndex, symptomKey, value) { update((next) => { next.causes[causeIndex].links[symptomKey] = value; return next; }); }
  function updateCost(causeIndex, costIndex, key, value) { update((next) => { next.causes[causeIndex].costs[costIndex][key] = value; return next; }); }
  function addCost(causeIndex) { update((next) => { next.causes[causeIndex].costs.push({ city: "", parts_min: "", parts_max: "", labour_min: "", labour_max: "", last_verified: "" }); return next; }); }

  async function submitFlow() {
    const validation = [1, 2, 3, 4, 5, 6].flatMap((n) => Object.keys(validateStep(n, flow)));
    if (validation.length) { setErrors({ final: t("mechanic_complete_steps") }); setStep(1); return; }
    try {
      const data = await api(flowId ? `/mechanic/flows/${flowId}/` : "/mechanic/flows/", { method: flowId ? "PATCH" : "POST", body: buildFlowPayload(flow) });
      setFlowResponse(data);
      const requests = [
        ...(data.symptoms || []).map((item) => api(`/mechanic/items/symptoms/${item.id}/submit/`, { method: "POST", body: {} })),
        ...(data.causes || []).map((item) => api(`/mechanic/items/causes/${item.id}/submit/`, { method: "POST", body: {} })),
      ];
      await Promise.all(requests);
      writeDraft(user?.id, { flow, flowId: data.id, step: WIZARD_STEPS, submitted: true });
      setSubmitMessage(t("mechanic_submit_success"));
      queryClient.invalidateQueries({ queryKey: ["mechanic-dashboard"] });
    } catch (error) { setErrors({ final: error.message }); }
  }

  if (options.isLoading) return <Spinner />;
  if (options.isError) return <div><ErrorBox>{options.error?.message}</ErrorBox><button className="btn" onClick={() => options.refetch()}>{t("retry")}</button></div>;
  if (!options.data?.models?.length) return <Empty action={<Link to="/mechanic">{t("mechanic_dashboard_title")}</Link>}>{t("mechanic_models_missing")}</Empty>;

  return <main className="mechanic-area">
    <Link to="/mechanic">← {t("mechanic_dashboard_title")}</Link>
    <h1>{t("mechanic_wizard_title")}</h1>
    <p>{t("mechanic_step", { current: step, total: WIZARD_STEPS })}</p>
    <progress className="mechanic-wizard-progress" max={WIZARD_STEPS} value={step}>{step}/{WIZARD_STEPS}</progress>
    <section className="panel mechanic-step" aria-labelledby="step-title">
      <h2 id="step-title">{t(`mechanic_step_${step}_title`)}</h2>
      {step === 1 && <>
        <Field label={t("mechanic_problem")}>
          <select value={categories.find((c) => c.name_en === flow.category.name_en)?.id || ""} onChange={(event) => chooseCategory(event.target.value)}>
            <option value="">{t("mechanic_choose_problem")}</option>{categories.map((category) => <option key={category.id} value={category.id}>{pick(category, "name")}</option>)}
          </select>
        </Field>
        {fieldError("name_en")}
        <fieldset className="mechanic-models"><legend>{t("mechanic_car_models")}</legend>{makes.map((make) => <section key={make.id}><h3>{make.name}</h3>{options.data.models.filter((model) => String(model.car_make) === String(make.id)).map((model) => <label className="mechanic-check" key={model.id}><input type="checkbox" checked={flow.car_models.includes(`${make.name} ${model.name}`)} onChange={(event) => setField("car_models", event.target.checked ? [...flow.car_models, `${make.name} ${model.name}`] : flow.car_models.filter((v) => v !== `${make.name} ${model.name}`))} />{model.name}</label>)}</section>)}</fieldset>
        {fieldError("car_models")}
      </>}
      {step === 2 && <>
        {flow.symptoms.map((symptom, i) => <article className="mechanic-editor" key={symptom.key}>
          <div className="row spread"><h3>{t("mechanic_symptom_heading", { number: i + 1 })}</h3><button type="button" className="btn ghost" disabled={Boolean(removingItem)} onClick={() => removeSymptom(i)}>{removingItem === symptom.key ? t("mechanic_removing") : t("mechanic_remove_symptom")}</button></div>
          <Field label={t("mechanic_symptom_en")}><textarea rows={2} value={symptom.en} onChange={(e) => updateSymptom(i, "en", e.target.value)} /></Field>{fieldError(`symptom_${i}_en`)}
          <Field label={t("mechanic_symptom_roman")}><textarea rows={2} value={symptom.roman} onChange={(e) => updateSymptom(i, "roman", e.target.value)} /></Field>{fieldError(`symptom_${i}_roman`)}
          <label className="mechanic-check"><input type="checkbox" checked={symptom.safety} onChange={(e) => updateSymptom(i, "safety", e.target.checked)} />{t("mechanic_safety_critical")}</label>
          {symptom.safety && <><Field label={t("mechanic_safety_explanation")}><textarea rows={2} value={symptom.safety_explanation} onChange={(e) => updateSymptom(i, "safety_explanation", e.target.value)} /></Field>{fieldError(`symptom_${i}_safety`)}</>}
        </article>)}
        {errors.symptoms && <p className="error">{t("mechanic_add_one_symptom")}</p>}<button type="button" className="btn ghost" onClick={addSymptom}>{t("mechanic_add_symptom")}</button>
        {import.meta.env.VITE_MECHANIC_VOICE_NOTES === "true" && <VoiceNote onError={(message) => setErrors((current) => ({ ...current, voice: message }))} />}{errors.voice && <ErrorBox>{errors.voice}</ErrorBox>}
      </>}
      {step === 3 && <>
        {flow.causes.map((cause, i) => <article className="mechanic-editor" key={cause.key}>
          <div className="row spread"><h3>{cause.name || t("mechanic_cause_name")}</h3><button type="button" className="btn ghost" disabled={Boolean(removingItem)} onClick={() => removeCause(i)}>{removingItem === cause.key ? t("mechanic_removing") : t("mechanic_remove_cause")}</button></div>
          <Field label={t("mechanic_cause_name")}><input value={cause.name} onChange={(e) => updateCause(i, "name", e.target.value)} /></Field>
          <Field label={t("mechanic_system")}><input value={cause.system} onChange={(e) => updateCause(i, "system", e.target.value)} /></Field>
          <Field label={t("mechanic_commonness")} hint={t("mechanic_commonness_hint")}><select value={cause.commonness} onChange={(e) => updateCause(i, "commonness", e.target.value)}><option value="high">{t("mechanic_high")}</option><option value="medium">{t("mechanic_medium")}</option><option value="low">{t("mechanic_low")}</option></select></Field>
        </article>)}
        {errors.causes && <p className="error">{errors.causes === "required" ? t("mechanic_add_one_cause") : errors.causes}</p>}<button type="button" className="btn ghost" onClick={addCause}>{t("mechanic_add_cause")}</button>
      </>}
      {step === 4 && <>
        {flow.causes.map((cause, i) => <article className="mechanic-editor" key={cause.key}><h3>{cause.name || t("mechanic_cause_name")}</h3>
          {flow.symptoms.map((symptom) => <div className="mechanic-link-row" key={symptom.key}><strong>{symptom.en || symptom.key}</strong><StrengthSelector name={t("mechanic_link_strength")} value={cause.links?.[symptom.key]} onChange={(value) => updateLink(i, symptom.key, value)} /></div>)}
        </article>)}
        {errors.links && <p className="error">{t("mechanic_choose_all_strengths")}</p>}
      </>}
      {step === 5 && flow.causes.map((cause, i) => <article className="mechanic-editor" key={cause.key}><h3>{cause.name}</h3>
        <Field label={t("mechanic_check_steps")}><textarea rows={4} value={cause.self_check?.steps || ""} onChange={(e) => updateSelfCheck(i, "steps", e.target.value)} /></Field>
        <Field label={t("mechanic_tools")}><input value={cause.self_check?.tools_needed || ""} onChange={(e) => updateSelfCheck(i, "tools_needed", e.target.value)} /></Field>
        <Field label={t("mechanic_difficulty")}><select value={cause.self_check?.difficulty || "easy"} onChange={(e) => updateSelfCheck(i, "difficulty", e.target.value)}><option value="easy">{t("mechanic_easy")}</option><option value="medium">{t("mechanic_medium")}</option><option value="hard">{t("mechanic_hard")}</option></select></Field>
        {errors.self_checks && !cause.self_check?.steps?.trim() && <p className="error">{t("mechanic_required")}</p>}
      </article>)}
      {step === 6 && <>{flow.causes.map((cause, ci) => <article className="mechanic-editor" key={cause.key}><h3>{cause.name}</h3>
        {(cause.costs || []).map((cost, i) => <div className="mechanic-cost" key={i}>
          <Field label={t("mechanic_city")}><select value={cost.city} onChange={(e) => updateCost(ci, i, "city", e.target.value)}><option value="">{t("mechanic_choose_city")}</option>{["Lahore", "Karachi", "Islamabad", "Rawalpindi", "Other"].map((city) => <option key={city}>{city}</option>)}</select></Field>
          <div className="mechanic-cost-grid"><Field label={t("mechanic_parts_min")}><input type="number" min="0" value={cost.parts_min} onChange={(e) => updateCost(ci, i, "parts_min", e.target.value)} /></Field><Field label={t("mechanic_parts_max")}><input type="number" min="0" value={cost.parts_max} onChange={(e) => updateCost(ci, i, "parts_max", e.target.value)} /></Field><Field label={t("mechanic_labour_min")}><input type="number" min="0" value={cost.labour_min} onChange={(e) => updateCost(ci, i, "labour_min", e.target.value)} /></Field><Field label={t("mechanic_labour_max")}><input type="number" min="0" value={cost.labour_max} onChange={(e) => updateCost(ci, i, "labour_max", e.target.value)} /></Field></div>
          <Field label={t("mechanic_last_verified")}><input type="date" value={cost.last_verified || ""} onChange={(e) => updateCost(ci, i, "last_verified", e.target.value)} /></Field>
        </div>)}<button type="button" className="btn ghost" onClick={() => addCost(ci)}>{t("mechanic_add_cost")}</button>
        {errors.costs && <p className="error">{errors.costs === "invalid" ? t("mechanic_cost_bounds") : errors.costs}</p>}
      </article>)}</>}
      {step === 7 && <>
        <p>{t("mechanic_red_flags_help")}</p>
        {(flow.red_flags || []).map((flag, i) => <Field key={i} label={t("mechanic_red_flag")}><textarea rows={2} value={flag} onChange={(e) => setField("red_flags", flow.red_flags.map((item, n) => n === i ? e.target.value : item))} /></Field>)}
        <button type="button" className="btn ghost" onClick={() => setField("red_flags", [...(flow.red_flags || []), ""])}>{t("mechanic_add_red_flag")}</button>
        <p className="muted small">{t("mechanic_red_flags_local_note")}</p>
      </>}
      {step === 8 && <>
        <h3>{flow.category.name_en}</h3><p>{t("mechanic_review_models", { models: flow.car_models.join(", ") })}</p>
        <h3>{t("mechanic_symptoms_title")}</h3><ul>{flow.symptoms.map((s) => <li key={s.key}>{s.en} / {s.roman}{s.safety ? ` — ${t("mechanic_safety_critical")}` : ""}</li>)}</ul>
        <h3>{t("mechanic_causes_title")}</h3><ul>{flow.causes.map((c) => <li key={c.key}>{c.name} ({t(`mechanic_${c.commonness}`)})</li>)}</ul>
        <p>{t("mechanic_review_note")}</p>
        <Link className="btn ghost" to="/mechanic/simulator">{t("mechanic_test_simulator")}</Link>
        {(flowResponse?.id || flowId) && <p className="muted small">{t("mechanic_draft_saved")}</p>}
        {submitMessage && <p className="ok-text" role="status">{submitMessage}</p>}
      </>}
      {errors.server && <ErrorBox>{errors.server}</ErrorBox>}{errors.final && <ErrorBox>{errors.final}</ErrorBox>}
      <div className="row mechanic-wizard-actions">
        {step > 1 && <button type="button" className="btn ghost" onClick={previousStep}>{t("mechanic_back")}</button>}
        {step < WIZARD_STEPS ? <button type="button" className="btn" disabled={save.isPending} onClick={nextStep}>{save.isPending ? t("mechanic_saving") : t("mechanic_next")}</button> : <button type="button" className="btn" disabled={Boolean(submitMessage)} onClick={submitFlow}>{t("mechanic_submit_review")}</button>}
      </div>
      {save.isPending && <p role="status" className="muted">{t("mechanic_saving")}</p>}
    </section>
  </main>;
}

function VoiceNote({ onError }) {
  const { t } = useAuth();
  const [recorder, setRecorder] = useState(null);
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  async function toggle() {
    if (recording) { recorder?.stop(); setRecording(false); return; }
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) { onError(t("mechanic_voice_unsupported")); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream);
      const chunks = [];
      mediaRecorder.ondataavailable = (event) => chunks.push(event.data);
      mediaRecorder.onstop = async () => {
        setBusy(true);
        const form = new FormData(); form.append("audio", new Blob(chunks, { type: mediaRecorder.mimeType || "audio/webm" }), "mechanic-note.webm");
        try { await api("/mechanic/voice-notes/", { method: "POST", body: form }); }
        catch (error) { onError(error.message); }
        finally { setBusy(false); stream.getTracks().forEach((track) => track.stop()); }
      };
      mediaRecorder.start(); setRecorder(mediaRecorder); setRecording(true);
    } catch (error) { onError(error.message || t("mechanic_voice_denied")); }
  }
  return <div className="mechanic-voice"><button type="button" className="btn ghost" disabled={busy} onClick={toggle}>{busy ? t("mechanic_voice_uploading") : recording ? t("mechanic_voice_stop") : t("mechanic_voice_record")}</button><span className="muted small">{t("mechanic_voice_stub")}</span></div>;
}
