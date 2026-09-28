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

Copy `.env.example` to `.env` in the project root and adjust the values. `.env.example` lists every supported setting, including the optional ones.

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

CI_BASE_URL=http://192.168.6.63:8014
MODULE_SLUG=spatial-geographical-analysis

EMAIL_DUMP_API_BASE_URL=http://192.168.6.63:8002
EMAIL_DUMP_TIMEOUT_SECONDS=30
```

`DATABASE_URL` is the main application database. `MAPSERVER_DATABASE_URL` is optional for the app in general, but required for hotspot search.

`EMAIL_DUMP_API_BASE_URL` points at the external Email Dump Backend. It is optional: when it is empty the application still starts, and only the Email Dump route reports a configuration error. `EMAIL_DUMP_TIMEOUT_SECONDS` bounds the upstream request.

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

## Module Slugs

`module_slug` is metadata identifying which source module created a layer or feature. It is **not** the CI authentication module (`settings.MODULE_SLUG` from `.env`, used when talking to Central Intelligence).

Supported slugs:

| Slug                | Origin                                          |
| ------------------- | ----------------------------------------------- |
| `gis`               | Core GIS operations (manual layers, imports, measurements, GeoCLIP, hotspots, vector operations) |
| `email-dump`        | Email intelligence integrations                 |
| `telecom-analysis`  | Telecom / phone-number analysis integrations     |

Rules:

- Manual layer creation must send a valid `module_slug`; `null`, empty, whitespace-only, or unknown values are rejected (`gis / email-dump / telecom-analysis` only).
- Automatically created layers inherit the `module_slug` of the feature being created when no `layer_id` is supplied. Ordinary GIS-created features use `gis`.
- Feature `module_slug` defaults to `gis` and supports the same whitelist. The feature/layer DB columns are NOT NULL, indexed, and constrained by CHECK constraints matching the application whitelist.
- Removing the columns is handled by the migration's downgrade; applying `alembic upgrade head` backfills any pre-existing rows to `gis` before enforcing NOT NULL.

## Email and Phone Properties

Email and phone values are independent and live inside the existing feature `properties` JSON — they may be present separately or together. `module_slug` identifies the originating module, not the presence of an email or phone number.

```json
{
  "module_slug": "email-dump",
  "properties": {
    "email": "person@example.com"
  }
}
```

```json
{
  "module_slug": "telecom-analysis",
  "properties": {
    "phone_number": "+919876543210"
  }
}
```

```json
{
  "module_slug": "telecom-analysis",
  "properties": {
    "email": "person@example.com",
    "phone_number": "+919876543210"
  }
}
```

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
- Email Dump records: `emails`, `email_targets`, `email_dumps`

The `email-dump` module writes a `layers` row per imported email, so every
imported email is visible in the layers list alongside its point features.

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
POST   /layers/case/{case_id}
GET    /layers
GET    /layers/case/{case_id}
GET    /layers/case/{case_id}/{layer_id}
PUT    /layers/case/{case_id}/{layer_id}
PATCH  /layers/case/{case_id}/{layer_id}
DELETE /layers/case/{case_id}/{layer_id}
```

Manual layer creation requires the origin `module_slug` in the request body:

```json
{
  "name": "Email Locations",
  "layer_type": "email",
  "module_slug": "email-dump",
  "visible": true
}
```

`POST /layers/case/{case_id}` takes `case_id` as a path parameter (not the body), validates the bearer token, the user's access to the case, and the layer write role, and broadcasts the `layer.created` WebSocket event. `POST /layers` also requires `module_slug`.

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

### Satellites

```text
GET    /api/satellites
```

Token-protected live satellite positions, read from CelesTrak and propagated with SGP4. Returns a GeoJSON `FeatureCollection`; each feature is a `Point` whose properties are the satellite name, NORAD ID, altitude in km, and the propagation timestamp.

| Parameter | Default | Description |
| --- | --- | --- |
| `bbox` | none | Post-propagation filter, `minLon,minLat,maxLon,maxLat`. Invalid values return 400. |
| `limit` | 500 | Maximum features returned, capped by `SATELLITE_MAX_RESULTS`. |
| `group` | `active` | CelesTrak element group. An unknown value returns 422. |

Supported `group` values:

| Value | Contents |
| --- | --- |
| `active` | Everything in the current active catalog. The default. |
| `stations` | Crewed space stations and visiting vehicles. |
| `visual` | The brightest objects. |
| `weather` | Weather satellites. |
| `gps-ops` | The GPS operational constellation. |
| `starlink` | The Starlink constellation. |

Omitting `group` keeps the previous behaviour and returns the full active catalog, so existing clients are unaffected.

```http
GET /api/satellites?group=stations&bbox=70,15,80,20&limit=100
```

Feeds are cached per group: TLE data for an hour, propagated positions for five seconds, so a client cycling through groups does not multiply upstream requests. CelesTrak regenerates its data on a two-hour cadence and answers requests made inside that window with `403` and a "no new data" body. That is treated as a successful no-op and the last good TLE set is reused, so a cooldown never surfaces as an error. It only returns 503 if the feed is unavailable and nothing has been cached yet.

