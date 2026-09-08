# GIS Backend

FastAPI backend for a PostgreSQL/PostGIS based geospatial case management platform. The service manages cases, layers, map features, comments, file imports, GeoCLIP image predictions, vector operations, geo-news search, and hotspot discovery from a separate MapServer/PostGIS database.

## Tech Stack

- FastAPI
- PostgreSQL + PostGIS
- SQLAlchemy / GeoAlchemy2
- Alembic migrations
- Pydantic schemas
- Uvicorn
- WebSockets for live layer, feature, cursor, and comment updates

## Project Structure

```text
api/                 FastAPI route modules
database/            Main DB and MapServer DB connection setup
models/              SQLAlchemy models
schemas/             Pydantic request/response schemas
services/            Business logic grouped by feature area
utils/               Config, auth, roles, exceptions, logging
migrations/          Alembic migration files
uploads/             Uploaded GIS files
logs/                Application logs
config/              Runtime configuration files, including hotspot categories
```

## Environment

Create a `.env` file in the project root.

```env
DATABASE_URL=postgresql://postgres:password@localhost:5432/geobackend
MAPSERVER_DATABASE_URL=postgresql://geouser:password@localhost:5432/geodb

LOG_DIR=logs
LOG_LEVEL=INFO
LOG_JSON=false
LOG_MAX_BYTES=10485760
LOG_BACKUP_COUNT=5

GEOCLIP_TOP_K=5
MAX_FILE_SIZE_MB=20

ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

SECRET_KEY=change_this_secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=120
```

`DATABASE_URL` is the main application database. `MAPSERVER_DATABASE_URL` is optional for the app in general, but required for hotspot search.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### MIME detection (libmagic)

File/attachment upload validation detects the real content type with `python-magic`, a wrapper around the native libmagic C library. MIME detection is not optional — it protects against rename attacks (e.g. an `.exe` renamed to `report.pdf` is rejected).

The correct libmagic provider is selected automatically per platform by `requirements.txt`:

- **Windows** — `pip install -r requirements.txt` installs `python-magic-bin`, which bundles the required Windows libmagic DLL. No extra step.
- **Linux/WSL** — `python-magic` wraps the system libmagic library, so first install it with:

  ```bash
  sudo apt-get install libmagic1
  ```

  (On some distributions/older packages the development package `libmagic-dev` may be required instead.) `pip install -r requirements.txt` does **not** install the Linux system library itself.

## Database

Apply migrations:

```bash
alembic upgrade head
```

The main database stores:

- users
- cases
- layers
- features
- comments and replies
- image records
- geo-news search history

The MapServer database is read separately for hotspot reference data, mainly from:

- `public.planet_osm_point`
- `public.planet_osm_polygon`

## Run

Development:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

If WSL/file watching runs out of memory, run without reload:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

API docs:

```text
http://localhost:8000/docs
```

Health check:

```text
GET /health
```

## Authentication

Routes:

```text
POST /register
POST /login
GET  /me
```

Protected APIs require a bearer token:

```http
Authorization: Bearer <token>
```

Role groups are defined in `utils/roles.py`.

## Core APIs

### Cases

```text
POST   /cases
GET    /cases
GET    /cases/{case_id}
PUT    /cases/{case_id}
PATCH  /cases/{case_id}
DELETE /cases/{case_id}
```

### Layers

```text
POST   /layers
GET    /layers
GET    /layers/case/{case_id}
GET    /layers/case/{case_id}/{layer_id}
PUT    /layers/case/{case_id}/{layer_id}
PATCH  /layers/case/{case_id}/{layer_id}
DELETE /layers/case/{case_id}/{layer_id}
```

### Features

