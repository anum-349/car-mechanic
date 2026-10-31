# Security Review

Audit date: 2026-10-16. Scope: Django/DRF APIs, React dependencies, settings, upload/admin paths, NLU, object ownership, serializers, logs and Git secrets. The fixes below are implemented in this working tree. `pytest` and the checks listed at the end are the verification evidence; dependency audit items remain marked according to their actual result.

## Findings and disposition

| Area | Finding | Disposition |
| --- | --- | --- |
| Authentication throttling | Signup and mechanic registration had `auth` scoped throttling; login and refresh did not. | **Fixed** — login, refresh and logout share the `auth` scope; registration remains scoped. Diagnosis endpoints use `diagnosis`, free text uses `free_text`, Scam Shield uses `scam_check`, and events use `analytics`. |
| JWT lifecycle | Refresh rotation existed, but rotated tokens were not blacklisted and there was no logout endpoint. | **Fixed** — SimpleJWT blacklist app enabled, rotation blacklists old tokens, and authenticated logout revokes only the caller's refresh token. Frontend logout calls the endpoint before clearing local tokens. Access lifetime remains 30 minutes and refresh lifetime 7 days. |
| Input validation | Text, numeric, date, nested, enum and upload values needed bounded parsing. | **Fixed** : serializers validate password policy and account fields, session/pre-screen/outcome values, bounded event props, per-model enum/choice fields, 20 question options, price/cost caps, mileage/year/engine ranges, review comments, mechanic inputs, service logs and content text. Flow JSON is schema validated. |
| IDOR | User-owned records must be scoped before detail lookup. | **Fixed and regression-tested** — cars, service logs, sessions, Scam Checks, private reviews and notifications are filtered by owner. The IDOR test requests another user's detail and write/read actions and asserts no object is returned. Public verified mechanic profiles and published knowledge remain intentionally public. |
| Mass assignment | Role, staff flags, mechanic verification, workflow status, dummy/version/approval fields, and derived link weights must not be client controlled by non-reviewers. | **Fixed and tested** — registration sets role server-side; profile/user serializers mark protected fields read-only or omit them; governed serializers make workflow fields read-only; mechanic write views reject control fields; review state is server-set. Reviewer/admin-only knowledge writes are explicit. |
| CORS | Cross-origin access must be allowlisted. | **Fixed / confirmed** — `CORS_ALLOWED_ORIGINS` is built only from the configured comma-separated environment value; `CORS_ALLOW_ALL_ORIGINS` is not enabled. Configure only the production web origins. |
| Production transport/security headers | HSTS was unset by default; transport and secure cookies must be enforced in production. | **Fixed** — production defaults enable SSL redirect, 1-year HSTS with subdomains/preload, secure session/CSRF cookies, `X-Content-Type-Options: nosniff`, and a strict referrer policy. `manage.py check --deploy --fail-level WARNING` is the deploy gate. |
| CSP | The app has no nonce-aware CSP middleware; a static policy must match the deployed frontend/API origins. | **Accepted with deployment action** — configure the reverse proxy CSP in the nginx example below, substituting the actual API origin. Django sets the other security headers. |
| Admin URL | The admin route was fixed at `/admin/`. | **Fixed** — `ADMIN_URL` configures the route, and production `check --deploy` rejects the default `/admin/`; use a long random path and keep the admin behind VPN/IP allowlisting where possible. |
| Admin authentication | Strong staff credentials and second factor reduce compromise risk. | **Fixed / accepted** — Django password validation now requires 12 characters and rejects common/numeric-only passwords. **2FA accepted for follow-up**: django-otp was not added because it changes staff enrollment and recovery flows; place admin behind identity-aware access now and schedule 2FA before public launch. |
| Uploads | The admin JSON importer previously had no explicit upload size/type cap. | **Fixed** — `.json` plus JSON MIME type, 2 MB cap, and the global request/upload memory caps are enforced. No user media upload endpoint exists. |
| Prompt injection | User free text is sent to an LLM for symptom mapping. | **Fixed / reviewed** — input is JSON escaped and marked untrusted, the prompt forbids instructions inside it, output is schema checked, confidence bounded, IDs allowlisted to current category symptoms, duplicates removed, and output capped at five IDs. LLM output cannot choose a cause. |
| Sensitive logging | Passwords, tokens and free text must not enter application logs. | **Fixed / reviewed** — no app logger writes request bodies, prompts, passwords, tokens, phone numbers or free text. Reminder adapters log only the user ID. Keep reverse-proxy access logs free of query-string secrets and do not enable HTTP body logging. |
| Secrets in source/history | Credentials must not be committed or left in history. | **Fixed in source; history exception accepted with reason** : demo seed credentials are randomly generated unless `DEMO_PASSWORD` is supplied; `.env.example` contains placeholders only. The repository-file scan found no credential patterns; gitignored local env files are not tracked and are excluded. The staged Gitleaks hook scans any staged file, including a force-added env file. Git history contains one old Django-generated `django-insecure-...` development key in `backend/config/settings.py`, not a production credential; current settings require `SECRET_KEY` from the environment. If it was ever reused outside development, revoke it immediately. |
| Dependencies | Vulnerable Python and npm packages must be detected and updated. | **Accepted with release gate** : the last successful npm audit reported 15 advisories (2 critical, 6 high, 7 moderate) in transitive dependencies including Vitest, Vite/esbuild, Tailwind/PostCSS, chokidar/micromatch/braces and React Router. Non-breaking `npm audit fix` did not clear them; available fixes require major tooling/framework upgrades and a compatibility migration. Re-run both audits on a networked release runner and clear critical/high issues before deployment. |

