import { useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { getAll } from "../api.js";
import { useAuth } from "../auth.jsx";
import { Empty, ErrorBox, Spinner } from "../components/ui.jsx";
import { readOfflineCache, writeOfflineCache } from "../utils/offlineCache.js";
import { FaBan, FaExclamationTriangle, FaInfoCircle } from "react-icons/fa";

const SEVERITIES = ["all", "stop_now", "repair_soon", "info"];
const SEVERITY_META = {
  stop_now: { label: "lights_stop", Icon: FaBan, cls: "text-red-500" },
  repair_soon: { label: "lights_repair", Icon: FaExclamationTriangle, cls: "text-yellow-500" },
  info: { label: "lights_info", Icon: FaInfoCircle, cls: "text-green-500" },
};

export function WarningLightSheet({ light, onClose }) {
  const { t, lang } = useAuth();
  useEffect(() => {
    if (!light) return undefined;
    const closeOnEscape = (event) => { if (event.key === "Escape") onClose(); };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [light, onClose]);

  if (!light) return null;
  const meta = SEVERITY_META[light.severity] || SEVERITY_META.info;
  const roman = lang === "roman_ur";
  return createPortal(<div className="light-sheet-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section className="bottom-sheet" role="dialog" aria-modal="true" aria-labelledby="light-sheet-title">
      <button className="sheet-close" type="button" onClick={onClose} aria-label={t("lights_close")}>×</button>
      <div className="light-sheet-icon">{light.icon_url ? <img src={light.icon_url} alt="" /> : null}</div>
      <h2 id="light-sheet-title">{light.name}</h2>
      <p className={`severity-badge ${meta.cls}`}><span aria-hidden="true">{meta.icon}</span> {t(meta.label)}</p>
      <h3>{t("lights_meaning")}</h3><p>{roman && light.meaning_roman ? light.meaning_roman : light.meaning}</p>
      <h3>{t("lights_action")}</h3><p>{roman && light.action_roman ? light.action_roman : light.recommended_action}</p>
      {light.severity === "stop_now" && <Link className="btn danger-option" to="/stop-driving">{t("lights_stop_advice")}</Link>}
    </section>
  </div>, document.body)
}

export default function WarningLights() {
  const { t } = useAuth();
  const [query, setQuery] = useState("");
  const [severity, setSeverity] = useState("all");
  const [selected, setSelected] = useState(null);
  const closeSheet = useCallback(() => { setSelected(null); }, []);
  const cached = readOfflineCache("warning-lights");
  const lightsQuery = useQuery({
    queryKey: ["warning-lights"],
    queryFn: async () => {
      const data = await getAll("/warning-lights/");
      const result = { items: data, draft: data.some((item) => item.is_dummy || item.status === "ai_draft") };
      writeOfflineCache("warning-lights", result);
      return result;
    },
    initialData: cached,
    staleTime: cached ? 0 : 60_000,
    retry: false,
  });
  const visible = useMemo(() => (lightsQuery.data?.items || []).filter((light) => {
    const needle = query.trim().toLocaleLowerCase();
    const text = [light.name, light.meaning, light.meaning_roman].join(" ").toLocaleLowerCase();
    return (!needle || text.includes(needle)) && (severity === "all" || light.severity === severity);
  }), [lightsQuery.data, query, severity]);
  if (lightsQuery.isLoading) return <Spinner />;
  if (!lightsQuery.data && lightsQuery.isError) return <><ErrorBox>{t("lights_load_error")}</ErrorBox><button className="btn" onClick={() => lightsQuery.refetch()}>{t("retry")}</button></>;
  return <div className="stack">
    <h1>{t("nav_lights")}</h1>
    {lightsQuery.isError && <p className="offline-note" role="status">{t("offline_cached")}</p>}
    <label className="field"><span>{t("lights_search")}</span><input type="search" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
    <div className="filter-chips" role="group" aria-label={t("lights_filter")}>
      {SEVERITIES.map((value) => <button key={value} className={`chip ${severity === value ? "on" : ""}`} aria-pressed={severity === value} onClick={() => setSeverity(value)}>{t(value === "all" ? "lights_all" : SEVERITY_META[value].label)}</button>)}
    </div>
    {!visible.length ? (
      <Empty>{t("lights_empty")}</Empty>
    ) : (
      <div className="warning-light-grid grid-cols-3 md:grid-cols-4">
        {visible.map((light) => {
          const meta = SEVERITY_META[light.severity] || SEVERITY_META.info;
          const { Icon, cls, label } = meta;

          return (
            <button
  className="warning-light-tile grid grid-rows-3 text-center self-center"
  key={light.id}
  onClick={() => setSelected(light)}
>
  <span className="warning-light-icon self-center">
    {light.icon_url ? (
      <img src={light.icon_url} alt="" loading="lazy" />
    ) : null}
  </span>
  <strong className="self-center">{light.name}</strong>
  <span className={`flex items-center justify-center gap-2 ${cls}`}>
    <Icon size={18} aria-hidden="true" />
    <span>{t(label)}</span>
  </span>
</button>
          );
        })}
      </div>
    )}
    <WarningLightSheet light={selected} onClose={closeSheet} />
  </div>;
}