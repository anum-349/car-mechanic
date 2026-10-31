import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth.jsx";
import { ErrorBox, Field } from "../components/ui.jsx";

export default function Register() {
  const { user, register, registerMechanic, t, lang, setLang } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", password: "", phone: "", city: "", language: lang,
    account_type: "owner", workshop_name: "", address: "", experience_years: "", specialization: "" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  if (user) return <Navigate to="/" replace />;
  const set = (key) => (event) => setForm((current) => ({ ...current, [key]: event.target.value }));

  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setErrors({});
    try {
      const fields = { username: form.username, password: form.password,
        phone: form.phone || null, city: form.city, language: form.language };
      if (form.account_type === "mechanic") {
        await registerMechanic({ ...fields, workshop_name: form.workshop_name,
          address: form.address, experience_years: Number(form.experience_years || 0),
          specialization: form.specialization });
        navigate("/mechanic");
      } else {
        await register(fields);
        navigate("/garage");
      }
    } catch (error) {
      if (error.data && typeof error.data === "object") {
        setErrors(Object.fromEntries(Object.entries(error.data).map(([key, value]) => [key, Array.isArray(value) ? value.join(" ") : String(value)])));
      } else setErrors({ form: error.message });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <h1 className="brand-big">{t("brand")}</h1>
      <div className="seg wide" role="group" aria-label={t("language")}>
        <button type="button" className={lang === "en" ? "on" : ""} aria-pressed={lang === "en"} onClick={() => { setLang("en"); setForm((current) => ({ ...current, language: "en" })); }}>{t("lang_english")}</button>
        <button type="button" className={lang === "roman_ur" ? "on" : ""} aria-pressed={lang === "roman_ur"} onClick={() => { setLang("roman_ur"); setForm((current) => ({ ...current, language: "roman_ur" })); }}>{t("lang_roman")}</button>
      </div>
      <form className="stack" onSubmit={submit}>
        <Field label={t("register_account_type")}><select value={form.account_type} onChange={set("account_type")}>
          <option value="owner">{t("register_car_owner")}</option>
          <option value="mechanic">{t("register_mechanic")}</option>
        </select></Field>
        {form.account_type === "mechanic" && <p className="approval-note">{t("register_mechanic_approval_note")}</p>}
        <Field label={t("username")}><input value={form.username} onChange={set("username")} autoComplete="username" required minLength={3} maxLength={150} aria-invalid={Boolean(errors.username)} /></Field>
        {errors.username && <span className="error" role="alert">{errors.username}</span>}
        <Field label={t("password")} hint={t("password_hint")}><div className="password-input"><input type={showPassword ? "text" : "password"} value={form.password} onChange={set("password")} autoComplete="new-password" required minLength={12} aria-invalid={Boolean(errors.password)} /><button className="password-toggle" type="button" aria-label={t(showPassword ? "password_hide" : "password_show")} aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>{t(showPassword ? "password_hide" : "password_show")}</button></div></Field>
        {errors.password && <span className="error" role="alert">{errors.password}</span>}
        <Field label={t("phone")} hint={form.account_type === "mechanic" ? t("register_public_phone_help") : t("optional")}><input type="tel" value={form.phone} onChange={set("phone")} maxLength={15} autoComplete="tel" required={form.account_type === "mechanic"} aria-invalid={Boolean(errors.phone)} /></Field>
        {errors.phone && <span className="error" role="alert">{errors.phone}</span>}
        <Field label={t("city")}><input value={form.city} onChange={set("city")} maxLength={60} autoComplete="address-level2" required aria-invalid={Boolean(errors.city)} /></Field>
        {errors.city && <span className="error" role="alert">{errors.city}</span>}
        {form.account_type === "mechanic" && <>
          <Field label={t("register_workshop_name")}><input value={form.workshop_name} onChange={set("workshop_name")} maxLength={150} required /></Field>
          {errors.workshop_name && <span className="error" role="alert">{errors.workshop_name}</span>}
          <Field label={t("register_workshop_address")}><textarea rows={2} value={form.address} onChange={set("address")} maxLength={250} required aria-invalid={Boolean(errors.address)} /></Field>
          {errors.address && <span className="error" role="alert">{errors.address}</span>}
          <Field label={t("register_experience")}><input type="number" min="0" max="80" step="1" inputMode="numeric" value={form.experience_years} onChange={set("experience_years")} /></Field>
          <Field label={t("register_specialization")} hint={t("optional")}><input value={form.specialization} onChange={set("specialization")} maxLength={100} /></Field>
        </>}
        <Field label={t("language")}><select value={form.language} onChange={(event) => { set("language")(event); setLang(event.target.value); }}><option value="en">{t("lang_english")}</option><option value="roman_ur">{t("lang_roman")}</option></select></Field>
        {errors.language && <span className="error" role="alert">{errors.language}</span>}
        <ErrorBox>{errors.form || errors.detail || errors.non_field_errors}</ErrorBox>
        <button className="btn" disabled={busy}>{busy ? t("register_loading") : t("register_submit")}</button>
      </form>
      <p>{t("register_existing")} <Link to="/login">{t("login_submit")}</Link></p>
    </div>
  );
}
