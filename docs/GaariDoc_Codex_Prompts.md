# GaariDoc: Codex Prompt Pack

Companion to the Project Document and the Step-by-Step Build Guide. One prompt per task, in build order.

## How to run this pack

1. **Put the context file in the repo first** (Prompt 00). Codex reads `AGENTS.md` at the repo root, so every later prompt can stay short.
2. **One prompt = one branch = one commit.** `git checkout -b p05-knowledge-models`, run the prompt, read the diff, run the tests, merge. Do not stack prompts.
3. **Paste the prompt verbatim.** Each one names the guide step it implements and ends with acceptance commands. If an acceptance command fails, paste the failure back and ask Codex to fix it before moving on.
4. **After each phase, run the Audit prompt** (bottom of this file) in a fresh session. A second pass catches what the first one rationalised.
5. **Assumption:** you did Step 0.4 and Step 1.1 yourself (folders, venv, `startproject`, `startapp` x6). Prompts start at Step 1.2. If you also wrote the User model by hand, skip Prompt 02.

---

## Prompt 00: AGENTS.md (create this file yourself, at repo root)

```markdown
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
- React + Vite, Tailwind, React Router, TanStack Query, axios, i18next (en, roman; Urdu RTL later).
- No hard-coded user-facing strings: use i18n keys in src/i18n/en.json and roman.json.
- Mobile first at 360px width. Big tap targets. Every question has a "Not sure" button.
- API calls only through src/api/. Server state via TanStack Query.
- Run `npm run lint` and `npm run build` before declaring work done.

## Working style
- Make the smallest change that satisfies the task. Do not refactor unrelated code or add unrequested features.
- If the task is ambiguous or conflicts with these rules, ask instead of guessing.
- End every task with: files changed, commands run with results, anything left undone.
```

---

# BACKEND

## Prompt 01: Settings, environment, CORS, JWT, OpenAPI (Step 1.2)

```
Read AGENTS.md and docs/. Implement guide Step 1.2 in backend/config/settings.py.

- Add accounts, garage, knowledge, diagnosis, scamshield, reviews, rest_framework, corsheaders, drf_spectacular to INSTALLED_APPS; add the CorsMiddleware in the correct position.
- Load config with python-dotenv from backend/.env: SECRET_KEY, DEBUG, ALLOWED_HOSTS, DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, CORS_ALLOWED_ORIGINS, ALLOW_DRAFT_CONTENT (default True when DEBUG, otherwise False). Create backend/.env.example with every variable and safe placeholder values. Confirm .env is in .gitignore.
- DATABASES: PostgreSQL via those env vars.
- AUTH_USER_MODEL = "accounts.User".
- REST_FRAMEWORK: JWT auth, IsAuthenticated default, drf_spectacular schema, throttling with both AnonRateThrottle and UserRateThrottle (anon 60/min, user 300/min) plus a named scope "diagnosis" at 120/min and "auth" at 10/min that views can opt into.
- SIMPLE_JWT: access 30 min, refresh 7 days, rotate refresh tokens.
- Add the engine thresholds as settings with env overrides: ENGINE_CONFIDENCE_THRESHOLD=0.70, ENGINE_MIN_GAP=0.20, ENGINE_MAX_QUESTIONS=8, ENGINE_LEAK_LIKELIHOOD=0.05.
- config/urls.py: /api/schema/, /api/docs/ (Swagger UI), /api/auth/token/, /api/auth/token/refresh/, and an empty include("...urls") stub per app under /api/.
- Split nothing into multiple settings files yet.

Do not create models. Acceptance: `python manage.py check` passes; /api/schema/ renders once the User model exists (if Prompt 02 is not done yet, say so rather than faking it).
```

## Prompt 02: Custom user, mechanic profile, roles, JWT login (Steps 1.3 and 1.4)

```
Read AGENTS.md and docs/ (Database Schema 9.1). Implement guide Steps 1.3 and 1.4 in the accounts app.

Models (match the schema doc, not just the guide snippet):
- User(AbstractUser) with: phone (unique, null=True, blank=True), role (user/mechanic/reviewer/admin, default user), city, language choices en / roman_ur / ur (default en), created_at, updated_at. Keep username-based login for now.
- MechanicProfile one-to-one with User: workshop_name, city, experience_years, specialization, is_verified (default False), honesty_score (decimal 3,2, default 0), created_at, updated_at.

Also build:
- permissions.py with IsMechanic, IsReviewer, IsAdminRole, checking request.user.role and request.user.is_authenticated. A "reviewer" permission must also admit role=admin.
- POST /api/auth/register/ (username, password, phone optional, city, language): creates role=user ONLY. Role must never be settable from the client. Apply the "auth" throttle scope. Validate password with Django validators.
- GET/PATCH /api/me/ for profile (name, city, language, phone). Role is read-only.
- Use the SimpleJWT views already wired in config/urls.py for login and refresh.
- Admin registration for both models.
- Tests: register works; client cannot set role; login returns access+refresh; /api/me/ requires auth; each permission class allows its role and rejects others.

Run makemigrations and migrate. Acceptance: `pytest -q` green; `python manage.py check` clean; /api/schema/ loads.
```

## Prompt 03: Garage models (Step 2.1)

```
Read AGENTS.md and docs/ (Database Schema 9.1). Implement guide Step 2.1 in garage/models.py: CarMake, CarModel, Car, plus ServiceLog from the schema (car FK, service_type, service_date, mileage_km, cost, next_due_date, notes).

- Use TextChoices for fuel_type (petrol, diesel, hybrid, cng) and transmission (manual, automatic) instead of free strings.
- Car also has fuel_type (schema doc). CarModel unique on (make, name, generation).
- Add created_at / updated_at via a small abstract TimeStamped base in a shared place (accounts or a new core module) and use it everywhere from now on.
- Validators: year between 1980 and current year + 1; mileage_km >= 0.
- Register in admin with list_display, list_filter, search_fields.
- Add garage serializers and views now: GET/POST /api/cars/, GET/PATCH/DELETE /api/cars/{id}/, GET /api/car-models/ (public read, for the add-car picker). Users can only see and edit their own cars (queryset filtered by request.user; test that another user's car returns 404).

Tests for ownership, validation, and the car-model list. Acceptance: migrations created and applied; `pytest -q` green.
```

