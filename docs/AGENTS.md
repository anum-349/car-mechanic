# GaariDoc: agent instructions

AI car-diagnosis assistant for Pakistan. Django REST Framework API (backend/) + React/Vite PWA (frontend/) + PostgreSQL.
Specs live in docs/ (project document, build guide). Follow them; if code and spec disagree, stop and say so.

## Golden rules
1. Nothing AI-written reaches real users until a mechanic approves it. Every knowledge table has `status` and `is_dummy`.
   In production only `status="published"` AND `is_dummy=False` rows are served (setting ALLOW_DRAFT_CONTENT=False).
2. The rules engine is the source of truth for diagnosis. An LLM may only (a) map free text to existing symptom ids and
   (b) phrase explanations. It never picks causes. If the LLM is down, the app still works.
3. Safety-critical symptoms interrupt every flow before any ranking is shown.
4. Wording: say "likely", "unlikely based on your symptoms", "ask for proof". Never "the mechanic is lying". Never name a workshop.
5. Knowledge (rules, costs, thresholds) is data or settings, never hard-coded in views.

## Backend conventions
- Python 3.11, Django, DRF, SimpleJWT, drf-spectacular, pytest + pytest-django. Config in backend/config/.
- Apps: accounts, garage, knowledge, diagnosis, scamshield, reviews. Business logic in services modules (engine.py, logic.py), not views.
- Secrets only from environment (.env, never committed). Update .env.example when adding a variable.
- Every new endpoint: explicit permission class, serializer validation, drf-spectacular annotation, and a pytest test
  (happy path + permission failure).
- Migrations are committed. Never edit an applied migration; add a new one.
- Run `pytest -q` and `python manage.py check` before declaring work done.

## Frontend conventions
- React + Vite, Tailwind, React Router, TanStack Query, axios, i18next (en, roman).
- No hard-coded user-facing strings: use i18n keys in src/i18n/en.json and roman.json.
- Mobile first at 360px width. Big tap targets. Every question has a "Not sure" button.
- API calls only through src/api/. Server state via TanStack Query.
- Run `npm run lint` and `npm run build` before declaring work done.

## Working style
- Make the smallest change that satisfies the task. Do not refactor unrelated code or add unrequested features.
- If the task is ambiguous or conflicts with these rules, ask instead of guessing.
- End every task with: files changed, commands run with results, anything left undone.
