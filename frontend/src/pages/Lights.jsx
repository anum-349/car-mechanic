import { useState } from "react";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Empty, ErrorBox, Field, Spinner, useLoad } from "../components/ui.jsx";

const SEV = {
  stop_now: { label: "Stop now", cls: "bad" },
  repair_soon: { label: "Repair soon", cls: "warn" },
  info: { label: "For information", cls: "info" },
};

function WarningLights() {
  const list = useLoad(() => api("/knowledge/warning-lights/").then((d) => d.results));
  if (list.loading) return <Spinner />;
  if (list.error) return <ErrorBox>{list.error}</ErrorBox>;
  if (!list?.data?.length) return <Empty>No warning lights have been added yet.</Empty>;
  return (
    <div>
      {list.data.map((w) => (
        <article key={w.id} className={`panel light ${SEV[w.severity]?.cls}`}>
          <h2>{w.name}</h2>
          <span className={`chip ${SEV[w.severity]?.cls}`}>{SEV[w.severity]?.label || w.severity}</span>
          <p>{w.meaning}</p>
          <p><strong>What to do:</strong> {w.recommended_action}</p>
        </article>
      ))}
    </div>
  );
}

function ObdLookup() {
  const [q, setQ] = useState("");
  const list = useLoad(() => api(`/knowledge/obd-codes/?search=${encodeURIComponent(q)}`).then((d) => d.results), [q]);
  return (
    <>
      <Field label="Code or description" hint="For example P0301. A mechanic's scanner shows these codes.">
        <input type="search" value={q} onChange={(e) => setQ(e.target.value)} />
      </Field>
      {list.loading && <Spinner />}
      <ErrorBox>{list.error}</ErrorBox>
      {list.data?.length === 0 && <Empty>No code matches that search.</Empty>}
      <ul className="list">
        {(list.data || []).map((c) => (
          <li key={c.code} className="list-row stack-tight">
            <strong>{c.code}</strong>
            <span>{c.description}</span>
            {c.system && <span className="muted small">{c.system}</span>}
          </li>
        ))}
      </ul>
    </>
  );
}

export default function Lights() {
  const { t } = useAuth();
  const [tab, setTab] = useState("lights");
  return (
    <>
      <h1>{t("nav_lights")}</h1>
      <div className="seg wide" role="tablist">
        <button role="tab" aria-selected={tab === "lights"} className={tab === "lights" ? "on" : ""} onClick={() => setTab("lights")}>Dashboard lights</button>
        <button role="tab" aria-selected={tab === "obd"} className={tab === "obd" ? "on" : ""} onClick={() => setTab("obd")}>Scanner codes</button>
      </div>
      {tab === "lights" ? <WarningLights /> : <ObdLookup />}
    </>
  );
}