## Prompt 04: Knowledge-base models (Step 2.2)

```
Read AGENTS.md and docs/ (Database Schema 9.2 and 9.4, Section 7.3 status workflow). Implement guide Step 2.2 in knowledge/models.py. Read the guide's code as a sketch only; follow the schema doc where they differ.

Models: SymptomCategory (name_en, name_roman, name_ur), Symptom, Cause (with car_models M2M), CauseSymptomLink, Question, AnswerOption, SelfCheck, RepairCost, WarningLight, ObdCode (code is the primary key), ObdCodeCause, ContentReview.

Requirements:
- Abstract `Governed` base: status (ai_draft, draft, submitted, under_review, approved, published; default draft), is_dummy, version, created_by, approved_by, created_at, updated_at. Apply to Symptom, Cause, Question, SelfCheck, RepairCost.
- A custom manager/queryset method `.visible()` on every Governed model that returns everything when settings.ALLOW_DRAFT_CONTENT is True, otherwise only status=published and is_dummy=False. Engine and public endpoints must use it. Unit-test both modes.
- STRENGTH_WEIGHT = always 0.9, often 0.7, sometimes 0.4, rarely 0.1. CauseSymptomLink.weight is derived from strength in save() and is never client-editable. Include the optional car_model FK override from the schema.
- Constraints: unique (cause, symptom, car_model) on links (note: nullable car_model means you need a conditional UniqueConstraint for the NULL case too, otherwise duplicates slip through on PostgreSQL), unique (cause, city) on RepairCost, composite uniqueness on ObdCodeCause. Add DB CheckConstraints: prior between 0 and 1, parts_min <= parts_max, labour_min <= labour_max.
- Question.type (single_choice, yes_no, media_choice), media_url. AnswerOption: label (add label_roman), is_unsure, implies_symptom nullable. Add a model-level clean/validation helper that a question has at least two options including exactly one unsure option (enforced in the importer and API serializers, not in the DB).
- RepairCost: last_verified (date, nullable), source.
- ContentReview: content_type, object_id, version, status (submitted, under_review, approved, rejected, returned), submitted_by, reviewed_by, comment, snapshot (JSONField), reviewed_at.
- Add the indexes listed in schema section 9.6.

Do NOT register admin yet (next prompt). Acceptance: makemigrations + migrate succeed; tests for .visible(), weight derivation, and each constraint (assert IntegrityError) pass.
```

## Prompt 05: Diagnosis and Scam Shield models (Step 2.3)

```
Read AGENTS.md and docs/ (Database Schema 9.3). Implement guide Step 2.3.

diagnosis app: DiagnosisSession (user, car, category, status in_progress/completed/abandoned, safety_alert, free_text, started_at, completed_at), SessionAnswer (session related_name="answers", question, option, free_text, answered_at), SessionResult (session related_name="results", cause, rank, confidence, explanation), Outcome (session one-to-one, actual_cause nullable, actual_cause_text, actual_cost, mechanic nullable FK to User, was_helpful, notes).
scamshield app: ScamCheck (session nullable, user, claimed_cause nullable, claim_text, quoted_price, plausibility, verdict plausible/doubtful/suspicious).
reviews app: Review (user, mechanic -> accounts.MechanicProfile, rating 1-5 with check constraint, comment, status pending/approved/rejected).

Rules:
- Sessions are append-only for analysis: use on_delete=PROTECT for knowledge FKs so deleting a cause cannot erase history. Unique (session, question) on SessionAnswer. Unique (session, rank) on SessionResult. Indexes per schema 9.6.
- SessionResult stores a snapshot of the cause name too (cause_name) so history survives later renames.
- Do not build views yet.

Acceptance: migrations apply; tests cover the unique constraints, the PROTECT behaviour, and the rating check.
```

## Prompt 06: Admin as the first content panel (Step 2.4)

```
Read AGENTS.md. Implement guide Step 2.4 in admin.py for knowledge, diagnosis, scamshield, reviews, accounts, garage.

- list_display, list_filter (status, is_dummy, severity, system where relevant), search_fields, readonly created_at/updated_at.
- Cause admin: inlines for CauseSymptomLink, SelfCheck, RepairCost; filter_horizontal for car_models.
- Question admin: AnswerOption inline.
- Admin actions on Symptom, Cause, Question, SelfCheck, RepairCost: "Mark as submitted", "Approve" (sets approved + approved_by=request.user + is_dummy=False + writes a ContentReview snapshot), "Publish approved". Only users with role reviewer/admin may run them (check inside the action, not just by Django permissions).
- Make weight readonly on CauseSymptomLink; show derived label.
- A highlighted "SAMPLE" marker column for is_dummy rows.

Add a pytest using the Django test client that logs in as superuser and loads every changelist page (catches broken admin config). Acceptance: `pytest -q` green.
```

## Prompt 07: Flow import command with validation (Steps 3.1 and 3.3)

```
Read AGENTS.md and docs/ (guide Phase 3). Build `python manage.py import_flow <path>` in knowledge/management/commands/import_flow.py.

Input: the JSON format in guide Step 3.1 (category, car_models, symptoms with key/en/roman/safety, causes with links/self_check/costs, questions with options). Differences from the guide's sketch:
1. VALIDATE FIRST, write nothing if any error. Use a pydantic or hand-written validator. Collect all errors and print them with JSON paths. Rules: strength in always/often/sometimes/rarely; every link/question references a defined symptom key; every question has >=2 options with exactly one {"unsure": true}; prior between 0 and 1; costs min<=max; car_models resolve to existing CarModel rows (exact "Make Model" or model name match, error if ambiguous or missing); priors for causes in one flow sum to between 0.8 and 1.2 (warn, not error).
2. Run inside transaction.atomic().
3. Idempotent: re-importing the same file updates rows keyed by (category, symptom key / cause name / question text) instead of duplicating. Store the symptom `key` in a new nullable `key` field on Symptom (add the migration), unique per category.
4. Everything imported gets status=ai_draft, is_dummy=True, created_by=None. Never overwrite a row whose status is approved or published; skip and report it.
5. Create SelfCheck, RepairCost (one row per city; last_verified left null for AI data, source="ai_draft"), Question and AnswerOption rows, and link Cause.car_models.
6. Print a summary: counts created/updated/skipped.
7. A --dry-run flag.

Also create backend/flows/_example_wont_start.json as a small, hand-written valid sample (4 symptoms, 4 causes, 3 questions) used as a test fixture.

Tests: valid import; each validation rule fails correctly; atomic rollback; idempotency; approved rows untouched. Acceptance: `pytest -q` green.
```

