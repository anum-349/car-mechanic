import { useAuth } from "../../auth.jsx";
import { STRENGTHS } from "./wizardModel.js";

export default function StrengthSelector({ value, onChange, name }) {
  const { t } = useAuth();
  return (
    <div className="mechanic-strength" role="group" aria-label={name}>
      {STRENGTHS.map((strength) => (
        <button key={strength.value} type="button" className={`btn ghost${value === strength.value ? " on" : ""}`}
          aria-pressed={value === strength.value} onClick={() => onChange(strength.value)}>
          {t(strength.key)}
        </button>
      ))}
    </div>
  );
}
