import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useAuth } from "../auth.jsx";
import { DraftBanner } from "./Result.jsx";
import { ErrorBox, Field, Spinner } from "../components/ui.jsx";
import { readOfflineCache, writeOfflineCache } from "../utils/offlineCache.js";
import { normalizeObdCode } from "../utils/obdCode.js";

export default function ObdLookup() {
  const { t } = useAuth();
  const [input, setInput] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [validationError, setValidationError] = useState(false);
  const cached = submitted ? readOfflineCache(`obd:${submitted}`) : undefined;
  const result = useQuery({
    queryKey: ["obd-code", submitted],
    queryFn: async () => {
      const data = await api(`/obd/${encodeURIComponent(submitted)}/`);
      writeOfflineCache(`obd:${submitted}`, data);
      return data;
    },
    enabled: Boolean(submitted),
    initialData: cached,
    staleTime: cached ? 0 : 60_000,
    retry: false,
  });
  const submit = (event) => {
    event.preventDefault();
    const normalized = normalizeObdCode(input);
    if (!normalized) { setValidationError(true); setSubmitted(""); return; }
    setValidationError(false);
    setSubmitted(normalized);
  };
  const codeNotFound = result.isError && result.error?.status === 404;
  return <div className="stack">
    <h1>{t("page_obd")}</h1>
    <p>{t("obd_intro")}</p>
    {result.data?.draft_content && <DraftBanner />}
    {result.isError && result.data && <p className="offline-note" role="status">{t("offline_cached")}</p>}
    <form onSubmit={submit} noValidate>
      <Field label={t("obd_search_label")} hint={t("obd_search_hint")}>
        <input type="search" value={input} onChange={(event) => setInput(event.target.value)} autoCapitalize="characters" aria-invalid={validationError} />
      </Field>
      {validationError && <p className="field-error" role="alert">{t("obd_invalid")}</p>}
      <button className="btn" type="submit">{t("obd_search")}</button>
    </form>
    {result.isFetching && <Spinner />}
    {result.isError && !result.data && <>
      {codeNotFound ? <p className="panel" role="status">{t("obd_not_found")}</p> : <ErrorBox>{t("obd_load_error")}</ErrorBox>}
      {!codeNotFound && <button className="btn ghost" onClick={() => result.refetch()}>{t("retry")}</button>}
    </>}
    {result.data && <article className="panel obd-result">
      <h2>{result.data.code}</h2><p>{result.data.description}</p>
      {result.data.system && <p><strong>{t("obd_system")}:</strong> {result.data.system}</p>}
      <h3>{t("obd_causes")}</h3>
      {result.data.likely_causes?.length ? <ul>{result.data.likely_causes.map((cause, index) => <li key={`${cause.name}-${index}`}>{cause.name}</li>)}</ul> : <p>{t("obd_causes_empty")}</p>}
      <Link className="btn" to={`/diagnose?obd=${encodeURIComponent(result.data.code)}`}>{t("obd_start_diagnosis")}</Link>
    </article>}
  </div>;
}
