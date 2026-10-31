import { useAuth } from "../auth.jsx";

export default function StopDriving({ message }) {
  const { t } = useAuth();
  return <main className="stop-driving" role="alert" aria-labelledby="stop-driving-title">
    <div className="stop-driving-content">
      <p className="stop-eyebrow">{t("stop_urgent")}</p>
      <h1 id="stop-driving-title">{t("stop_title")}</h1>
      {message && <p className="stop-api-message">{message}</p>}
      <ol>
        <li>{t("stop_step_pull_over")}</li>
        <li>{t("stop_step_engine_off")}</li>
        <li>{t("stop_step_do_not_drive")}</li>
        <li>{t("stop_step_tow")}</li>
      </ol>
      <p className="stop-tow-note">{t("stop_tow_note")}</p>
      <button type="button" className="stop-call" disabled aria-describedby="stop-call-note">{t("stop_call_button")}</button>
      <p id="stop-call-note" className="stop-call-note">{t("stop_call_note")}</p>
    </div>
  </main>;
}