## Prompt 08: Seed cars, warning lights, OBD2 (Step 3.5)

```
Read AGENTS.md and docs/ (guide Step 3.5, Step 0.1 scope). Create fixtures and a loader.

- backend/fixtures/cars.json: makes Suzuki, Toyota, Honda and CarModel rows for the five in-scope cars: Suzuki Alto (660cc, current-gen EFI), Suzuki Cultus (1000cc), Toyota Corolla (1.3L and 1.6L/1.8L generations), Honda Civic, Honda City. Use plausible generation/year ranges; add a comment field noting "verify with a mechanic".
- backend/fixtures/warning_lights.json: 18 common dashboard lights (battery/charging, oil pressure, engine temperature, check engine, ABS, airbag, brake system, power steering, low fuel, tyre pressure, seatbelt, door ajar, glow plug, traction control, etc.) with severity stop_now/repair_soon/info, a plain-English meaning, recommended_action, and a Roman Urdu meaning field if you add one (add `meaning_roman`, `action_roman` fields via migration). All flagged is_dummy via a new is_dummy field on WarningLight, since AI-written meanings need review too.
- backend/fixtures/obd_codes.json: ~40 generic powertrain codes (P0100-P0135 sensors, P0171/P0172, P0300-P0304, P0420, P0440s, P0500s, P0600s selection) with description and system. Use only generic SAE code meanings; do not invent manufacturer-specific codes.
- `python manage.py seed_reference` loads all three idempotently (update_or_create).
- Public read endpoints: GET /api/warning-lights/ and GET /api/obd/{code}/ (case-insensitive, returns description, system, severity if known, and likely causes via ObdCodeCause) and GET /api/categories/ (SymptomCategory list). These are AllowAny, throttled.
- Add a `draft_content` boolean to every API response that serves is_dummy or ai_draft content, via a small mixin or response wrapper, so the frontend can show the SAMPLE DATA banner (Step 3.4).

Tests for the loader and the three endpoints. Acceptance: `pytest -q` green, `python manage.py seed_reference` runs twice with no duplicates.
```

> **Non-Codex step (Step 3.2):** generate the three flows with your LLM using the improved drafting prompt in the appendix at the bottom, save them to `backend/flows/`, and import with `python manage.py import_flow backend/flows/wont_start_alto_cultus.json --dry-run`, then for real.

---

# DIAGNOSIS ENGINE AND API

## Prompt 09: Scoring engine, safety rules, next question, stopping rule (Steps 4.1 to 4.4, 4.6)

```
Read AGENTS.md and docs/ (Project Doc Section 6, guide Phase 4). Create backend/diagnosis/engine.py as pure, well-tested service functions. Use the guide's code as a sketch, but FIX THESE DEFECTS in the guide's version:

1. LEAK / UNLINKED SYMPTOMS. The guide only multiplies by a cause's own links, so a present symptom LOWERS the score of causes that explain it (weight < 1) while unrelated causes are untouched. Correct Naive-Bayes-style update: for each cause and each OBSERVED symptom, likelihood is `w` if the cause has a link (model-specific link overrides the generic one), else `ENGINE_LEAK_LIKELIHOOD` (setting, 0.05). For each ABSENT symptom: `1 - w` if linked, else `1 - leak`. "Not sure" answers contribute nothing. Compute in log space and normalise so confidences sum to 1.
2. SAFETY FIRST. `safety_alert(session)` must also consider symptoms implied by the CURRENT answer and be callable before any answer exists (for the pre-screen). Return the symptom plus a stop message key.
3. QUERY SANITY. Scope causes by category AND car model; apply `.visible()` (from the knowledge managers) everywhere; avoid N+1 queries (prefetch links; compute the cause x symptom weight map once per call instead of querying inside the loop in next_question).
4. NEXT QUESTION. Pick the unanswered, visible question for this category whose symptom has the largest spread of link weights across the current top 3 causes (unlinked = leak value). Skip questions whose symptom is already determined. Return None when no question has spread above a small epsilon.
5. STOPPING RULE. should_stop(session, ranked) is true when top confidence >= ENGINE_CONFIDENCE_THRESHOLD and gap to second >= ENGINE_MIN_GAP, or answered count >= ENGINE_MAX_QUESTIONS, or no useful question remains. Thresholds come from settings.
6. EXPLAINABILITY (NFR-7). rank_causes returns for each cause its confidence and the list of supporting and contradicting symptoms (with the user's answer wording) so the result page can show a plain "why" line.

Also: evidence(session) as in the guide (option with implies -> present; negative option with no implies and not unsure -> question.symptom absent; unsure -> ignored).

Tests (pytest, build fixtures with factories, not the importer): weak battery ranks first for slow crank + dim lights with confidence > 0.5; a present symptom RAISES a linked cause relative to an unlinked one (regression test for defect 1); absent symptom lowers a linked cause; unsure changes nothing; a safety-critical symptom triggers the alert; draft rows are hidden when ALLOW_DRAFT_CONTENT=False; stopping rule branches; next_question prefers the more discriminating question; confidences sum to 1; query count stays constant as causes grow (use django_assert_max_num_queries).

Acceptance: `pytest -q` green.
```

## Prompt 10: Session API (Steps 4.5 and 8.1 backend part)

