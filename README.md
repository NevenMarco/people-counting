# People Counting Backend (Dahua NVR, Python/FastAPI)

Backend in Python/FastAPI che dialoga con un NVR Dahua (HTTP_API_3.26) per il conteggio persone in tempo reale.

## Stack

- Python 3.11+
- FastAPI + Uvicorn
- PostgreSQL
- SQLAlchemy (async)
- httpx (HTTP client con Digest Auth)

## Installazione rapida

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Configura le variabili d'ambiente (o un file `.env`) secondo i campi in `backend/config.py`:

- `NVR_HOST`, `NVR_PORT`, `NVR_USERNAME`, `NVR_PASSWORD`
- `DB_DSN` (es. `postgresql+asyncpg://user:pass@host:5432/people_counting`)

Poi avvia il server:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8080
```

L'endpoint principale per il frontend è:

- `GET /api/presence` – restituisce il numero di persone presenti totali e per camera.
- `GET /docs` – documentazione interattiva Swagger.

## Esecuzione in Docker (sviluppo su Mac / produzione su Ubuntu)

Prerequisiti:

- Docker e Docker Compose installati.

Avvio stack completo (Postgres + backend):

```bash
docker compose up --build
```

Prima dell'avvio, modifica nel file `docker-compose.yml`:

- `NVR_HOST`, `NVR_PORT`, `NVR_USERNAME`, `NVR_PASSWORD`
- eventuali `CAMERA_D4_CHANNEL`, `CAMERA_D6_CHANNEL` se l'indice canale differisce.

Una volta in esecuzione:

- Backend: `http://localhost:8080`
- API presenza: `GET http://localhost:8080/api/presence`
- Doc interattiva: `http://localhost:8080/docs`

Lo stesso `docker-compose.yml` e `Dockerfile` possono essere usati tali e quali sul server Ubuntu (eventualmente cambiando solo `NVR_HOST` o le credenziali DB).