## Reverse-proxy CSP example

Set this in nginx at the application location after replacing `api.example.com` with the only API origin the browser needs:

```nginx
add_header Content-Security-Policy "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; img-src 'self' data: https:; font-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self' https://api.example.com" always;
```

Do not add `unsafe-eval`, wildcard origins, or third-party script hosts without a reviewed requirement. Verify the built app and API origin under this policy before rollout.

## Admin and deployment checklist

- Set `ADMIN_URL` to a randomly generated path in the production secret store; never expose the admin site publicly when VPN/IP restriction is available.
- Use unique staff accounts, password-manager-generated credentials, and a managed second factor/identity proxy. Keep Django `is_staff` limited to operators.
- Set `DEBUG=False`, explicit `ALLOWED_HOSTS`, configured frontend `CORS_ALLOWED_ORIGINS`, and production database/broker secrets.
- Run `python manage.py check --deploy --fail-level WARNING`, `python manage.py migrate --check`, `pip-audit -r backend/requirements.txt`, `npm audit --audit-level=high`, and the Gitleaks pre-commit hook before release.
- Ensure TLS termination forwards scheme safely. Only set `SECURE_PROXY_SSL_HEADER` when requests can reach Django exclusively through a trusted proxy configured to overwrite the forwarded-proto header.

## Audit commands and results

- `python manage.py check --deploy --fail-level WARNING` with production-like settings : **passed**, 0 issues. `makemigrations --check --dry-run` : **passed**, no changes detected.
- `pip-audit -r requirements.txt --progress-spinner off` : **not completed**: advisory lookup was unreachable in this environment.
- `npm audit --audit-level=high` : previous registry-backed result reported 15 advisories; latest request failed because `registry.npmjs.org` was unreachable. See the accepted dependency finding above.
- Repository-file secret-pattern scan : **passed** (0 matches; gitignored local env files excluded); history scan found only the old Django starter development key described above. Gitleaks itself was unavailable; TOML and pre-commit YAML parse successfully.
- `pytest -q` : **passed**, 132 passed and 35 subtests passed (16 warnings, including expected flow-prior fixture warnings and an unordered-paginator warning). Final focused security regression suite: **4 passed** after the last bounds changes.