```
Read AGENTS.md and docs/ (guide Step 4.5). Implement the diagnosis endpoints in diagnosis/views.py, serializers.py, urls.py using engine.py. Use the guide's answer view as a sketch only.

Endpoints (all IsAuthenticated, user can only touch own sessions, "diagnosis" throttle scope):
- POST /api/sessions/ {car, category, free_text?}: validates the car belongs to the user and the category exists; runs the safety pre-screen on any pre-screen answers if sent; returns session id and the first question.
- POST /api/sessions/{id}/answer/ {question, option}: validate the option belongs to the question, the question belongs to the session's category, and the question was not already answered (409). Save SessionAnswer, run safety check first; if tripped: set safety_alert, status stays in_progress, return {"stop": true, "message": ...}. Otherwise rank, check should_stop, and return {"done": true, "result": ...} or {"done": false, "question": ...}. Wrap in transaction.atomic and select_for_update on the session to stop double-submits.
- GET /api/sessions/{id}/result/: ranked top causes (max 5) with confidence band (use labels "very likely / likely / possible / unlikely" from thresholds rather than raw percentages in the payload field `band`, keep numeric `confidence` too), why-line data, self-checks, cost ranges for the user's city falling back to any city with a flag, `last_verified`, a generated "ask your mechanic" script from templates (en and roman, stored in knowledge as data or a simple template file, not LLM), `draft_content` flag, and the standing disclaimer text. Persist SessionResult rows once when the session completes; mark completed_at.
- POST /api/sessions/{id}/outcome/ {actual_cause?, actual_cause_text?, actual_cost?, was_helpful, notes?}: one per session (409 on duplicate), only for completed sessions.
- POST /api/sessions/{id}/abandon/ optional.

Question serializer must return options with ids and labels in the user's language (roman fallback to en) and must NOT leak implies_symptom or weights.

Tests: full happy-path through the API for the imported example flow; safety stop; another user gets 404; duplicate answer 409; wrong-category question rejected; outcome rules; no weight/implies fields in payloads; unauthenticated 401. Update OpenAPI annotations. Acceptance: `pytest -q` green and /api/schema/ lists every endpoint.
```

---

# REACT FRONTEND

## Prompt 11: Frontend scaffold, API client with real token refresh, i18n, routing (Steps 5.1 to 5.3, 5.7)

```
Read AGENTS.md. I already ran `npm create vite@latest` and installed the packages from guide Step 5.1 inside frontend/. If Tailwind is not initialised, finish it (Tailwind v3 or v4, whichever is installed; do not mix).

Build:
- Folder structure from guide Step 5.2 (api, components, pages, i18n, hooks).
- src/api/client.js: axios instance using VITE_API_URL; request interceptor adds the Bearer token; RESPONSE interceptor handles 401 by calling /auth/token/refresh/ ONCE (single in-flight refresh shared by concurrent requests, queue the others), retries the original request, and on refresh failure clears tokens and redirects to /login. The guide's version omits this.
- src/hooks/useAuth.jsx: context with login, logout, register, current user (GET /me/), isMechanic/isReviewer helpers. Tokens in localStorage inside try/catch.
- i18next with en.json and roman.json, a language switcher component that persists the choice, and the user's profile language used as default after login. Add `dir` handling so Urdu RTL can be added later without refactoring.
- React Router with routes: /, /login, /register, /garage, /diagnose, /diagnose/:id, /result/:id, /scam-shield, /warning-lights, /obd, /history; a ProtectedRoute wrapper; placeholder pages only.
- A <DraftBanner /> component ("SAMPLE DATA: not for real use") shown when any API response has draft_content true (React Query meta/ context), and a persistent <Disclaimer /> footer.
- .env.example with VITE_API_URL=http://localhost:8000/api.

Mobile-first at 360px. Add a Vitest + Testing Library setup with one test for the refresh-queue logic. Acceptance: `npm run lint`, `npm test`, `npm run build` pass; app loads and navigates between placeholder pages.
```

## Prompt 12: Auth screens and My Garage (Step 5.5, first two bullets)

```
Read AGENTS.md. Build Login, Register and Garage pages in frontend/src/pages using the existing useAuth hook and api client.

- Login/Register forms: big inputs, inline validation errors from the API, language switch visible on the first screen, loading and error states. Register collects username, password, phone (optional), city, language.
- Garage page: list the user's cars (React Query), "Add car" form with make -> model dropdown (from /car-models/, model options filtered by make), year, mileage, transmission, fuel, nickname; edit and delete with confirmation.
- Empty state that explains why adding a car matters.
- All strings via i18n keys in en.json and roman.json (write natural Roman Urdu, flag any line you are unsure of with a "// verify" comment in a docs/i18n-review.md list instead of in JSON).

Acceptance: lint, test, build pass. Add component tests for the add-car form validation.
```

## Prompt 13: Start Diagnosis, question flow, stop-driving screen (Steps 5.4, 5.5)

```
Read AGENTS.md and docs/ (API contract is in /api/schema/; backend/diagnosis/views.py shows payloads). Build:

1. /diagnose (StartDiagnosis): choose car (from garage, link to add one), choose category (from /categories/, big cards), optional free-text box (disabled with a "coming soon" note until the NLU endpoint exists), and a first-screen safety pre-screen: "Any brake problem, burning smell, steam or smoke?" Yes -> go straight to the StopDriving screen with towing advice. Otherwise POST /sessions/ and navigate to /diagnose/:id.
2. /diagnose/:id (Diagnosis): chat-style, one QuestionCard at a time, options as large buttons (min 48px height), a "Not sure" button always visible, a progress hint, back-safe (page refresh must resume: add GET /api/sessions/{id}/ on the backend returning the next unanswered question or the result, with a test). Handle the three response shapes {stop}, {done, result}, {question}. Disable buttons while a request is in flight to prevent double-submits. Show media_url images when present, lazy-loaded.
3. <StopDriving />: full-screen red, large type, plain steps (pull over safely, switch off the engine, do not drive, call a tow), a button to call a saved emergency number the user can set later (placeholder), no ranking shown.
4. Skeleton/loading state and an error state with retry.

Acceptance: lint, test, build pass; tests for the three response shapes and the double-submit guard. Walk through the flow against the local backend using the imported example flow and report what you verified.
```

## Prompt 14: Result page (Step 5.5, Result bullet; Step 8.2 card)

```
Read AGENTS.md. Build /result/:id (Result) and the components CauseCard, ConfidenceBar, CostRange, SelfCheckList, MechanicScript, in frontend/src.

- Cause cards ranked, using the `band` label as the headline ("Very likely / Likely / Possible") with a bar for confidence. DO NOT show over-precise percentages; show the number only in a small secondary label rounded to the nearest 5.
- Each card: plain "why" line from the supporting/contradicting symptoms, expandable self-check (steps, tools, difficulty), cost range with parts and labour shown separately in PKR, city, and a "last verified" date (show "estimate, not verified" in an amber label if null).
- "Ask your mechanic" script card in the user's language with a copy button.
- Standing disclaimer visible above the fold. DraftBanner when draft_content is true.
- Helpful / not helpful vote posting to the outcome endpoint partially (add PATCH support on the backend for `was_helpful` before the full outcome exists, with a test).
- A <ShareCard /> component (verdict, top cause band, cost range, watermark and short referral code placeholder) that renders offscreen and exports with html-to-image; a Share button using navigator.share({files}) with a download fallback. 360px layout, test the exported card visually by rendering it in a Vitest snapshot of the DOM structure.

Acceptance: lint, test, build pass. Report what you could not verify (real-device sharing).
```

