import { Link } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../../api.js";
import { useAuth } from "../../auth.jsx";
import { Empty, ErrorBox, Field, Spinner } from "../../components/ui.jsx";
import { readDraft } from "./wizardModel.js";

function ContactDetailsForm({ profile, onSave }) {
  const { t } = useAuth();
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  async function submit(event) {
    event.preventDefault();
    setError("");
    setSaved(false);
    const form = new FormData(event.currentTarget);
    try {
      await onSave({
        address: String(form.get("address") || "").trim(),
        phone: String(form.get("phone") || "").trim(),
      });
      setSaved(true);
    } catch (saveError) {
      setError(saveError.message);
    }
  }

  return (
    <details className="border-t border-line pt-3 open:[&>summary]:mb-4">
      <summary className="cursor-pointer font-medium">{t("mechanic_contact_edit_title")}</summary>
      <form className="grid gap-3.5" onSubmit={submit}>
        <Field label={t("register_workshop_address")}>
          <textarea name="address" rows={2} maxLength={250} defaultValue={profile.address || ""} required />
        </Field>
        <Field label={t("phone")} hint={t("register_public_phone_help")}>
          <input name="phone" type="tel" maxLength={20} defaultValue={profile.phone || ""} required />
        </Field>
        <ErrorBox>{error}</ErrorBox>
        {saved && <p className="font-bold text-green" role="status">{t("mechanic_contact_saved")}</p>}
        <button className="btn">{t("mechanic_contact_save")}</button>
      </form>
    </details>
  );
}

function Stat({ label, value }) {
  return (
    <div className="grid gap-0.5 bg-panel px-4 py-3.5">
      <span className="text-2xl font-semibold tabular-nums">{value}</span>
      <span className="text-xs text-ink-soft">{label}</span>
    </div>
  );
}

export default function MechanicDashboard() {
  const { t, user } = useAuth();
  const queryClient = useQueryClient();
  const dashboard = useQuery({ queryKey: ["mechanic-dashboard"], queryFn: () => api("/mechanic/dashboard/") });
  const records = useQuery({ queryKey: ["mechanic-records", "dashboard"], queryFn: () => api("/mechanic/records/?page=1") });
  const profile = useQuery({ queryKey: ["mechanic-profile"], queryFn: () => api("/mechanic/profile/"), refetchInterval: 60000 });
  const draft = readDraft(user?.id);

  async function saveContactDetails(details) {
    const updated = await api("/mechanic/profile/", { method: "PATCH", body: details });
    queryClient.setQueryData(["mechanic-profile"], updated);
  }

  const wizardPath = draft?.flowId ? `/mechanic/wizard?flow=${draft.flowId}&step=${draft.step || 1}` : "/mechanic/wizard";
  const summary = records.data?.summary;

  return (
    <main className="mx-auto grid max-w-3xl gap-8">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="mb-2 text-2xl font-semibold tracking-tight">{t("mechanic_dashboard_title")}</h1>
          {profile.data && (
            <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${profile.data.is_verified ? "bg-green-bg text-green" : "bg-amber-bg text-amber"}`} role="status">
              {t(profile.data.is_verified ? "mechanic_verified_notice" : "mechanic_pending_notice")}
            </span>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Link className="btn ghost" to={wizardPath}>{draft ? t("mechanic_continue") : t("mechanic_new_flow")}</Link>
          <Link className="btn" to="/mechanic/record/new">{t("mechanic_record_new")}</Link>
        </div>
      </header>

      <section className="grid gap-4">
        <div className="flex items-baseline justify-between">
          <h2 className="m-0 font-body text-base font-semibold">{t("mechanic_records_title")}</h2>
          <Link className="text-sm" to="/mechanic/records">{t("mechanic_records_view_all")}</Link>
        </div>
        {records.isLoading && <Spinner />}
        {records.isError && <ErrorBox>{records.error.message}</ErrorBox>}
        {summary && (
          <>
            <div className="grid grid-cols-[repeat(auto-fit,minmax(120px,1fr))] gap-px overflow-hidden rounded-lg border border-line bg-line">
              <Stat label={t("mechanic_records_total")} value={summary.total} />
              <Stat label={t("mechanic_records_open")} value={summary.open} />
              <Stat label={t("mechanic_repairs_completed")} value={summary.repair_completed} />
              <Stat label={t("mechanic_outcome_drafts")} value={summary.outcome_drafts} />
            </div>
            {records.data.results.length ? (
              <ul className="m-0 list-none border-t border-line p-0">
                {records.data.results.slice(0, 5).map((item) => (
                  <li key={item.id} className="flex items-center justify-between gap-4 border-b border-line py-3">
                    <Link to={`/mechanic/records/${item.id}`}>
                      {item.car.label} — {item.diagnosis_type === "obd" ? item.obd_context?.code : item.free_text}
                    </Link>
                    <span className="chip">{t(`mechanic_record_status_${item.status}`)}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>{t("mechanic_records_empty")}</Empty>
            )}
          </>
        )}
      </section>

      {dashboard.isLoading && <Spinner />}
      {dashboard.isError && (
        <>
          <ErrorBox>{dashboard.error.message}</ErrorBox>
          <button className="btn ghost" onClick={() => dashboard.refetch()}>{t("retry")}</button>
        </>
      )}
      {dashboard.data && (
        <section className="grid gap-4">
          <h2 className="m-0 font-body text-base font-semibold">{t("mechanic_flow_progress")}</h2>
          {dashboard.data.flows.length ? (
            <ul className="m-0 list-none border-t border-line p-0">
              {dashboard.data.flows.map((flow) => (
                <li key={flow.id} className="grid grid-cols-[1fr_auto] items-center gap-4 border-b border-line py-3 sm:grid-cols-[1fr_minmax(80px,160px)_auto_auto]">
                  <span>{flow.name}</span>
                  <progress className="col-span-full h-1.5 w-full sm:col-span-1" max="100" value={flow.percentage} aria-label={flow.name} />
                  <span className="text-sm tabular-nums text-ink-soft">{flow.percentage}%</span>
                  {String(draft?.flowId) === String(flow.id) && (
                    <Link to={`/mechanic/wizard?flow=${flow.id}&step=${draft.step || 1}`}>{t("mechanic_continue_flow")}</Link>
                  )}
                </li>
              ))}
            </ul>
          ) : (
            <Empty>{t("mechanic_no_flows")}</Empty>
          )}

          <details className="border-t border-line pt-3 open:[&>summary]:mb-4">
            <summary className="cursor-pointer font-medium">{t("mechanic_my_items")}</summary>
            {dashboard.data.items.length ? (
              <ul className="m-0 list-none border-t border-line p-0">
                {dashboard.data.items.map((item) => (
                  <li key={`${item.type}-${item.id}`} className="flex items-center justify-between gap-4 border-b border-line py-3">
                    <span>{item.label}</span>
                    <span className="chip">{t(`mechanic_status_${item.status}`) || item.status}</span>
                  </li>
                ))}
              </ul>
            ) : (
              <Empty>{t("mechanic_no_items")}</Empty>
            )}
          </details>
        </section>
      )}

      {profile.data && <ContactDetailsForm profile={profile.data} onSave={saveContactDetails} />}
    </main>
  );
}