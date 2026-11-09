# Agri Mitra API

The API package is under `agrinetra/`. Run database migrations with Alembic before starting the server. Never point the FastAPI process at the original training datasets. Technical database, package, route, and model artifact names remain unchanged for compatibility with the existing application.


## Agri Mitra plant-analysis capabilities and limits

The existing species service uses the exported Keras Functional model `ml_models/agrinetra_efficientnet_species_final.keras`: an EfficientNetB0 feature extractor followed by global average pooling, dropout, and an eight-class softmax head. Its class map is `ml_models/species_class_names.json` (Alstonia Scholaris, Arjun, Bael, Basil, Guava, Jamun, Pomegranate, and Pongamia Pinnata). These softmax values are raw model scores; the model has no calibration evidence in this checkout, so the API and UI do not call them probabilities. The low-confidence threshold is an existing setting and is not a validated accuracy claim.

The separate disease model is unavailable: its model artifact is not installed and its configured class map has zero classes. There is no healthy/unhealthy model, leaf lesion segmentation data, or annotated leaf-health dataset. The workspace also has no relative-water-content labels, water-stress model, or soil/leaf sensor integration. The additive `analysis.water_status` response therefore returns null water-content and confidence values, an uncertain/not-assessed visual status, and soil moisture as not measured. An RGB image is not used to estimate RWC or soil moisture. The species classifier cannot support a leaf-health percentage, so the new additive analysis response returns `health.score_percent: null` and `assessment_unavailable`. No reviewed crop-, growth-stage-, and soil-specific fertilizer source is bundled; the recommendation response therefore reports `evidence_quality: insufficient`, null product/rate/concentration/confidence, and requests field/soil checks. Existing disease-table guidance remains informational and is not presented as a fertilizer rate.

`POST /api/species/predict` and `POST /api/disease/predict` retain their existing fields and add an `analysis` object with separate plant, disease, health, water-status, and recommendation sections. Existing scan storage, authentication, history, camera upload, and chat endpoints remain in use. The chat system prompt receives explicit rules not to reinterpret model scores as health, water status, or treatment confidence and uses verified saved scan records when a scan ID is supplied.

## Native PostgreSQL on Windows (safe Docker-to-local transition)

This project reads `DATABASE_URL` from this folder's `.env`. Its SQLAlchemy URL uses Psycopg 3 (`postgresql+psycopg`). The checked-in example targets the detected native PostgreSQL port `5433` and contains only a password placeholder; the existing `.env` is intentionally not changed by setup. In the inspected checkout, that `.env` still targets Docker at `localhost:5432`, while PostgreSQL 18 service `postgresql-x64-18` is running natively at port `5433`. Docker Compose is PostgreSQL 16.15, database and role `agrinetra`, using named volume `backend_agrinetra_pgdata`. The prior `agrinetra_user` error does not match the role configured by this project.

**Migration checkpoint (2026-10-28):** Docker container `agrinetra-postgres` is healthy. A custom-format logical backup was created and successfully read by `pg_restore --list`: `backend/backups/agrinetra-docker-20261028-151336.dump` (86,129 bytes; SHA-256 `C447D28578B3ABAEC3D15BD7E8422DF63BE24DACE836CC0E8EE71C06C59FE9F6`). The source database is UTF8, runs PostgreSQL 16.15, and is at Alembic revision `0005_market_contacts` with 18 public tables. The backup and original Docker volume remain untouched. The native service is available on 5433, but passwordless administrator catalog access failed and the current app credentials were not accepted there, so no role/database was changed and no restore has been attempted. After native access is authorized, compare the restored tables and counts before switching `.env`.

Use the root VS Code tasks **PostgreSQL: Check status**, **PostgreSQL: Start native service**, and **PostgreSQL: Test Agri Mitra connection**. The status and start scripts inspect the actual Windows service and its `postgresql.conf`; they never start Docker, change service startup mode, print a password, or start a second instance. `psql` is discovered from PATH or the installed PostgreSQL folders. A database password is entered only at psql's hidden prompt.

### Preserve and migrate the current Docker data

The current container and volume have now been inspected and the backup above is verified. When repeating this procedure, start Docker Desktop temporarily only when ready to export. First inspect the existing resources from `backend\backend`:

```powershell
Set-Location D:\Agri_netraa\backend\backend
docker compose ps -a
docker volume ls
docker compose config --volumes
```

Confirm the existing PostgreSQL container and named volume before starting anything. If they are present, start only that existing Compose service with `docker compose up -d postgres`, wait for it to become healthy using `docker compose ps`, then run the root task **PostgreSQL: Back up existing Docker database**, or:

```powershell
Set-Location D:\Agri_netraa
.\scripts\postgres-backup-compose.ps1
```

The backup script streams a custom-format `pg_dump` to `backend\backups`, checks its exit code, file size, and readability with `pg_restore --list`, and prints a SHA-256 hash. Backup files are Git-ignored because they may contain farmer and authentication data. The script does not stop/delete the container or modify its volume. If Docker or the existing volume cannot be found, stop: this checkout cannot recover data from an inaccessible container. **Never use `docker compose down -v` or drop the original database or volume.**