## Prompt 15: PWA, performance, 360px pass (Step 5.6)

```
Read AGENTS.md. Add vite-plugin-pwa with a manifest (name GaariDoc, theme colour, icons placeholder in public/), a service worker that precaches the app shell and uses stale-while-revalidate for GET /categories/, /car-models/, /warning-lights/ and network-first for session endpoints (NEVER cache authenticated POSTs or /me/). Lazy-load every route with React.lazy + Suspense. Add `loading="lazy"` and explicit width/height to images. Report the production bundle size per chunk (`npm run build`) and flag anything over 150 kB gzipped.

Then review every existing page at 360px width using Playwright screenshots (Chromium is installed; do not run `playwright install`) and fix overflow, tiny tap targets and contrast issues. Save screenshots to docs/screens/ . Acceptance: build passes, Lighthouse PWA installability check (via Playwright/CLI if available, otherwise state it was not run).
```

---

# SCAM SHIELD, LIGHTS, OBD2, LANGUAGE

## Prompt 16: Scam Shield backend and screen (Steps 6.1, FR-16 to FR-19)

```
Read AGENTS.md and docs/ (Project Doc 6.4, guide Step 6.1). Implement scamshield/logic.py, the API and the React screen.

Logic (fix the guide's sketch):
- evaluate(session, claimed_cause, quoted_price, city) -> (plausibility, verdict, reasons, proof_suggestions). Cause probability comes from engine.rank_causes for that session (include the claimed cause even if it was outside the top list; if it is not a candidate at all for this car/category, treat probability as 0 and say so).
- Cost: RepairCost.visible() for (cause, city); fall back to any city if missing and mark `price_basis="other_city"`; if no cost at all, price_score is neutral 0.5 and the verdict cannot be "suspicious" on price alone.
- plausibility = 0.6 * min(prob*2, 1) + 0.4 * price_score, thresholds as settings (0.65 / 0.35). Price: > 1.5 x max -> 0.2, > max -> 0.6, within range -> 1.0, far below min -> 0.9 (flag "unusually cheap, ask about part quality").
- Proof suggestions are DATA: add a `proof_hint` text field to Cause (migration) filled per cause; fall back to generic hints ("Ask which part is worn and to be shown it", "Ask for the old part back").
- Wording: only "unlikely based on your symptoms", "higher than the usual range", "ask for proof". Add a test that scans all verdict/reason strings for banned words (lying, cheat, fraud, scam artist, thief).

API: POST /api/scam-check/ {session, claimed_cause | claim_text, quoted_price, city?}; session must belong to the user and be completed; claim_text alone (no known cause) returns a limited response asking the user to pick from the list. Persist ScamCheck. GET /api/scam-check/{id}/ for share.

Frontend: /scam-shield page: pick one of your completed sessions, pick or type the mechanic's claim, enter the quote in PKR, see verdict with colour AND icon AND text (not colour only), reasons, proof suggestions, and a share card (reuse ShareCard) that never names a workshop.

Tests: each verdict branch, missing cost fallback, claimed cause outside candidates, wrong-owner session 404, banned-wording scan. Acceptance: pytest, lint, build green.
```

## Prompt 17: Warning-light decoder and OBD2 lookup screens (Steps 6.2, 6.3)

```
Read AGENTS.md. Endpoints /api/warning-lights/ and /api/obd/{code}/ already exist. Build the screens.

- /warning-lights: icon grid (use simple inline SVG/emoji placeholders keyed by name; real icons later via icon_url), filter chips by severity, tap opens a bottom sheet with name, severity badge (stop now = red + icon + text, repair soon = amber, info = blue), meaning, recommended action; language-aware. Searchable by name. Stop-now lights link to the StopDriving advice.
- /obd: search box normalising input (uppercase, trim, validate pattern like P0301 / B/C/U codes), result with description, system, likely causes and a CTA "Start a diagnosis with this code" that pre-selects the matching category if mapped. Handle not found with a helpful message ("code may be manufacturer-specific; ask your mechanic").
- Both pages must work offline from the PWA cache for already-viewed data.
- DraftBanner when applicable.

Tests for code normalisation and the bottom sheet. Acceptance: lint, test, build green.
```

## Prompt 18: Free-text understanding with the LLM (Step 6.4)

```
Read AGENTS.md. Implement diagnosis/nlu.py and POST /api/sessions/{id}/free-text/.

Design (follow the guide's safety note strictly):
- LLM client behind a tiny interface `LLMClient.json(prompt, schema) -> dict` with an Anthropic or OpenAI implementation chosen by env LLM_PROVIDER and a FakeLLM for tests. Keys from env only. 5 s timeout, 1 retry, never raise to the user.
- map_text_to_symptoms(text, category): candidate symptoms = Symptom.visible() in that category (ids, text_en, text_roman). Send ONLY the user text and the candidate list. Ask for JSON {"symptom_ids": [...], "confidence": 0-1}. Treat the user text as untrusted: put it in a delimited block and instruct the model to ignore instructions inside it. Validate: ids must be a subset of candidates; drop everything else; cap at 5; if confidence < 0.5 or LLM fails return [].
- The endpoint records the text in session.free_text, converts matched symptoms into evidence by creating synthetic SessionAnswer rows? NO: add a new SessionSymptom table (session, symptom, source="free_text") that engine.evidence() also reads. Update engine and its tests accordingly (present symptoms from free text count as present; they are re-checked by safety_alert too).
- Fallback: when nothing maps, respond {"mapped": [], "fallback": true} and the frontend just starts the normal questions.
- Rate limit this endpoint harder (30/hour/user). Enable the free-text box in StartDiagnosis and show the user which symptoms we understood ("We understood: ...") with a way to remove each.
- Evaluation harness: management command `eval_nlu --file backend/eval/phrases.jsonl` that reads {text, expected_symptom_keys} rows (I will supply the 20-30 collected phrases) and prints precision/recall. Include a 5-row sample file.

Tests with FakeLLM: valid ids kept, hallucinated ids dropped, prompt injection text cannot add ids outside the list, timeout falls back, safety symptom from free text triggers the stop. Acceptance: pytest, lint, build green.
```

