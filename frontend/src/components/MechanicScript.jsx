import { useState } from "react";
import { useAuth } from "../auth.jsx";

export default function MechanicScript({ text }) {
  const { t } = useAuth();
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text || "");
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }
  return <section className="mechanic-script panel">
    <div className="row spread"><h3>{t("result_mechanic_script_title")}</h3><button className="btn ghost" type="button" onClick={copy}>{copied ? t("result_copied") : t("result_copy")}</button></div>
    <p>{text}</p>
  </section>;
}
