import { useAuth } from "../auth.jsx";

export default function SelfCheckList({ checks = [] }) {
  const { t } = useAuth();
  return <details className="self-check-list">
    <summary>{t("result_self_check")}</summary>
    {checks.length ? <ol>{checks.map((check, index) => <li key={`${check.steps}-${index}`}>
      <p className="steps">{check.steps}</p>
      <p className="muted small">{t("result_difficulty", { difficulty: check.difficulty })}</p>
      {check.tools_needed && <p className="muted small">{t("result_tools", { tools: check.tools_needed })}</p>}
    </li>)}</ol> : <p>{t("result_no_self_check")}</p>}
  </details>;
}