The feed URL is `settings.CELESTRAK_TLE_URL` plus a `GROUP` query parameter. The legacy static `pub/TLE/catalog.txt` file is no longer served by CelesTrak and answers `403`; the default is the query-string endpoint.

Note that `starlink` contains several thousand objects while the propagation input is capped at `SATELLITE_MAX_RESULTS` (500). The cap is applied before propagation, so a large group returns the first 500 records in feed order rather than the whole constellation.

`GET /api/aircraft` is the sibling live-data endpoint and follows the same GeoJSON and caching conventions, with a `bbox` filter instead of `group`.

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

## Email Dump Origin IPs

```text
Frontend  →  GIS Backend  →  Email Dump Backend
```

The GIS backend is the integration/proxy layer. It does **not** replace or duplicate the Email Dump backend: email analysis, email records, email IDs, risk analysis, origin-IP analysis, and Email Dump authentication all stay in the Email Dump backend. The frontend never calls the Email Dump backend directly — it calls the GIS route, which forwards the request upstream and converts the answer into GIS layers and features.

### Routes

```text
GIS route (used by the frontend):
GET /cases/{case_id}/email-dump/origin-ips

External Email Dump endpoint (called by GIS only):
GET {EMAIL_DUMP_API_BASE_URL}/api/emails/single/origin-ips/{case_id}
```

The provider URL is always built from `settings.EMAIL_DUMP_API_BASE_URL`; the host and port are never hard-coded in service logic. Only the path segment is fixed.

### Configuration

```env
EMAIL_DUMP_API_BASE_URL=http://192.168.6.63:8002
EMAIL_DUMP_TIMEOUT_SECONDS=30
```

`EMAIL_DUMP_API_BASE_URL` defaults to `""`. The application starts without it; calling the Email Dump route then returns a clear configuration error.

### Authentication

The route uses the standard GIS authentication: the bearer token is validated by Central Intelligence, case access is validated, and the write role is required because the import creates layers and features.

```python
access_token = Depends(get_access_token)
current_user  = Depends(require_roles_for_case(CAN_WRITE))
```

The caller's token is forwarded upstream so Email Dump applies its own authorization:

```http
Authorization: Bearer <current-token>
```

GIS never mints, stores, or logs provider credentials.

### Query parameters

The route accepts every parameter documented by the Email Dump Backend and forwards only the ones that were provided:

```text
view_type  target_id  dump_id  ip_type  limit  keyword  isp  country  risk_level  is_suspicious
```

### email_id → layer

Every item in the upstream `data` array maps to one GIS layer, named deterministically:

```text
layer_name = f"Email {email_id}"
```

```json
{
  "case_id": 123,
  "name": "Email 101",
  "layer_type": "email",
  "module_slug": "email-dump",
  "visible": true
}
```

Before creating anything, GIS looks for an existing layer matching `case_id` + `name` + `module_slug` and reuses it (`layers_reused`) instead of creating a duplicate (`layers_created`). Layers are case-scoped: the same `email_id` in a different case gets its own layer.

### IP → feature

Every valid IP coordinate becomes one Point feature in that email's layer:

```json
{
  "name": "IP 8.8.8.8",
  "geometry_type": "Point",
  "geometry": { "type": "Point", "coordinates": [73.8567, 18.5204] },
  "module_slug": "email-dump",
  "properties": {
    "email_id": 101,
    "ip": "8.8.8.8",
    "ip_type": "origin",
    "count": 2,
    "email_address": "person@example.com",
    "risk_level": "safe",
    "is_suspicious": false,
    "country": "India",
    "isp": "Example ISP",
    "first_seen": "2026-01-01T00:00:00+00:00",
    "last_seen": "2026-01-02T00:00:00+00:00"
  }
}
```

- Coordinates are stored as `[longitude, latitude]` in SRID 4326 through the existing PostGIS handling.
- Latitude must be within `-90..90` and longitude within `-180..180`.
- Missing or invalid coordinates create no geometry and are counted in `skipped_coordinates`.
- The original `email_id` and `ip` are preserved in `properties` and are the feature's identity for duplicate detection.
- Features are written through the existing batch feature service.

### module_slug

Every layer and feature created by this integration uses `module_slug = "email-dump"`, validated against the centralized whitelist in `utils/constants.py` (`gis` / `email-dump` / `telecom-analysis`). The response never contains a null `module_slug`.

### Stored tables

The same import also writes the payload to three normalised tables, so it can be queried in SQL instead of extracted from `features.properties` JSON.

| Table | One row per | Primary key |
| --- | --- | --- |
| `emails` | email and IP observation | `(case_id, email_id, ip)` |
| `email_targets` | target reported for an email | `(case_id, target_id)` |
| `email_dumps` | dump belonging to a target | `(case_id, dump_id)` |