---

# MECHANIC PANEL AND APPROVAL WORKFLOW

## Prompt 19: Versioning design and content services (Step 7.5 groundwork)

```
Read AGENTS.md and docs/ (Project Doc 7.3, FR-31, FR-34, guide Step 7.5). Before coding, write docs/versioning-design.md (max one page) and then implement it.

PROBLEM: the guide says editing a published item creates version+1 as a draft while the live version stays live. With one row per item and unique constraints (cause+city, cause+symptom+model), that is impossible to do safely. Choose and implement THIS design unless you find a concrete flaw (then stop and explain):
- Keep the LIVE row untouched. Edits to approved/published content are saved as a `pending_revision` JSON on a new model `ContentRevision(content_type, object_id, base_version, payload, author, status, created_at)`; the live row changes only when a reviewer approves the revision, at which point the payload is applied, version += 1, and a ContentReview snapshot is written.
- New (never-published) items are edited in place as drafts.
- Cause-level edits must include their nested links, self-checks and costs in one payload, applied atomically.

Implement in knowledge/services/workflow.py: submit(item, user), start_review(item, reviewer), approve(item_or_revision, reviewer, comment), return_for_changes(..., comment), reject(..., comment), publish(item, reviewer), create_revision(item, user, payload), apply_revision(...). Rules: mechanics may only draft/submit their own items; only reviewer/admin may approve/return/reject/publish; illegal transitions raise a domain error; every transition writes a ContentReview row with a JSON snapshot; approve sets is_dummy=False and approved_by; versions never decrease; a mechanic cannot approve their own submission even if they are also a reviewer (two-person rule, configurable setting for solo dev: ALLOW_SELF_APPROVAL default False in production).

Tests: every legal and illegal transition, role checks, snapshot content, revision apply atomicity (failure rolls back), live content unchanged until approval, self-approval blocked. Acceptance: pytest green.
```

## Prompt 20: Mechanic registration, verification and content API (Steps 7.1, 7.2)

```
Read AGENTS.md and docs/versioning-design.md. Build the mechanic backend.

- POST /api/mechanic/register/: creates User(role=mechanic) + MechanicProfile(is_verified=False). Applies the auth throttle. Mechanic can GET/PATCH their profile but not is_verified or honesty_score.
- Unverified mechanics may draft and use the simulator but may NOT submit for review (403 with a clear message). Admin verifies via admin action "Verify mechanic".
- Under /api/mechanic/ (IsMechanic only): CRUD for flows composed of Symptom, Cause, CauseSymptomLink, SelfCheck, RepairCost, Question+AnswerOption, restricted to content the mechanic created or that is ai_draft/draft and unassigned. Writes ALWAYS save status draft or submitted, never approved/published (reject attempts with 400 and test it). Strength labels only (weight is derived). Costs per city with parts and labour separate and last_verified date entered by the mechanic.
- Serializer validation mirrors import_flow rules (question needs >=2 options with one unsure, parts_min <= parts_max, prior 0 to 1).
- POST /api/mechanic/items/{type}/{id}/submit/ uses workflow.submit.
- GET /api/mechanic/dashboard/: counts by status, the mechanic's items, and a progress figure per flow (percentage of required pieces present).
- Ownership of ai_draft items: a "claim" action assigns created_by when a mechanic starts editing an AI draft (so approval is traceable).

Permission tests: normal user and reviewer get 403 on /mechanic/ write endpoints as appropriate; mechanic A cannot edit mechanic B's items; mechanic cannot publish or approve; unverified cannot submit. Acceptance: pytest green, OpenAPI updated.
```

## Prompt 21: Mechanic wizard in React (Steps 7.2, 7.7)

```
Read AGENTS.md. Build the mechanic area under /mechanic (guarded by role) in frontend/src/pages/mechanic.

- Dashboard: progress per flow, items by status, "continue where you left off".
- Wizard with the 8 steps from guide Step 7.2 / Project Doc 7.2: 1 car models + problem, 2 symptoms in customer wording (en + Roman Urdu; mark safety-critical with an explanation of what that triggers), 3 causes, 4 link symptoms to causes using four big buttons Always/Often/Sometimes/Rarely (no numbers anywhere), 5 self-check + tools + difficulty, 6 costs per city parts and labour with a last-verified date, 7 red-flag warnings, 8 review summary + test simulator link + submit.
- Autosave drafts per step; every step finishes in under 5 minutes of typing; large inputs and tap targets; works at 360px; resumable. Show a progress bar. Plain language, no jargon like "prior" (call it "how common is this problem", High/Medium/Low mapped to priors in one place, documented).
- Voice note: add an optional record button using MediaRecorder that uploads to a stub endpoint (store as media for later transcription; clearly behind a feature flag, default off).
- Validation errors from the API shown next to the field.

Tests for the strength selector and autosave. Acceptance: lint, test, build green. Report anything you stubbed.
```

## Prompt 22: Test simulator and AI-draft review (Steps 7.3, 7.4)

```
Read AGENTS.md. Backend: implement knowledge/simulator.py and endpoints under /api/mechanic/simulator/ (IsMechanic or reviewer).

- simulate(car_model_id, category_id, answers, include_drafts=True): reuse engine functions WITHOUT mutating settings globally (refactor engine to accept an `include_drafts` parameter / explicit visibility function instead of toggling ALLOW_DRAFT_CONTENT, which is not thread-safe). Does not persist sessions or pollute analytics (flag simulated runs).
- Returns the ranked causes, the evidence supporting each, the next question, and which link weights contributed so the UI can say "this looks wrong" and jump to the top cause's links.
- Also: GET /api/mechanic/ai-drafts/ listing ai_draft items for the mechanic's specialisation/car models with Approve as is (moves to submitted with a snapshot and the mechanic recorded as author), Edit (claim) and Reject (marks rejected with a reason) actions.

Frontend: /mechanic/simulator: pick car and problem, answer as a fake customer in the same QuestionCard UI, see ranked result with the "why", and a prominent "This looks wrong" button that opens the top cause's symptom-link editor. /mechanic/ai-drafts: list with the three buttons.

Tests: simulator never writes DiagnosisSession rows; simulated results equal real engine output for the same answers; AI-draft actions respect ownership and status. Acceptance: pytest, lint, build green.
```

