# Agri Mitra — AI-Powered Smart Agriculture and Plant Health Monitoring System

A FastAPI backend and Google Colab training pipeline for Agri Mitra. PostgreSQL stores application data in one relational database. Farmer and admin accounts use separate tables and login flows. FastAPI only loads an exported model; it never scans or trains on PlantVillage, PlantDoc, or PlantWild. Existing lowercase database/package identifiers, the species model artifact name, and legacy `AgriNetra/` Drive paths are retained so existing data and training artifacts continue to work.

## Included

- Farmer registration/login/profile, farms, crops, disease scans, private scan images, notifications, weather, and chat history APIs.
- Separate admin login and `/api/admin/*` endpoints for dashboard metrics, users, disease analytics, model metadata, and audit logs.
- SQLAlchemy models and Alembic migration for application data.
- Argon2 password hashes, signed JWTs, logout revocation, server-side role checks, and per-user ownership filters.
- Local image storage behind an owner-checked route, with a storage adapter boundary for cloud storage.
- Colab notebook and training code for Drive datasets, manifests, exact duplicate removal, explicit label mapping, deterministic splits, EfficientNetB0 training/evaluation, and export.
- Security tests for cross-user access, admin authorization, and password hash exposure.

The deployed API preserves the existing database, account, weather, market, and scan contracts. The species model is installed; the separate disease model and reviewed disease/fertilizer knowledge corpus are not. The current image-analysis API makes those missing capabilities explicit and does not invent health scores or fertilizer rates.

## Run locally on Windows without Docker

Use the native PostgreSQL Windows service for normal development. The VS Code tasks and PowerShell helpers are in the repository root. They do not start Docker or change Windows service startup settings. PostgreSQL is an independent Windows service, so it persists when VS Code closes.

The inspected development machine has PostgreSQL 18 installed as service `postgresql-x64-18`, running on port `5433`; the project `.env` still points to the Docker PostgreSQL 16 database on port `5432`. The Docker Compose project uses database/role `agrinetra` and named volume `backend_agrinetra_pgdata`. The `.env` must remain on its current target until the database is restored and verified on native PostgreSQL. See `backend/backend/README.md` for the guarded migration steps. Do not run Alembic against a new empty native database to bypass that migration.

Open `D:\Agri_netraa` in VS Code and run **Terminal → Run Task**:

1. `PostgreSQL: Check status`
2. `PostgreSQL: Start native service` if it is stopped (Windows may require an elevated terminal)
3. After the verified data restore and `.env` switch, `PostgreSQL: Test Agri Mitra connection`
4. `Backend: Start FastAPI` and `Frontend: Start local server` in separate terminals

The frontend is at `http://127.0.0.1:5500`; the API docs and health endpoint are at `http://127.0.0.1:8000/docs` and `http://127.0.0.1:8000/health`.

From a first-time setup with no existing `.env`, create one without replacing an existing file:

