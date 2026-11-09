# Agri Mitra — AI-Powered Smart Agriculture and Plant Health Monitoring System

Static HTML, CSS, and browser JavaScript for the Agri Mitra farmer experience. No package installation or build step is required.

## Run the frontend

Serve this folder from a local static web server (for example, VS Code Live Server or `py -m http.server 5500 --bind 127.0.0.1`) and open `http://127.0.0.1:5500/`. Sign in with a farmer account from the backend, or register one from the app. The API must be running and its CORS settings must allow the frontend origin. Using a local web server is necessary because browsers do not allow API calls reliably from a `file://` page.

The Admin Portal login uses the backend's separate administrator accounts. Dashboard totals, Users/Farmers, Crops, Disease Records, Scan Records, AI Queries, Notifications, and Reports load from authenticated admin API endpoints and refresh on demand or every minute. Records that belong to farmers include their registered user details. Passwords are never returned to the admin UI.

Farmer sign-in accepts the email address or mobile number saved on the account, together with the same password. Admin sign-in continues to use the administrator email and password.

From the repository root, create the first admin after the database is running and migrated:

```powershell
Set-Location D:\Agri_netraa\backend\backend
.\.venv\Scripts\python.exe create_admin.py
```

The script prompts for the admin name, email, and password without echoing the password. Farmers and admins use separate account tables and sign-in flows. Admins can reset a farmer's password from **Users/Farmers → Reset password**; this is audit logged and signs out the farmer's existing sessions. Farmers can change their own password in **Settings → Change password** after entering their current password. Passwords are stored as hashes and cannot be displayed or recovered. Email/SMS self-service recovery is not configured; farmers who cannot sign in need an administrator to reset their password. After this auth update is deployed, farmers may need to sign in again once.

## Disease scanner API

The scanner sends a multipart `POST` request to `/api/species/predict` by default. Set `SCAN_ENDPOINT` in `config.js` to `"disease"` to call `/api/disease/predict` instead. The multipart image field defaults to `file` and can be changed with `FILE_FIELD_NAME` to match the FastAPI route.

Edit these settings in `config.js`:

- `API_BASE_URL`: defaults to `http://127.0.0.1:8000` for the local FastAPI server; leave empty for a same-origin deployment.
- `SCAN_ENDPOINT`: `species` (default) or `disease`.
- `SPECIES_PREDICT_PATH` and `DISEASE_PREDICT_PATH`: backend route paths.
- `FILE_FIELD_NAME`: multipart field name expected by the backend.
- `CONFIDENCE_THRESHOLD`: value from 0 to 1; the current default is `0.65`. Lower-scoring predictions are shown as unverified rather than presented as a plant or disease label. Tune this threshold against validation data for the configured model.

The backend should allow the frontend origin through FastAPI CORS when they run on different origins. The frontend does not set `Content-Type` for multipart requests; the browser adds the correct boundary.

The scanner accepts JSON containing `crop`, `disease`, `confidence`, `model`, and `model_version`, with optional `recommendation`, `is_confident`, `low_confidence`, `human_detected`, `message`, and `scan_id`. A confidence such as `0.94` or `94%` is supported. Low-confidence results are shown as unverified. The species API uses an OpenCV face detector before the plant classifier and returns `human_detected` for a visible face. The frontend does not invent a disease result, treatment recommendation, or thermal image.

The Crop Scanner and AI Assistant have their own camera and image upload controls. The scanner can show a live camera preview and capture a leaf photo without leaving the page. Camera capture needs browser camera permission and a secure origin (localhost is allowed for local development; deployed sites need HTTPS). It calls the configured image endpoint. The AI Assistant displays the model label, confidence, and top predictions without navigating to the standalone scanner. The default `species` endpoint is a crop/species classifier; it does not identify disease symptoms. To use disease detection, install/configure a trained disease model and set `SCAN_ENDPOINT` to `"disease"`.

## Analysis response behavior