## Prompt 23: Reviewer screens and approval API (Step 7.5)

```
Read AGENTS.md and docs/versioning-design.md. Build the reviewer side.

Backend (IsReviewer): GET /api/review/queue/ (submitted/under_review items and revisions, filter by type, flow, mechanic), GET /api/review/items/{type}/{id}/ (current published payload, proposed payload, field-level diff, history of ContentReview rows), POST .../start/, .../approve/, .../return/ (comment required), .../reject/ (comment required), .../publish/. Add "conflict" support: when two submitted revisions touch the same cause/link, return both side by side and require a resolution comment on approve (Step 10.3: keep both opinions, ask a third, or choose the more cautious option).

Frontend /review: queue list, side-by-side diff view (readable at 360px by stacking), Approve / Return with comment / Reject, history timeline showing who did what and when, and a "safety-critical" badge so safety symptoms are always reviewed first (sort them to the top).

Tests: only reviewers; return needs comment; diff correctness; conflict resolution recorded; history complete. Acceptance: pytest, lint, build green.
```

## Prompt 24: Launch gate (Step 7.6)

```
Read AGENTS.md and docs/ (Project Doc 4.1, guide Step 7.6 and 10.4). Create `python manage.py launch_check` and a reviewer-only page /review/launch-gate and endpoint GET /api/review/launch-gate/.

Checks, each with pass/fail and the list of offending objects:
a) Per category in scope: at least 1 published, non-dummy flow (symptoms + causes + questions + links) and a configurable minimum of N flows overall (default 3).
b) No Symptom, Cause, Question, SelfCheck, RepairCost, WarningLight with is_dummy=True or status in (ai_draft, draft) that is reachable by users (i.e. attached to a published flow).
c) Every safety-critical symptom has status published and has a ContentReview approved by a reviewer who is a verified mechanic or admin.
d) Every published RepairCost has last_verified within the last 120 days.
e) Every published question has >=2 options with exactly one unsure; every cause has at least one link and at least one cost row.
f) Settings sanity when run with --production: DEBUG False, ALLOW_DRAFT_CONTENT False, SECRET_KEY not default, ALLOWED_HOSTS set.
Exit code 1 if anything fails. Wire the same function into the deployment checklist (Prompt 31) so deploy is blocked on failure. Tests for each failing condition. Acceptance: pytest green.
```

---

# FEEDBACK, SHARING, ANALYTICS

## Prompt 25: Outcome capture UI and history (Steps 8.1, FR-4)

```
Read AGENTS.md. The outcome endpoint exists. Build:
- /outcome/:sessionId form: pick the actual cause from the session's ranked list or "Something else" (free text), actual cost in PKR (optional), which mechanic type (free text optional, never published), helpful vote, notes. Mobile friendly.
- /history page: past diagnoses per car (new GET /api/sessions/?car= with pagination), status chips, link to result or to the outcome form if completed with no outcome.
- Backend: Celery task `send_outcome_reminder(session_id)` scheduled 24 h after completion (countdown) that creates an in-app Notification row (new small model: user, kind, payload, read_at) and, behind a feature flag, a push/WhatsApp stub interface. GET /api/notifications/ and POST .../read/. Frontend shows an unread badge in the header.
Tests for the reminder scheduling (use CELERY_TASK_ALWAYS_EAGER in tests), outcome idempotency, history pagination and ownership. Acceptance: pytest, lint, build green.
```

## Prompt 26: Analytics events and admin dashboard (Steps 8.3, 8.4)

```
Read AGENTS.md. Build a privacy-minimal first-party analytics layer.

- New app `analytics` with Event(user nullable, session nullable, name, props JSON, created_at; index on name+created_at). POST /api/events/ for the frontend (whitelisted event names only: session_started, question_answered, result_viewed, share_clicked, outcome_submitted, scam_check_run; reject others; throttle). Server-side emits for session_started/completed too. No free text, phone numbers or exact locations in props.
- Celery beat task nightly rollup into DailyStat (date, metric, dimension, value).
- Reviewer/admin endpoint GET /api/admin/analytics/ returning: sessions per day, top categories, drop-off by question (answered vs asked-then-abandoned), average questions per session, share rate, outcome rate, top-3 accuracy (actual_cause within top 3 SessionResult), cost-range hit rate (actual_cost within shown range), safety-stop count. Define each metric precisely in docs/metrics.md with the SQL/ORM logic.
- Minimal React dashboard at /admin/analytics with a few simple charts (use a lightweight library or plain SVG; keep bundle small, lazy-loaded).
Tests with seeded sessions proving each metric calculation. Acceptance: pytest, lint, build green.
```

---

# QUALITY, SECURITY, DEPLOYMENT

## Prompt 27: Test suite, scenario sheet, CI (Steps 9.1, 9.2)

```
Read AGENTS.md. Do three things.

1. Gap analysis: run `pytest --cov=. --cov-report=term-missing` and list untested engine, scamshield, workflow and permission code. Write the missing tests, prioritising: scoring, safety rules, next-question, Scam Shield, every status transition, and a PERMISSION MATRIX test that, for every endpoint in the OpenAPI schema, asserts the expected status for anonymous / user / mechanic / reviewer / admin (generate the matrix from the schema so new endpoints cannot be forgotten).
2. Scenario harness: `python manage.py export_scenarios` writes a CSV (scenario, car, answers, app top-3 with bands, blank "mechanic verdict" and "comment" columns) from backend/scenarios/*.yaml; `pytest -m scenarios` runs the same YAML as automated assertions (expected top cause, or acceptable set). Create 3 example scenarios per the guide's table (Alto slow crank + dim lights; Corolla no sound, dash off; Cultus cranks but won't fire, fuel smell -> safety stop).
3. GitHub Actions: .github/workflows/ci.yml running on push/PR: backend (postgres service, pip cache, migrations check `makemigrations --check --dry-run`, pytest with coverage threshold 80% on engine/scamshield/workflow modules) and frontend (npm ci, lint, test, build). Fail on any warning from `manage.py check --deploy` with the production env.

Acceptance: CI config passes `act` or at least YAML lint; local pytest green; report coverage numbers.
```