```text
POST   /features
POST   /cases/{case_id}/layers/{layer_id}/features/measurement
GET    /features
GET    /cases/{case_id}/features
GET    /cases/{case_id}/layers/{layer_id}/features
GET    /cases/{case_id}/layers/{layer_id}/features/{feature_number}
PUT    /cases/{case_id}/layers/{layer_id}/features/{feature_id}
PATCH  /cases/{case_id}/layers/{layer_id}/features/{feature_id}
DELETE /cases/{case_id}/layers/{layer_id}/features/{feature_id}
```

Features are stored in SRID 4326. Geometry is written through PostGIS functions and returned as GeoJSON.

## File Import

```text
POST /import
```

The import pipeline supports GIS file extraction and stores parsed geometries as features under a layer. Bulk import broadcasts feature batch events over the existing feature WebSocket.

## GeoCLIP

```text
POST   /upload
GET    /layers/{layer_id}/images
GET    /geoclip/layers/{layer_id}/features
GET    /image/{image_id}
DELETE /geoclip/layers/{layer_id}
```

GeoCLIP image predictions are saved as circular prediction features. Each prediction creates a feature with circle geometry and prediction metadata in `properties`.

## Comments

```text
POST   /cases/{case_id}/layers/{layer_id}/comments
POST   /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/reply
GET    /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments
GET    /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/thread
GET    /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/{comment_id}/replies
GET    /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/{comment_id}/attachment
GET    /cases/{case_id}/comments
GET    /cases/{case_id}/layers/{layer_id}/comments
DELETE /cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/{comment_id}
```

Comments support attachments, delete, and flat reply threads through `root_comment_id`.

## Vector Operations

```text
POST /vector/union
POST /vector/intersection
POST /vector/difference
POST /vector/symdifference
POST /vector/buffer
POST /vector/centroid
POST /vector/convex-hull
```

Vector results are saved back into the project as new features/layers and broadcast using the existing layer and feature WebSocket managers.

Intersection uses `ST_Intersects` before computing `ST_Intersection` so non-overlapping selected shapes are rejected instead of saving empty geometries.

## Geo News Search

```text
POST   /geo-search/news
GET    /geo-search/news/history
DELETE /geo-search/news/history
POST   /geo-search/news/comment
```

News search uses the selected feature geometry as the search area, fetches relevant current news, stores lightweight search history metadata, and can save selected news as feature comments.

## Hotspots

```text
POST /hotspots/search
POST /hotspots/save
```

Hotspot search uses the selected project feature geometry from the main database, then searches the MapServer/PostGIS database for matching OSM places.

Current MapServer sources:

```text
planet_osm_point
planet_osm_polygon
```

Default behavior:

- `range_meters = null`: search inside/intersecting the selected feature geometry
- `range_meters` set: search within that distance from the selected feature center
- `limit` default: `100`
- `limit` max: `1000`
- `range_meters` max: `50000`

Hotspot response includes individual hotspot priority and risk zones. Saved hotspots are stored as normal project features and broadcast over the existing feature WebSocket as `feature.created`.

Hotspot priority rules are configured in:

```text
config/hotspot_categories.json
```

## WebSockets

```text
/ws/cases/{case_id}/features
/ws/cases/{case_id}/layers
/ws/cases/{case_id}/cursors
/ws/cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments
```

WebSocket events include:

```text
feature.created
feature.updated
feature.deleted
feature.batch_created
feature.batch_import_completed
layer.created
layer.updated
layer.deleted
comment.created
comment.reply_created
comment.deleted
```

## Measurement Features

Measurements are saved as normal features with:

```json
{
  "geometry_type": "measurement",
  "properties": {
    "measurement_type": "straight",
    "distance_meters": 742.5
  }
}
```

The backend stores the provided distance as-is and does not recompute it server-side.

## Notes

- Main application geometries use SRID 4326.
- MapServer OSM geometries commonly use SRID 3857, so hotspot queries transform geometries before spatial comparison.
- The backend uses typed application exceptions from `utils/exceptions.py`.
- Logs are written under `logs/`.
- Uploaded files are stored under `uploads/`.