```powershell
Set-Location D:\Agri_netraa\backend\backend
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Keep `.env` private. Generate a JWT secret with `python -c "import secrets; print(secrets.token_urlsafe(48))"` and put it in `.env` without removing existing AI/weather settings. Run `alembic upgrade head` only after confirming the target database is the intended restored database. Create the first admin with `python create_admin.py`; it requests the password without echoing it.

Farmer flow: call `POST /api/auth/register`, then `POST /api/auth/login`. Send the returned token as `Authorization: Bearer <token>`. Admin flow: call `POST /api/admin/auth/login` with the account created in step 6. Set `USER_FRONTEND_URL` and `ADMIN_FRONTEND_URL` to the exact frontend origins in `.env`.

## Install the trained model for prediction

The species model is already present. The separate disease model is not installed, so `POST /api/disease/predict` returns HTTP 503 until a compatible trained model and non-empty class map are installed.

1. Train and export the model using Colab below.
2. Copy these three files from Drive `AgriNetra/models/` to `backend/ml_models/`: `efficientnetb0_agrinetra_v1.keras`, `class_labels_v1.json`, and `model_metadata_v1.json`.
3. From `backend`, install the optional inference runtime: `pip install -r requirements-ml.txt`.
4. Restart Uvicorn. `/health` and `/api/admin/model` report readiness.

Local uploads are stored under `backend/uploads/`; the API only returns an image after checking the scan owner. In production use TLS, a strong managed JWT secret, managed PostgreSQL with backups, and a cloud object-storage adapter.

## Train in Google Colab

1. In Google Drive create `MyDrive/AgriNetra/datasets/PlantVillage`, `PlantDoc`, and `PlantWild`. Keep original images in Drive. Included loaders expect class-folder layouts. If a dataset's labels live in a CSV file, adapt its loader in `training/datasets/`.
2. Extract the ZIP on your computer. In Colab choose **File → Open notebook → Upload** and select `AgriNetra/training/AgriNetra_Training.ipynb`. In the notebook, upload `AgriNetra_Backend.zip` to the Colab session using the Files pane; the notebook extracts the code into `/content/AgriNetra`.
3. Run the notebook cells. It mounts Drive and creates `processed/`, `models/`, and `reports/` there.
4. Review `/content/AgriNetra/training/datasets/label_map.json` before training. Add only verified mappings. A key looks like `PlantVillage::Tomato___Early_blight`; values include `canonical_class`, `crop`, `disease`, and `healthy`. Unmapped labels remain dataset-specific, so names are never merged just because they look similar.
5. Run training. The manifest goes to `processed/standardized_dataset.csv`; model artifacts go to `models/`; metrics and plots go to `reports/`.
6. Copy the three model artifacts described above into `backend/ml_models/`.

Images are verified before manifest inclusion. Byte-identical images are removed before splitting. Splits are deterministic per class: 80/10/10 where a class has enough samples; classes with fewer than three unique files remain in training only. Augmentation applies to training batches only.

## Route groups

- Farmer auth/profile: `/api/auth/*`, `/api/users/me`
- Farms/crops: `/api/farms/*`, `/api/crops/*`
- Disease: `POST /api/disease/predict`, `/api/disease/history*`
- Weather/notifications/chat: `/api/weather`, `/api/notifications*`, `/api/chat*`
- Admin: `/api/admin/auth/login`, `/api/admin/dashboard`, `/api/admin/users*`, `/api/admin/disease-analytics`, `/api/admin/model*`, `/api/admin/audit-logs`

Open `/docs` for request/response schemas.

## Run security tests

From `backend` with the virtual environment active:

```powershell
pip install -r requirements-dev.txt
pytest
```

The AI chatbot uses the official async OpenAI Responses API when `CHATBOT_PROVIDER=openai`, `OPENAI_API_KEY`, and `OPENAI_MODEL` are set in `backend/backend/.env`. Create the key in [OpenAI API key settings](https://platform.openai.com/api-keys); the full value is displayed only once. Save it in the backend `.env`, and update only those chatbot settings if `.env` already exists. The chatbot keeps owner-scoped chat history, stores verified image-analysis results in that history, uses existing disease/species scan records by verified scan ID, and can optionally retrieve citations from a local vector index of reviewed agricultural documents. No provider key is sent to the frontend. See `backend/backend/README.md` for architecture, RAG setup, environment variables, and commands. Without API credentials the endpoint returns a clear configuration error rather than canned agricultural advice. Weather uses the existing Open-Meteo integration; AI weather advice requires a configured LLM.



## Plant-analysis evidence limits

The installed species classifier is an EfficientNetB0-based eight-class model. Its output is an uncalibrated class score. The disease model class map is empty and no health labels/segmentation dataset or reviewed crop-specific fertilizer references are present; Agri Mitra consequently shows health unavailable and fertilizer evidence insufficient until those data sources are supplied and validated.
