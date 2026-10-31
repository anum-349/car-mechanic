# Gari Check: car owner web app

React + Vite front end for the Django API. Car owners add their car, answer
questions in a chat, and see the likely causes, what to check, and a price
range. It also checks a mechanic's quote, lists mechanics with reviews, and
explains warning lights and scanner codes.

## Run it

1. Start Django on port 8000 (`python manage.py runserver`).
2. In this folder:
   ```
   npm install
   npm run dev
   ```
3. Open http://localhost:5173.

In development, Vite forwards `/api` to Django, so you don't need any CORS setup.

## Demo data

The app needs published knowledge content before a diagnosis can ask anything.
In your Django project folder:

```
python manage.py shell < seed_demo.py
```

(`backend-extras/seed_demo.py` makes user `ali` / `Str0ng!pass99`, Suzuki Alto and
Cultus, a small published flow, a mechanic with a review, a warning light and an
OBD code.) For real content use the Import JSON button in the admin, then move
items through submit, approve and publish.

## Production

Build with `npm run build` and serve `dist/`. Either serve it from the same domain
as the API (simplest), or set `VITE_API_URL=https://api.example.com` at build time
and install `django-cors-headers` on the backend.

## Tests

`npm test` runs the real app in a headless DOM against a **running** Django API
(`VITE_API_URL=http://127.0.0.1:8000 npm test`) using the demo data above. The
tests change data (new sessions, an outcome), so reseed before running again.

## Where things are

| File | What it does |
|---|---|
| `src/api.js` | Every call to the API: token header, error messages, pagination |
| `src/auth.jsx` | Login, register, current user, language (English / Roman Urdu) |
| `src/pages/DiagnosisChat.jsx` | The question and answer conversation |
| `src/components/Results.jsx` | Ranked causes, costs, self-checks, outcome form |
| `src/pages/ScamShield.jsx` | Quote check |
| `src/i18n.js` | Interface text in both languages |
