import { useState } from "react";
import { useAuth } from "../auth.jsx";
import ConfidenceBar from "./ConfidenceBar.jsx";
import CostRange from "./CostRange.jsx";
import MechanicScript from "./MechanicScript.jsx";
import SelfCheckList from "./SelfCheckList.jsx";

export default function CauseCard({ cause, mechanicScript }) {
  const { t } = useAuth();
  const [scriptOpen, setScriptOpen] = useState(false);
  const why = cause.why || {};
  const supporting = (why.supporting || []).map((item) => item.answer || item.symptom).filter(Boolean);
  const contradicting = (why.contradicting || []).map((item) => item.answer || item.symptom).filter(Boolean);
  const missing = why.missing || [];
  return <article className="cause-card panel">
    <div className="cause-title"><span className="rank">{cause.rank}</span><div><h2>{cause.cause_name}</h2><ConfidenceBar confidence={cause.confidence} band={cause.band} /></div></div>
    {supporting.length > 0
      ? <p className="cause-why">{t("result_supporting_evidence", { symptoms: supporting.join("; ") })}</p>
      : <p className="cause-why">{cause.explanation || t("result_why_unknown")}</p>}
    {contradicting.length > 0 && <p className="muted">{t("result_conflicting_evidence", { symptoms: contradicting.join("; ") })}</p>}
    {missing.length > 0 && <p className="muted">{t("result_missing_information", { symptoms: missing.join("; ") })}</p>}
    <SelfCheckList checks={cause.self_checks || []} />
    <CostRange cost={cause.cost} />
    <button className="link-btn" type="button" aria-expanded={scriptOpen} onClick={() => setScriptOpen((open) => !open)}>{t("result_mechanic_script_title")}</button>
    {scriptOpen && <MechanicScript text={cause.ask_your_mechanic || mechanicScript} />}
  </article>;
}