## Prompt 28: Security hardening (Step 9.4)

```
Read AGENTS.md. Audit and harden; produce docs/security-review.md with findings and fixes.

Check and fix: throttle scopes applied to login, register, free-text, diagnosis, scam-check, events; JWT lifetimes and refresh rotation + blacklist (add rest_framework_simplejwt.token_blacklist and logout endpoint); input validation on every serializer (lengths, ranges, enum checks); object-level permission on EVERY queryset (IDOR sweep: try each detail endpoint as another user); mass-assignment (no serializer exposes role, is_verified, status transitions, weight, approved_by, is_dummy to non-staff); CORS limited to configured origins; production security settings (SECURE_SSL_REDIRECT, HSTS, secure cookies, X-Content-Type-Options, referrer policy, CSP header via middleware or nginx note); admin hardening notes (separate admin URL via env, strong passwords, mention 2FA with django-otp and implement it for staff if time allows); upload endpoints (type and size limits); secrets scan (no keys in git history or code; add pre-commit with gitleaks config); dependency audit (`pip-audit`, `npm audit`); prompt-injection review of nlu.py; logging that never records passwords, tokens or free text.

Add tests for the IDOR sweep and mass-assignment. Acceptance: pytest green; security-review.md lists each finding as fixed / accepted-with-reason.
```

## Prompt 29: Docker, production settings, CI/CD, backups (Phase 11)

```
Read AGENTS.md and docs/ (guide Phase 11). Create deployment assets.

- backend/Dockerfile (multi-stage, non-root user, gunicorn), frontend build stage, nginx config serving the React build with SPA fallback and proxying /api and /static, long cache for hashed assets, no cache for index.html and the service worker, gzip/brotli, security headers.
- docker-compose.yml (db postgres:16 with healthcheck, redis:7, api, worker, beat, web) + docker-compose.override.yml for local dev. Secrets only via env_file / env vars, .env.production.example with every variable and no values.
- config/settings production profile via env (DEBUG False, ALLOWED_HOSTS, CSRF_TRUSTED_ORIGINS, ALLOW_DRAFT_CONTENT=False forced when DEBUG is False, STATIC_ROOT + whitenoise or nginx static, Sentry init when SENTRY_DSN set, structured logging).
- Entrypoint script: wait for db, migrate, collectstatic, then `python manage.py launch_check --production` as a deploy gate controlled by RUN_LAUNCH_CHECK (default 1).
- scripts/backup.sh (pg_dump to a configurable S3-compatible bucket, daily, retention policy) and scripts/restore.sh with a documented restore drill in docs/runbook.md, including recovery-time target (NFR-14: under 4 hours).
- GitHub Actions deploy workflow: on merge to main run tests, build and push images, SSH deploy (or Render/Railway notes), with the launch gate as a blocking step.
- docs/runbook.md: first deploy, rollback, rotating secrets, restoring a backup, adding a mechanic, running launch_check.
Do not hard-code domains or credentials. Acceptance: `docker compose config` validates; images build; `docker compose up` brings up a working stack locally (report what you ran).
```

---

# Reusable prompts

## Audit prompt (run after each phase, fresh session)

```
Read AGENTS.md and docs/. You are a skeptical reviewer, not the author. Review the changes on branch <BRANCH> against main for: (1) violations of the Golden rules in AGENTS.md, (2) bugs and race conditions, (3) missing permission checks or fields that leak (weights, implies_symptom, role, status), (4) queries inside loops, (5) spec drift from docs/, (6) missing or weak tests. Do not edit code. Output a ranked list: severity, file:line, what is wrong, how to reproduce or a failing test sketch. If you find nothing in a category, say so explicitly.
```

## Bug-fix prompt

```
Read AGENTS.md. Bug: <what you did, what you expected, what happened, traceback>. First write a failing test that reproduces it. Show me the test failing. Then make the smallest fix, show it passing, and run the full suite. Do not refactor anything else.
```

## "Spec question" prompt (when the guide is ambiguous)

```
Read AGENTS.md and docs/. Do not write code yet. Question: <ambiguity>. List the 2 or 3 reasonable interpretations, the consequences of each for the schema and API, and which one you recommend and why. Wait for my decision.
```

---

# Appendix: improved LLM drafting prompt (Step 3.2, for your chat LLM, not Codex)

```
You are helping build a car diagnosis app for Pakistan. Create a diagnostic flow for:
CATEGORY: "<Car won't start | Overheating | AC not cooling>"
CARS: <e.g. Suzuki Alto (660cc, EFI), Suzuki Cultus (1000cc)>

Return ONLY valid JSON, no commentary, in exactly this schema:
<paste the guide Step 3.1 JSON, with the questions block extended so every option has
 "implies": "<symptom key>" or null, and exactly one option has "unsure": true>

Hard rules:
- 6 to 10 symptoms, 8 to 12 causes, 6 to 10 questions. Every question has 3 to 5 options, exactly one with "unsure": true, and at least one option with implies = a symptom key and one negative option with implies = null and no "unsure".
- Every symptom key used in links and questions must be defined in "symptoms". Snake_case keys.
- strength must be one of: always, often, sometimes, rarely.
- Cause priors are your honest guess at how common each cause is for this problem on these cars in Pakistan; they should roughly sum to 1.0.
- Mark safety-critical symptoms with "safety": true (fuel smell, smoke, steam with gauge in red, brake loss, burning smell, etc.).
- Include Pakistan-specific causes: bad petrol, summer battery failure, CNG kit issues, dust-clogged filters, poor-quality local parts, water in fuel after rain.
- Costs: PKR ranges [min, max] for parts and labour separately for Lahore, Karachi and Islamabad. These are rough estimates and will be verified by mechanics.
- Roman Urdu written the way ordinary customers speak ("gaari jhatke deti hai"), not formal Urdu transliteration.
- Self-checks must be safe for a non-expert at home. Never suggest anything involving the fuel system while the engine is hot, opening a hot radiator cap, or working under a car on a jack.
After the JSON, add nothing.
```