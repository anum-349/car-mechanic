# Mechanic wizard data mapping

The wizard uses plain language for cause frequency. The single mapping in `frontend/src/pages/mechanic/wizardModel.js` converts High / Medium / Low to importer priors of `0.6 / 0.3 / 0.1`. These are initial data weights, not percentages displayed to mechanics.

Symptom-to-cause strength uses the backend's named values Always, Often, Sometimes, Rarely. The backend derives numeric weights; the UI never displays those weights.

## Integration gaps

The current mechanic flow API does not accept red-flag warning records or the explanation attached to a safety-critical symptom, so those details remain in the browser's resumable draft. The simulator and voice-note upload endpoints are also not implemented. Voice recording is hidden by default; set `VITE_MECHANIC_VOICE_NOTES=true` only when a compatible upload endpoint is available.