`POST /api/species/predict` preserves its existing `status`, `scan_id`, and `prediction` fields and adds a structured `analysis` object. The `analysis` object separates plant identity and raw class scores, disease prediction and raw score, leaf health, and fertilizer recommendation evidence. A raw classifier score is not a calibrated probability. Predictions below the configured threshold are shown as uncertain with the top model candidate clearly labeled. If the species detector finds a person, the result is **Human detected**.

The current checkout has an eight-class EfficientNetB0 species model. It does not have an installed disease model with usable labels, a validated leaf-health model or annotated health dataset, or reviewed crop-specific fertilizer guidance. Those analysis fields are therefore reported as unavailable or insufficient with null scores, rates, and concentrations; the app does not invent them.

## Weather and AI assistant

After sign-in, the dashboard can search a village or town, or use browser device location. It displays current conditions, the previous seven days, and the next seven days. Weather refreshes when the dashboard session starts, every 30 minutes while the page is open, and from the **Refresh** button. Open-Meteo provides geocoding and weather data without an API key.

The dashboard weather briefing and AI Assistant use the authenticated `POST /api/ai/chat` Ollama endpoint. `GET /api/ai/health` reports whether the local Ollama service and configured model are available. The backend supplies recent weather saved through the existing Open-Meteo integration, owner-scoped crop/farm context, and a saved image result when relevant. Chat sessions continue to use `/api/chat/history`; messages carry recent history for follow-up questions. Failures appear in the chat with a Retry button.

Install Ollama and pull the backend's configured model (`qwen2.5:3b` by default). Optional current-information search uses Tavily with a key stored only in the backend `.env`; browser code contains no provider credentials. The image itself is sent to the existing species/disease prediction endpoint; AI explanations reference the owner-scoped saved scan ID and prediction. Live weather is not invented, marketplace product prices are not presented as mandi prices, and disease text is not treated as a confirmed diagnosis. When Ollama is offline or its model is missing, the API reports a clear service error instead of returning a fabricated answer. See [OLLAMA_CHATBOT.md](../backend/backend/OLLAMA_CHATBOT.md) for setup, PowerShell commands, sample requests, and limits.

## Other screens and images

Weather, farmer login and registration, crop records, disease/species scans, profile photos, and AI chat use authenticated backend routes. Market products, suppliers/buyers, farmer listings, and order requests also use backend marketplace records. AI chat history stores conversations and verified image-analysis summaries under the signed-in farmer's account. Browser camera capture requires permission and works on localhost or an HTTPS deployment.

To change the existing crop photography, edit the `image` URLs in the `mockData.crops` entries in `app.js`. The remaining page artwork and photo references are in `app.js` and `styles.css`; they can be replaced with your own image URLs or local image paths.


## Image analysis result fields

The existing species endpoint returns its original prediction fields plus an additive `analysis` object. The result cards keep species and disease model scores separate from leaf health and fertilizer evidence. Classifier scores are shown as uncalibrated model scores, not calibrated probabilities. In this checkout the installed EfficientNetB0 species model has eight classes; a disease model with usable classes, annotated leaf-health data, and reviewed crop-specific fertilizer sources are not present. The interface therefore reports health as unavailable, disease analysis as unavailable when the model cannot run, and fertilizer evidence as insufficient. It does not invent health percentages, product names, rates, or concentrations. Human-face detection keeps its existing explicit non-crop result.


## Leaf water status

The image-analysis result includes a separate **Leaf Water Status** section. It reports relative water content (RWC) only when a defined measurement and source are supplied; model confidence and disease confidence are never converted to a water percentage. The current repository has no RWC or visual water-stress model and no connected soil-moisture sensor, so leaf water content is unavailable, visual water stress is not assessed, and soil moisture is shown as not measured. A leaf photo cannot provide a soil reading. Use a calibrated soil sensor or field check and consider crop stage, recent rain/irrigation, and other causes before changing irrigation. No database migration is required for the unavailable-status fields.
