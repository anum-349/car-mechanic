export const WIZARD_STEPS = 9;

export const STRENGTHS = [
  { value: "always", key: "mechanic_strength_always" },
  { value: "often", key: "mechanic_strength_often" },
  { value: "sometimes", key: "mechanic_strength_sometimes" },
  { value: "rarely", key: "mechanic_strength_rarely" },
];

export const PRIOR_BY_COMMONNESS = { high: 0.6, medium: 0.3, low: 0.1 };

export function newFlow() {
  return {
    category: { name_en: "", name_roman: "" }, car_models: [], symptoms: [],
    causes: [], questions: [], self_checks: [], red_flags: [],
  };
}

const uid = () => Math.random().toString(36).slice(2, 7);

/* A question tree: each answer points to another question ("q:<key>") or to a cause/result ("c:<key>"). */
export function newAnswer() {
  return { key: `answer_${Date.now()}_${uid()}`, en: "", roman: "", next: "", mechanic_note: "" };
}

export function newQuestion() {
  return { key: `question_${Date.now()}_${uid()}`, en: "", roman: "", answers: [newAnswer(), newAnswer()] };
}

const lines = (text) => String(text || "").split("\n").map((line) => line.trim()).filter(Boolean);

const storageKey = (userId) => `mechanic-flow-draft-${userId}`;

export function readDraft(userId) {
  try {
    const raw = localStorage.getItem(storageKey(userId));
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    return parsed?.flow ? parsed : null;
  } catch {
    return null;
  }
}

export function writeDraft(userId, draft) {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(draft));
    return true;
  } catch {
    return false;
  }
}

export function buildFlowPayload(flow) {
  const causes = flow.causes.map((cause) => ({
    key: cause.key,
    name: cause.name,
    system: cause.system || "general",
    prior: PRIOR_BY_COMMONNESS[cause.commonness] ?? PRIOR_BY_COMMONNESS.medium,
    severity: cause.severity || "medium",
    safe_to_drive: cause.safe_to_drive !== false,
    ask_mechanic: lines(cause.ask_mechanic),
    links: flow.symptoms.map((symptom) => ({
      symptom: symptom.key,
      strength: cause.links?.[symptom.key] || "sometimes",
    })),
    self_check: cause.self_check?.steps ? {
      en: cause.self_check.steps,
      tools_needed: cause.self_check.tools_needed || "",
      difficulty: cause.self_check.difficulty || "easy",
    } : undefined,
    costs: (cause.costs || []).map((cost) => ({
      city: cost.city,
      parts_min: Number(cost.parts_min || 0),
      parts_max: Number(cost.parts_max || 0),
      labour_min: Number(cost.labour_min || 0),
      labour_max: Number(cost.labour_max || 0),
      last_verified: cost.last_verified || null,
    })).filter((cost) => cost.city),
  }));
  const questions = (flow.questions || []).map((question, order) => ({
    key: question.key,
    order,
    en: question.en,
    roman: question.roman,
    answers: question.answers.map((answer) => ({
      key: answer.key,
      en: answer.en,
      roman: answer.roman,
      next_question: answer.next?.startsWith("q:") ? answer.next.slice(2) : null,
      next_cause: answer.next?.startsWith("c:") ? answer.next.slice(2) : null,
      mechanic_note: answer.mechanic_note || "",
    })),
  }));
  return {
    category: flow.category,
    car_models: flow.car_models,
    symptoms: flow.symptoms.map(({ key, en, roman, safety }) => ({ key, en, roman, safety })),
    causes,
    questions,
    red_flags: flow.red_flags.filter(Boolean),
  };
}

export function validateStep(step, flow) {
  const errors = {};
  if (step === 1) {
    if (!flow.car_models.length) errors.car_models = "required";
    if (!flow.category.name_en.trim()) errors.name_en = "required";
  }
  if (step === 2) {
    if (!flow.symptoms.length) errors.symptoms = "required";
    flow.symptoms.forEach((symptom, i) => {
      if (!symptom.en?.trim()) errors[`symptom_${i}_en`] = "required";
      if (!symptom.roman?.trim()) errors[`symptom_${i}_roman`] = "required";
      if (symptom.safety && !symptom.safety_explanation?.trim()) errors[`symptom_${i}_safety`] = "required";
    });
  }
  if (step === 3 && !flow.causes.length) errors.causes = "required";
  if (step === 4 && flow.causes.some((cause) => flow.symptoms.some((s) => !cause.links?.[s.key]))) errors.links = "required";
  if (step === 5 && flow.causes.some((cause) => !cause.self_check?.steps?.trim())) errors.self_checks = "required";
  if (step === 6 && flow.causes.some((cause) => !cause.costs?.length || cause.costs.some((c) => !c.city || Number(c.parts_min) > Number(c.parts_max) || Number(c.labour_min) > Number(c.labour_max)))) errors.costs = "invalid";
  if (step === 8) {
    const targets = new Set([...flow.questions.map((q) => `q:${q.key}`), ...flow.causes.map((c) => `c:${c.key}`)]);
    if (!flow.questions.length) errors.questions = "required";
    flow.questions.forEach((question, i) => {
      if (!question.en?.trim() || !question.roman?.trim()) errors[`question_${i}_text`] = "required";
      if ((question.answers || []).length < 2) errors[`question_${i}_answers`] = "required";
      (question.answers || []).forEach((answer, j) => {
        if (!answer.en?.trim() || !answer.roman?.trim()) errors[`question_${i}_answer_${j}_text`] = "required";
        if (!targets.has(answer.next)) errors[`question_${i}_answer_${j}_next`] = "required";
      });
    });
  }
  return errors;
}