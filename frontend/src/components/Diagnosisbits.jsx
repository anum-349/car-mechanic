// src/components/DiagnosisBits.jsx
// Small pieces shared by NewDiagnosis and DiagnosisChat.
import { useAuth } from "../auth.jsx";

export function Skeleton({ rows = 3 }) {
  const { t } = useAuth();
  return (
    <div className="skeleton-stack" role="status" aria-label={t("loading")}>
      {Array.from({ length: rows }, (_, index) => (
        <span className="skeleton" key={index} />
      ))}
    </div>
  );
}

// `context` = { code, description, system? } from /obd/<code>/ or session.obd_context
export function ObdPanel({ context }) {
  const { t } = useAuth();
  if (!context) return null;
  return (
    <section className="panel" aria-label={t("obd_system")}>
      <h2>{context.code}</h2>
      <p>{context.description}</p>
      {context.system && (
        <p>
          <strong>{t("obd_system")}:</strong> {context.system}
        </p>
      )}
    </section>
  );
}