Restore only after the native service is running. Open native `psql` as the PostgreSQL administrator (the role is environment-specific):

```powershell
psql -X -h 127.0.0.1 -p 5433 -U postgres -d postgres -W
```

At the `psql` prompt, inspect roles and databases first:

```sql
SELECT rolname FROM pg_roles ORDER BY rolname;
\l
```

If role `agrinetra` is absent, create that dedicated app role, then set its password using psql's hidden prompt. If it exists, do not create a duplicate; use `\password agrinetra` only if you have permission and need to set a known application password. Do not use `postgres` as the app login. Choose a new restore database name that does not already exist (the example is `agrinetra_import`):

```sql
CREATE ROLE agrinetra LOGIN;
\password agrinetra
CREATE DATABASE agrinetra_import OWNER agrinetra ENCODING 'UTF8';
\q
```

Run `CREATE ROLE` only when the role query showed it was missing, and run `CREATE DATABASE` only when `\l` showed the target name was unused. Otherwise choose another unused target name. Restore into that separate target (never use `--clean`):

```powershell
pg_restore --exit-on-error -h 127.0.0.1 -p 5433 -U agrinetra -d agrinetra_import -W D:\Agri_netraa\backend\backups\YOUR_VERIFIED_DUMP.dump
```

Verify the restored schema and Alembic revision before changing `.env`:

```powershell
psql -X -h 127.0.0.1 -p 5433 -U agrinetra -d agrinetra_import -W
```

```sql
\dt
SELECT version_num FROM alembic_version;
SELECT format('SELECT %L AS table_name, count(*) AS rows FROM %I.%I;', schemaname, tablename)
FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename \gexec
\q
```

Compare the table list, migration revision, and counts with the Docker source before switching. To change only the existing `.env` database URL after a verified restore, run from the project root:

```powershell
Set-Location D:\Agri_netraa
.\scripts\postgres-set-app-url.ps1 -BackupVerified -Database agrinetra_import
```

The script asks for the native role password without echo, URL-encodes special characters, and changes only `DATABASE_URL`; it does not print the URL. Then run **PostgreSQL: Test Agri Mitra connection**, inspect `alembic current`, and only if the restored schema needs newer migrations run `alembic upgrade head` against this verified native target. The original Docker database remains the fallback. This transition is not complete until backup verification, restore verification, app authentication, and migration checks succeed.

### Safe PostgreSQL administration

Use the actual detected service port (`5433` on the inspected machine). These commands prompt for a password when needed and do not put one on the command line:

```powershell
psql -X -h 127.0.0.1 -p 5433 -U agrinetra -d agrinetra_import -W
```

At the psql prompt: `\l` lists databases, `\du` lists roles, `\dt` lists tables, `SELECT version();` reports the server version, and `SELECT version_num FROM alembic_version;` reports the migration revision. In PowerShell, check a port with `Test-NetConnection 127.0.0.1 -Port 5433`; check service state with `Get-Service postgresql*`. Use `scripts\postgres-status.ps1` for a safe summary. To inspect PostgreSQL listening ports, use `Get-NetTCPConnection -State Listen -LocalPort 5432,5433 -ErrorAction SilentlyContinue`.

To back up the native target later, use `pg_dump -Fc -h 127.0.0.1 -p 5433 -U agrinetra -d agrinetra_import -W -f D:\Agri_netraa\backend\backups\agrinetra-native.dump`; verify with `pg_restore --list` before relying on it. Restore into a separate, unused database and compare tables/counts before switching. For a missing role or authentication failure, inspect `\du`, verify the configured role/database/port without sharing the URL, and use an administrator account to set credentials with `\password role_name`; do not reset the PostgreSQL administrator or grant broad privileges as a troubleshooting shortcut.

## Crop image scanning

Install the optional inference dependencies from `backend/backend` before starting the API:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-ml.txt
```

The species scanner uses OpenCV face detection to reject photos containing a visible human face before running the plant-only classifier. These images return a `human_detected` result and are shown as invalid crop photos in the scanner.

## Weather and AI chatbot setup

The authenticated weather API uses Open-Meteo for geocoding and forecast data. Weather requests are recorded per farmer in `weather_records`; the chatbot uses a reading only when it was saved within the last 24 hours and states its recorded time. No live weather reading means the assistant must say it cannot retrieve current conditions.

The Agri Mitra assistant calls authenticated `POST /api/ai/chat` using the local Ollama HTTP API and the `qwen2.5:3b` model by default. `GET /api/ai/health` checks that Ollama is reachable and the configured model is installed. Optional Tavily search adds verified source URLs to questions that need current information. See [OLLAMA_CHATBOT.md](OLLAMA_CHATBOT.md) for setup, PowerShell commands, endpoint examples, and limits. No Gemini key or cloud LLM key is sent to the frontend.

Install Ollama, pull the model, then add these settings to `backend/backend/.env`. Preserve any existing `.env` values and never copy the example over an existing file:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen2.5:3b
OLLAMA_TIMEOUT_SECONDS=90
WEB_SEARCH_ENABLED=false
TAVILY_API_KEY=
AI_MAX_REQUEST_BYTES=32768
```