`emails` is the normalised form of the `email-dump` feature properties: `email_id`, `email_address`, `ip`, `ip_type`, `count`, `risk_level`, `is_suspicious`, `country`, `isp`, `first_seen`, `last_seen`. One row per (email, IP) pair keeps it 1:1 with the IP features, and the IP stays in the key because it is the grain of the data: a re-import of the same email and IP updates that row, while the same IP belonging to a *different* email is a separate row.

The keys are the provider's own identifiers, so there is no backend-assigned `id` to keep in step with the payload. `email_dumps.target_id` is now the provider's target identifier, and a real composite foreign key `(case_id, target_id) -> email_targets(case_id, target_id)` replaces the old link to a local surrogate, so deleting a target still takes its dumps with it.

One link is necessarily weaker than before. `email_targets.email_id` was a foreign key to `emails.id`; it is now a plain indexed column holding the provider's `email_id`, because an email has one row per IP and so no single `emails` row for a target to point at. Deleting an email therefore no longer cascades to its targets — both are re-derivable from the provider on the next import.

All three tables also carry `layer_id`, a **required** foreign key to `layers.id` `ON DELETE CASCADE`, so a normalised row can always be traced back to the layer whose features it describes. Every imported email is a layer: the import creates one `Email {email_id}` layer per email, so the email shows up in the ordinary layers list and not only in SQL, and the rows written alongside it point at that layer. `layer_id` is `NOT NULL`, so the database rejects a row that names no layer; deleting a layer removes its rows with it.

Migration `20260928_05` enforces that. Rows left with a null `layer_id`, or naming a layer that no longer exists, are deleted rather than kept as dangling references — the foreign key cascade already prevents the second case, and such rows describe no layer, no features and no provider target, so the import recreates them from the provider on the next run. The count deleted per table is logged rather than dropped silently.

`case_id` on all three tables is **not** a foreign key. GIS owns no `cases` table: cases and users belong to Central Intelligence (migration `20260904_01` removed the local case and user FKs deliberately). `case_id` is a plain indexed integer, matching `layers.case_id` and `features.case_id`.

Provider `target_id` and `dump_id` are stored as text, so GIS does not assume the Email Dump Backend's identifier type. The provider is not consistent about sending them — the case-targets endpoint documents `target_id` as an integer while the per-case dumps endpoint leaves it untyped — so integer identifiers are coerced to their digit form on the way in rather than rejected. `targets` is optional in the upstream response, so the import works unchanged against the current payload and starts populating targets and dumps once the provider sends them.

### Duplicate behavior

The import is idempotent and case-scoped:

- **Layer reuse** — match on `case_id` + layer name + `module_slug`.
- **Feature reuse** — match on `layer_id` + `email_id` in `properties` + `ip` in `properties`.
- **Email row reuse** — match on the key `(case_id, email_id, ip)`.
- **Target row reuse** — match on the key `(case_id, target_id)`.
- **Dump row reuse** — match on the key `(case_id, dump_id)`.

A repeated import of the same data creates no duplicates; it increments `layers_reused` / `features_reused` and reports the normalised writes as `emails_updated`, `targets_updated`, and `dumps_updated` rather than `*_created`.

### WebSocket events

New layers broadcast `layer.created` and newly created features broadcast `feature.batch_created` through the existing layer and feature managers. Nothing new is registered.

### Errors

| Situation | GIS response |
| --- | --- |
| `EMAIL_DUMP_API_BASE_URL` not set | `503` configuration error |
| Upstream timeout | `504` gateway timeout |
| Connection failure | `503` service unavailable |
| Upstream `401` / `403` | `401` unauthorized |
| Upstream `404` | `404` provider resource error |
| Upstream `429` | `503` rate limited |
| Upstream `5xx` | `503` service unavailable |
| Malformed JSON, missing/invalid `data` | `503` invalid provider response |
| Missing / invalid coordinates | skipped and counted, import continues |

The upstream response body, provider credentials, bearer tokens, database connection strings, and internal tracebacks are never returned. Everything goes through the typed application exceptions in `utils/exceptions.py` and the shared exception handler.

### Example

Request:

```http
GET /cases/123/email-dump/origin-ips?risk_level=high&country=India
Authorization: Bearer <token>
```

GIS then calls:

```http
GET http://192.168.6.63:8002/api/emails/single/origin-ips/123?risk_level=high&country=India
Authorization: Bearer <token>
```

GIS response:

```json
{
  "success": true,
  "case_id": 123,
  "module_slug": "email-dump",
  "layers_created": 1,
  "layers_reused": 2,
  "features_created": 5,
  "features_reused": 3,
  "skipped_coordinates": 1,
  "emails_created": 2,
  "emails_updated": 0,
  "targets_created": 1,
  "targets_updated": 0,
  "dumps_created": 2,
  "dumps_updated": 0,
  "layers": [
    {
      "id": 25,
      "case_id": 123,
      "name": "Email 101",
      "layer_type": "email",
      "module_slug": "email-dump",
      "visible": true
    }
  ]
}
```

The raw Email Dump payload is never returned to the frontend.

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
