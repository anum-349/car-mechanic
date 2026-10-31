import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useAuth, homeFor } from "../auth.jsx";
import { ErrorBox, Field } from "../components/ui.jsx";

export default function Login() {
  const { user, login, t, lang, setLang } = useAuth();

  if (user) return <Navigate to={homeFor(user)} replace />;

  const [form, setForm] = useState({ username: "", password: "" });
  const [errors, setErrors] = useState({});
  const [busy, setBusy] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  if (user) return <Navigate to="/" replace />;

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setErrors({});

    try {
      await login(form.username, form.password);
    } catch (err) {
      if (err.data && typeof err.data === "object") {
        setErrors(
          Object.fromEntries(
            Object.entries(err.data).map(([key, value]) => [
              key,
              Array.isArray(value) ? value.join(" ") : String(value),
            ])
          )
        );
      } else {
        setErrors({ form: err.message });
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth">
      <h1 className="brand-big">{t("brand")}</h1>
      <div className="seg wide" role="group" aria-label={t("language")}>
        <button type="button" className={lang === "en" ? "on" : ""} aria-pressed={lang === "en"} onClick={() => setLang("en")}>{t("lang_english")}</button>
        <button type="button" className={lang === "roman_ur" ? "on" : ""} aria-pressed={lang === "roman_ur"} onClick={() => setLang("roman_ur")}>{t("lang_roman")}</button>
      </div>
      <p className="muted">{t("login_intro")}</p>
      <form className="stack" onSubmit={submit}>
        <Field label={t("username")}>
          <input
            value={form.username}
            onChange={(e) => setForm({ ...form, username: e.target.value })}
            autoComplete="username"
            required aria-invalid={Boolean(errors.username)}
          />
        </Field>
        {errors.username && <span className="error" role="alert">{errors.username}</span>}
        <Field label={t("password")}>
          <div className="password-input">
            <input
              type={showPassword ? "text" : "password"}
              value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })}
              autoComplete="current-password"
              required aria-invalid={Boolean(errors.password)}
            />
            <button className="password-toggle" type="button"
              aria-label={t(showPassword ? "password_hide" : "password_show")}
              aria-pressed={showPassword} onClick={() => setShowPassword((visible) => !visible)}>
              {t(showPassword ? "password_hide" : "password_show")}
            </button>
          </div>
        </Field>
        {errors.password && <span className="error" role="alert">{errors.password}</span>}
        <ErrorBox>{errors.form || errors.detail || errors.non_field_errors}</ErrorBox>
        <button className="btn" disabled={busy}>
          {busy ? t("login_loading") : t("login_submit")}
        </button>
      </form>
      <p>
        {t("login_new")} <Link to="/register">{t("register_link")}</Link>
      </p>
    </div>
  );
}