The legacy authenticated `POST /api/chat` route remains available with its existing OpenAI-compatible configuration. Its settings do not affect `/api/ai/chat`.

```env
CHATBOT_PROVIDER=openai
OPENAI_API_KEY=your-backend-only-api-key
OPENAI_MODEL=your-enabled-model-id
OPENAI_BASE_URL=
CHATBOT_TIMEOUT_SECONDS=30
CHATBOT_REQUESTS_PER_MINUTE=20
CHATBOT_HISTORY_MESSAGES=12
AGRI_RAG_ENABLED=false
```

Choose a model enabled for the API project and set its exact model ID in `OPENAI_MODEL`. `OPENAI_BASE_URL` is optional; leave it blank for OpenAI. Existing `CHATBOT_API_KEY`, `CHATBOT_BASE_URL`, and `CHATBOT_MODEL` values are still accepted as legacy aliases. Keep the real `.env` private; only placeholders belong in `.env.example`.

From PowerShell, run the API and frontend in separate terminals:

```powershell
Set-Location D:\Agri_netraa\backend\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

```powershell
Set-Location D:\Agri_netraa\frontend
py -m http.server 5500 --bind 127.0.0.1
```

Open `http://127.0.0.1:5500`. Ensure `USER_FRONTEND_URL` in the backend `.env` includes that exact origin. Run the mocked suite from a third terminal:

```powershell
Set-Location D:\Agri_netraa\backend\backend
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

The chatbot test suite mocks model providers and does not download a model or call Tavily. Live answers require the Ollama desktop service and the configured model to be installed locally. Tavily is optional and is used only when enabled with a backend API key.

Chat sessions and messages use the existing `chat_sessions` and `chat_messages` tables. Only the authenticated owner's recent messages are sent as conversation context. The assistant also receives limited account-owned crop/farm details, verified scan records, and a weather snapshot or public Agri Mitra marketplace products when relevant. Scan IDs are checked against the signed-in user before the result is used. Photos are classified by the existing `/api/species/predict` or `/api/disease/predict` route; the text chatbot receives the saved prediction, not the photo bytes.

`GET /api/chat/status` reports configuration without returning secrets. `GET /api/chat/history` returns only the signed-in user's sessions. `POST /api/chat/scan-result` saves a verified image result into that user's chat history and labels human or uncertain images without presenting them as crop identifications. Requests are limited to 4,000 characters and 20 per account per minute by default. The in-memory rate limiter is for a single development server; production with multiple workers should use a shared rate limiter. Provider errors, timeouts, and rate limits return safe HTTP errors that the UI displays with a retry button.

### Optional agricultural retrieval (RAG)

No reviewed agricultural source documents were present in the project during inspection, so RAG is disabled and no corpus is bundled. To enable it incrementally:

1. Add reviewed ICAR, Krishi Vigyan Kendra, or Karnataka agricultural university material as `.md` or `.txt` files under `backend/backend/knowledge/agriculture/`.
2. Configure `OPENAI_API_KEY` and, if desired, `OPENAI_EMBEDDING_MODEL`.
3. From `backend/backend`, run `python -m agrinetra.services.knowledge_index` to create a local vector index. The command embeds only files in that folder; it does not download or scrape documents.
4. Set `AGRI_RAG_ENABLED=true` and restart the API. Retrieved source names are included with chatbot answers when relevant evidence is used.

RAG is optional: if it is disabled or the index is unavailable, normal chat continues without retrieval. The generated vector index is ignored by Git.

## Marketplace

Admins can publish products through the Products page. Published products are returned by `GET /api/market/products` to signed-in farmers. Farmer crop listings and order requests are stored with the farmer account and visible in the admin Market Listings page. Orders are recorded as pending seller confirmation; this API does not process payments. Apply Alembic migrations before starting the API so the marketplace tables exist.

## Training dataset settings

The admin Settings page displays the model metadata and supported PlantVillage, PlantDoc, and PlantWild dataset adapters. The training pipeline reads labeled class-folder images from the separate training workspace. Dataset archives stay in Drive or Colab; the FastAPI serving process does not upload or train on them.

The compatibility endpoint `POST /api/chat` remains configured through `OPENAI_BASE_URL` only if the provider supports the Responses API. The frontend assistant uses `POST /api/ai/chat` with Ollama. Legacy key/model variable names are still accepted by the compatibility endpoint:

```env
CHATBOT_PROVIDER=openai
CHATBOT_API_KEY=your-provider-key
CHATBOT_BASE_URL=https://your-responses-compatible-provider.example/v1
CHATBOT_MODEL=your-enabled-model
```

Keep provider keys in the backend environment. The frontend calls the backend and does not receive the LLM key. If the provider stays set to `stub`, or the API key/model is missing, `/api/chat` returns a clear configuration error; it does not return canned agricultural advice.

`GET /api/chat/status` reports whether the configured provider has all required LLM settings; it never returns the API key. Farmer password changes use the authenticated `POST /api/auth/change-password` endpoint and require the current password. Passwords remain one-way hashes; there is no endpoint to read a user's password.
