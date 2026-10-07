# GIS Backend

FastAPI backend for a PostgreSQL/PostGIS case-management platform. It manages cases, layers, map features, comments, file imports, GeoCLIP image predictions, vector operations, geo-news search, live satellite and aircraft positions, hotspot discovery from a separate MapServer/PostGIS database, and the Email Dump and Face Recognition System integrations.

## Tech Stack

- FastAPI, Uvicorn
- PostgreSQL + PostGIS
- SQLAlchemy / GeoAlchemy2
- Alembic migrations
- Pydantic schemas
- WebSockets for live layer, feature, cursor, and comment updates

## Project Structure

```text
api/                 FastAPI route modules
config/              Runtime configuration, including hotspot categories
database/            Main DB and MapServer DB connection setup
migrations/          Alembic migration files
models/              SQLAlchemy models
schemas/             Pydantic request/response schemas
services/            Business logic grouped by feature area
utils/               Config, auth, roles, exceptions, logging
uploads/             Uploaded GIS files
logs/                Application logs
```

## Environment

Copy `.env.example` to `.env` and adjust the values. `.env.example` lists every supported setting.

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

FRS_API_BASE_URL=http://192.168.6.63:8003
FRS_TIMEOUT_SECONDS=30

OPENSKY_BASE_URL=https://opensky-network.org/api
OPENSKY_TIMEOUT_SECONDS=15
AIRCRAFT_CACHE_TTL_SECONDS=30
CELESTRAK_TLE_URL=https://celestrak.org/NORAD/elements/gp.php?GROUP={group}&FORMAT=tle
CELESTRAK_TIMEOUT_SECONDS=15
SATELLITE_TLE_CACHE_TTL_SECONDS=3600
SATELLITE_POSITION_CACHE_TTL_SECONDS=5
SATELLITE_MAX_RESULTS=500
```

`DATABASE_URL` is the main application database. `MAPSERVER_DATABASE_URL` is optional for the app in general but required for hotspot search. `EMAIL_DUMP_API_BASE_URL` and `FRS_API_BASE_URL` are also optional: when empty the application still starts, and only the Email Dump and Face Recognition System routes report a configuration error.

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

Upload validation detects the real content type with `python-magic`, a wrapper around the native libmagic C library. It is not optional — it rejects rename attacks such as an `.exe` renamed to `report.pdf`. `requirements.txt` picks the right provider per platform: `python-magic-bin` on Windows, which bundles the DLL, and `python-magic` on Linux/WSL, which needs the system library:

```bash
sudo apt-get install libmagic1
```

## Module Slugs

`module_slug` is metadata identifying which source module created a layer or feature. It is **not** the CI authentication module (`settings.MODULE_SLUG`, used when talking to Central Intelligence).

| Slug | Origin |
| --- | --- |
| `gis` | Core GIS operations: manual layers, imports, measurements, GeoCLIP, hotspots, vector operations |
| `email-dump` | Email intelligence integrations |
| `telecom-analysis` | Telecom / phone-number analysis integrations |
| `face-recognition-system` | Face Recognition System camera imports |

- Manual layer creation must send a valid `module_slug`; `null`, empty, whitespace-only, or unknown values are rejected.
- Automatically created layers inherit the `module_slug` of the feature being created when no `layer_id` is supplied. Ordinary GIS-created features use `gis`.
- The `features` and `layers` DB columns are NOT NULL, indexed, and constrained by CHECK constraints matching the application whitelist. `alembic upgrade head` backfills any pre-existing rows to `gis` before enforcing NOT NULL.

Email and phone values live inside the existing feature `properties` JSON and are independent of `module_slug`:

```json
{
  "module_slug": "email-dump",
  "properties": { "email": "person@example.com" }
}
```

```json
{
  "module_slug": "telecom-analysis",
  "properties": { "phone_number": "+919876543210" }
}
```

## Database

```bash
alembic upgrade head
```

The main database stores users, cases, layers, features, comments and replies, image records, geo-news search history, and the Email Dump tables (`emails`, `email_targets`, `email_target_emails`, `email_dumps`).

The MapServer database is read separately for hotspot reference data, mainly `public.planet_osm_point` and `public.planet_osm_polygon`.

## Run

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

If WSL file watching runs out of memory, run without reload:

```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

| | |
| --- | --- |
| API docs | http://localhost:8000/docs |
| Health check | `GET /health` |

## Authentication

```text
POST /register
POST  /login
GET   /me
```

Protected APIs require a bearer token:

```http
Authorization: Bearer <token>
```

Role groups are defined in `utils/roles.py`.

## Core APIs

### Cases, Layers, Features

| Method | Path |
| --- | --- |
| `POST` `GET` | `/cases` |
| `GET` `PUT` `PATCH` `DELETE` | `/cases/{case_id}` |
| `POST` `GET` | `/layers` |
| `POST` `GET` | `/layers/case/{case_id}` |
| `GET` `PUT` `PATCH` `DELETE` | `/layers/case/{case_id}/{layer_id}` |
| `POST` `GET` | `/features` |
| `POST` | `/cases/{case_id}/layers/{layer_id}/features/measurement` |
| `GET` | `/cases/{case_id}/features` |
| `GET` | `/cases/{case_id}/layers/{layer_id}/features` |
| `GET` | `/cases/{case_id}/layers/{layer_id}/features/{feature_number}` |
| `PUT` `PATCH` `DELETE` | `/cases/{case_id}/layers/{layer_id}/features/{feature_id}` |

Features are stored in SRID 4326. Geometry is written through PostGIS functions and returned as GeoJSON.

Manual layer creation requires the origin `module_slug` in the request body:

```json
{ "name": "Email Locations", "layer_type": "email", "module_slug": "email-dump", "visible": true }
```

`POST /layers/case/{case_id}` takes `case_id` as a path parameter rather than in the body, validates the bearer token, case access, and the layer write role, then broadcasts `layer.created`. `POST /layers` also requires `module_slug`.

### Satellites

```text
GET /api/satellites
```

Token-protected live satellite positions, read from CelesTrak and propagated with SGP4. Returns a GeoJSON `FeatureCollection` whose features are `Point`s with the satellite name, NORAD ID, altitude in km, and the propagation timestamp.

| Parameter | Default | Description |
| --- | --- | --- |
| `bbox` | none | Post-propagation filter, `minLon,minLat,maxLon,maxLat`. Invalid values return 400. |
| `limit` | 500 | Maximum features returned, capped by `SATELLITE_MAX_RESULTS`. |
| `group` | `active` | CelesTrak element group. An unknown value returns 422. |

| `group` | Contents |
| --- | --- |
| `active` | Everything in the current active catalog. The default. |
| `stations` | Crewed space stations and visiting vehicles. |
| `visual` | The brightest objects. |
| `weather` | Weather satellites. |
| `gps-ops` | The GPS operational constellation. |
| `starlink` | The Starlink constellation. |

```http
GET /api/satellites?group=stations&bbox=70,15,80,20&limit=100
```

Feeds are cached per group — TLE data for an hour, propagated positions for five seconds — so a client cycling through groups does not multiply upstream requests. CelesTrak regenerates on a two-hour cadence and answers requests inside that window with `403` and a "no new data" body; that is treated as a successful no-op and the last good TLE set is reused, so a cooldown never surfaces as an error. It returns 503 only if the feed is unavailable and nothing has been cached yet. The feed URL is `settings.CELESTRAK_TLE_URL` plus a `GROUP` query parameter — the legacy static `pub/TLE/catalog.txt` file is no longer served and answers `403`. `starlink` contains several thousand objects while the propagation input is capped at `SATELLITE_MAX_RESULTS`, and the cap is applied before propagation, so a large group returns the first 500 records in feed order.

`GET /api/aircraft` is the sibling live-data endpoint, following the same GeoJSON and caching conventions with a `bbox` filter instead of `group`.

### File Import, GeoCLIP, Comments, Vector, News, Hotspots

| Method | Path | Notes |
| --- | --- | --- |
| `POST` | `/import` | Extracts GIS files, stores geometries as features, broadcasts batch events |
| `POST` | `/upload` | GeoCLIP prediction images, saved as circular features with the metadata in `properties` |
| `GET` | `/layers/{layer_id}/images` | Also `/geoclip/layers/{layer_id}/features` |
| `GET` | `/image/{image_id}` | |
| `DELETE` | `/geoclip/layers/{layer_id}` | |
| `POST` | `/cases/{case_id}/layers/{layer_id}/comments` | Attachments, delete, and flat reply threads via `root_comment_id` |
| `POST` | `/cases/{case_id}/layers/{layer_id}/features/{feature_number}/comments/reply` | |
| `GET` | `…/features/{feature_number}/comments` | Also `…/comments/thread` |
| `GET` | `…/comments/{comment_id}/replies` | Also `…/comments/{comment_id}/attachment` |
| `DELETE` | `…/comments/{comment_id}` | |
| `GET` | `/cases/{case_id}/comments` | Also `/cases/{case_id}/layers/{layer_id}/comments` |
| `POST` | `/vector/union` `/intersection` `/difference` `/symdifference` `/buffer` `/centroid` `/convex-hull` | |
| `POST` | `/geo-search/news` | Uses the selected feature geometry as the search area |
| `GET` `DELETE` | `/geo-search/news/history` | Lightweight search history metadata |
| `POST` | `/geo-search/news/comment` | Saves selected news as feature comments |
| `POST` | `/hotspots/search` `/hotspots/save` | Searches MapServer/PostGIS for OSM places matching the selected geometry |

Vector results are saved back into the project as new features/layers and broadcast through the existing layer and feature WebSocket managers. Intersection uses `ST_Intersects` before computing `ST_Intersection` so non-overlapping selections are rejected instead of saving empty geometries.

Hotspot `range_meters` defaults to `null`, which searches inside/intersecting the selected geometry; set it to search within that distance of the feature's center, up to 50000. `limit` defaults to 100, capped at 1000. The response includes individual hotspot priority and risk zones; saved hotspots become normal project features and broadcast as `feature.created`. Priority rules live in `config/hotspot_categories.json`.

## Email Dump Origin IPs

```text
Frontend  →  GIS Backend  →  Email Dump Backend
```

The GIS backend is the integration layer. It does not replace or duplicate the Email Dump backend: email analysis, email records, email IDs, risk analysis, origin-IP analysis, and Email Dump authentication all stay upstream. The frontend never calls the Email Dump backend directly — it calls the GIS route, which forwards the request and converts the answer into GIS layers and features.

## Face Recognition System Cameras

```text
Frontend  →  GIS Backend  →  Face Recognition System
```

The frontend never calls FRS directly — it calls GIS, which forwards the caller's bearer token and converts the provider payload into GIS layers and features.

```text
GET /face-recognition-system/cameras[?case_id={id}]
GET /cases/{case_id}/face-recognition-system/persons
GET /cases/{case_id}/face-recognition-system/persons/{person_id}/history?person_name={name}
GET /cases/{case_id}/face-recognition-system/persons/{person_id}/route?limit={n}
```

Upstream endpoints, called by GIS only:

```text
GET {FRS_API_BASE_URL}/api/cameras
GET {FRS_API_BASE_URL}/api/persons?case_id={case_id}
GET {FRS_API_BASE_URL}/api/persons/{person_id}/history?case_id={case_id}
```

The provider URL is always built from `settings.FRS_API_BASE_URL`; the host and port are never hard-coded in service logic.

**One cameras route, registry global.** The camera registry is global, so `case_id` is optional upstream and GIS does not send it — the same cameras serve every case, and filtering by case would hide cameras not yet attributed to this one. `GET /face-recognition-system/cameras` mirrors that: no case in the path. Every call fetches the provider registry, upserts the global `frs_cameras` rows and returns what is stored (`data`, with each camera's latitude and longitude — the frontend plots its pins from these), cameras the provider has stopped reporting included, since the registry is never pruned. Passing an **optional** `?case_id=` additionally runs the case-scoped import on top: one layer per camera, one point feature at its fix, and the layer/feature counts in the same response — so the frontend passes its current case when it wants the pins drawn as GIS layers, and omits it when it just wants the registry. Both person endpoints are case-scoped, so `case_id` is required upstream and GIS always sends it.

### Authentication

All four routes use standard GIS authentication, and the three that call FRS forward the caller's own token so FRS applies its own authorization against the same CI identity GIS already validated (the route endpoint is local-only and never calls FRS):

```python
access_token = Depends(get_access_token)
current_user = Depends(require_roles_for_case(CAN_WRITE))  # the three case-scoped routes
current_user = Depends(require_roles(ALL_ROLES))           # /face-recognition-system/cameras (base gate)
# and, only when ?case_id= was supplied:
case_user  = await authorize_case(access_token, case_id)   # token + case access
enforce_role(case_user, CAN_WRITE)                         # same write role as before
```

The registry read takes any authenticated role via `require_roles(ALL_ROLES)`: with no case in the path there is no case membership to validate against, and a valid token is still required (and still forwarded to FRS). The moment `case_id` is supplied the old case-scoped cameras route's gate applies **in full, before anything is written** — `authorize_case` for token + case access, then the `CAN_WRITE` check — so an import into a case is exactly as protected as it was when the route had the case in its path.

The write role is also required on the three case-scoped routes, including the sync-on-read persons listing and the route endpoint: person registry membership and sighting history are investigative data. **GIS mints, stores and rotates no FRS credential.** There is no auth config to add — the provider reuses the CI token.

### Mapping rules

**camera_id → layer.** One layer per camera, named `FRS Camera {camera_id}` with `layer_type = "camera"`. The provider id is the sync key, never the display name: a name is not unique (two cameras can both be "Gate 2") and can exceed the `String(100)` width, so keying on a name would either collide or truncate into a second unreconcilable layer. If a pathological id overflows the column, the fixed prefix is kept and the id is truncated to the remaining budget. The `FRS Camera` / `FRS Person` prefixes exist so a hand-made analyst layer cannot collide and abort the whole import on the `uq_layers_case_id_name` constraint.

**camera → feature.** One Point feature per camera, at `[longitude, latitude]` in SRID 4326.

```json
{
  "name": "FRS Camera 12",
  "geometry_type": "Point",
  "geometry": { "type": "Point", "coordinates": [55.27, 25.2] },
  "module_slug": "face-recognition-system",
  "properties": {
    "camera_id": "12", "camera_name": "Gate 2", "zone": "North",
    "status": "online", "frs_case_id": "7",
    "latitude": 25.2, "longitude": 55.27
  }
}
```

`frs_case_id` is kept for traceability back to the provider's records but plays no part in placement, because the registry is global.

**Coordinates.** Latitude must be within `-90..90`, longitude within `-180..180`. Longitude is the only axis that is folded: values in `(180.0, 360.0]` become `value - 360.0`, which accepts the provider's 0-360 east-positive form without relocating anything. Values outside the window are left alone so the range check rejects them. **Latitude is never folded** — a shared step over both axes would turn corrupt data into valid data (`lat=359` would become `-1.0`, `lat=270` would become `-90.0`) and silently relocate a camera. A camera with no usable fix, or at `(0, 0)`, is skipped: `(0, 0)` is a real point in the Gulf of Guinea but FRS uses it as its "no fix" sentinel, and plotting it would place a fake observation in the Atlantic.

**No sync timestamp in `properties`.** A timestamp would differ on every run, so the unchanged check could never match and every panel open would rewrite and re-broadcast every camera to every open map for no reason. `Feature.updated_at` already records the write.

**person → layer.** One layer per person per history import, named `FRS Person {person_name} ({person_id})` with `layer_type = "person"`. The id is the sync key and is never the part that gets truncated: the display name gives way instead, and the ` ({person_id})` suffix survives intact. `person_name` is optional, so a history imported without one is named `FRS Person ({person_id})` and still reconciles on the id.

**Detections → features, collapsed per camera.** The provider emits **one history entry per detection**, so a person walking past a camera produces a long run of entries at the same coordinates. They are collapsed into one point per camera carrying `sighting_count` — the number of detections behind it, so "seen once" and "seen many times" are distinguishable on the map without opening a popup — plus `first_seen` / `last_seen` and the distinct `videos` the detections came from. One feature per entry would stack near-identical pins and bury the places that actually matter.

| Decision | Rule | Why |
| --- | --- | --- |
| `confidence` / `similarity` | **max** of the group's non-null values | A repeat detection carries its own score; taking the first entry's value would let an earlier, weaker detection hide a later, stronger match |
| `first_seen` / `last_seen` | `min(started_at)` / `max(ended_at)` over the raw strings | The provider emits ISO-8601 with a fixed UTC offset, which orders lexicographically exactly as it orders chronologically, so no parsing is needed |
| Grouping key | camera id (`camera:{id}`), falling back to coordinates (`point:{long},{lat}`) | Two cameras at the same spot are still **two places the person was seen from**, with different fields of view and different footage. Grouping by coordinate pair would merge them. Entries with no camera id fall back to coordinates so two unattributed detections at one spot still collapse to one point |
| `thumbnail_base64` | **forwarded verbatim on every `/persons` response** | Display-only and never persisted — `frs_persons` has no thumbnail column and does not get one — so it rides along on the model that `/persons` already returns, giving the frontend a face per row in one request. The value is passed through unchanged, **not** re-encoded or prefixed: the frontend is responsible for checking whether it already carries a `data:` prefix before rendering it |

Every layer and feature created by this integration uses `module_slug = "face-recognition-system"`, validated against the whitelist in `utils/constants.py`.

### Reconciliation

Idempotent in both halves. The registry sync always runs: it upserts on `camera_id` against the global table, so a second call updates rather than duplicates. The layer/feature half runs only when `?case_id=` was sent, and is case-scoped and idempotent like the Email Dump import:

| Step | Key |
| --- | --- |
| Layers | `case_id` + name + `module_slug` |
| Point features | Created, amended, or left alone, matched on `properties.camera_id` (cameras) or the camera key (persons) |
| Unchanged detection | Name, geometry type, properties and **coordinates** all compared, so a re-import of identical data reports `features_unchanged` rather than rewriting |
| Stale layers | Counted and reported; never deleted |

The camera import counts only `layer_type = "camera"` layers. Person history layers share the FRS `module_slug`, so counting on the slug alone would report every person's sighting layer in the case as a stale camera.

Nothing is removed when the provider stops reporting it. **Withdrawn cameras and dropped sightings keep their layers, their features, and any analyst comments or evidence attachments**, because an observation that was real when recorded is not retroactively wrong just because upstream pruned it. `layers_stale` reports the count; it is not an instruction to clean up.

Amended features are written with `db.commit()`, not `db.flush()`. `get_db` closes the request-scoped session without committing, so a flush-only update would be rolled back at the end of the request and the `features_updated` the response reports would never reach the database.

### Registry tables and the route endpoint

The map layer answers **where on the map**. It cannot answer **in what order was this person seen**, because the history import deliberately collapses per-detection entries into one point per camera — correct for a map, and exactly what destroys the ordering a route view needs. So the provider's records are also held as real tables:

| Table | Key | Scope |
| --- | --- | --- |
| `frs_cameras` | `camera_id` | **Global.** The provider owns one registry and sends no case filter, so a camera imported into three cases is one row here and three layers in `layers` |
| `frs_persons` | `(case_id, person_id)` | Case-scoped. `person_id` is a string even though the provider declares it as an integer |
| `frs_person_sightings` | surrogate `id` PK; unique `(case_id, person_id, video_id, camera_id, started_at)` | Case-scoped, **one row per raw detection**. `video_id` may be NULL — `source: "camera"` detections (which carry the coordinates) have a camera and a timestamp but no video. This is what the route view reads |

`frs_persons` rows are written by both the sync-on-read `/persons` listing and each history import, so everyone the case knows gets a row whether or not their history was ever pulled — a listed person with no detections answers `/route` as an **empty route** rather than as "never imported". Sightings, in contrast, exist only for detections the provider actually reports: pre-registering a person adds no sighting rows by itself.

There is **no per-detection id** upstream, so the natural key is `(video_id, camera_id, started_at)`. `video_id` is the trustworthy ordering unit where it exists: one video is one camera recording on one clock, so timestamps inside a `video_id` are mutually consistent. Camera-source detections have no video_id but DO carry a camera and a timestamp — they are stored keyed on their camera, and their ordering falls back to the provider's own UTC timestamp (the same cross-clock caveat the multi-video route already documents). The one thing that is never negotiable is the timestamp: an entry without a `started_at` cannot be placed in time, is skipped, and is counted as `sightings_unordered` — kept separate from `skipped_entries`, because "cannot be ordered" and "has no coordinates" are different failures the frontend must show differently. A fabricated timestamp would be worse than a visible skip.

**Sightings snapshot the camera coordinates.** A sighting stores the lat/long the provider reported for it rather than joining to `frs_cameras`, because a join would silently relocate historical evidence every time a camera is repositioned — rewriting where past sightings were actually captured. The disagreement is recorded as `camera_moved` instead, and `frs_cameras.coordinates_changed_at` records when the camera last moved. Nothing is ever deleted or pruned: sightings are evidence, and a record the provider stops reporting is retained and counted.

`GET .../persons/{person_id}/route` reads those rows in time order. Read-only and entirely local — no provider call, no writes. `limit` (1–5000, default 500) caps the response.

**Each sighting is a detection at a camera, not a measured position of the subject.** The provider reports the camera's own coordinates, so a person walking ten metres past a lens is still reported at the lens; the caller draws the line. `single_video` reports how far the ordering can be trusted: within one video it is sound, across videos it rests on the provider normalising every camera to UTC — which it asserts but exposes no way to verify, as the camera payload carries no clock-sync or NTP field. A multi-camera route should be presented as an **inferred** sequence, not a measured path, and the per-point timestamps shown so an analyst can see apparent back-tracking where two cameras captured the person at the same instant.

The `video_id` tiebreaker in the ordering is not cosmetic: without it, two identical requests can return the same two points in different orders, and a polyline drawn from that visibly jitters between refreshes.

### WebSocket events

New layers broadcast `layer.created`. Feature writes broadcast `feature.batch_created` for new points and `feature.batch_updated` for amended ones. Nothing new is registered, and an unchanged import broadcasts nothing at all.

### Errors

| Situation | GIS response |
| --- | --- |
| `FRS_API_BASE_URL` not set | `503` configuration error |
| Upstream timeout | `504` gateway timeout |
| Connection failure | `503` service unavailable |
| Upstream `401` / `403` | `401` unauthorized |
| Upstream `404` | `404` provider resource error |
| Upstream `429` | `503` rate limited |
| Upstream `5xx` | `503` service unavailable |
| Malformed JSON, or a payload with no usable list | `503` invalid provider response |
| One malformed camera / person / history record | skipped and counted, import continues |
| Missing, out-of-range, or `(0, 0)` coordinates | skipped and counted, import continues |
| Detection with no `video_id` or `started_at` | not stored; counted as `sightings_unordered` |
| Registry write failure | `503` — the transaction is rolled back |
| History empty, or nothing in it mappable | `200` — empty import (sightings still stored, `layers` empty, `points` `0`); when detections exist but have no coordinates, `message` reads "No coordinates of this particular person are present." |
| Route for a person the provider has never listed for the case | `404` — the sync-on-read listing gives every known person a registry row, so an empty route means "listed but no detections" |

The upstream response body, provider credentials, bearer tokens, database connection strings and internal tracebacks are never returned. Everything goes through the typed application exceptions in `utils/exceptions.py` and the shared exception handler.

### Example

```http
GET /face-recognition-system/cameras?case_id=123
Authorization: Bearer <token>
```

GIS then calls `GET http://192.168.6.63:8003/api/cameras` with the same token (never with a `case_id` — the provider registry is global), upserts `frs_cameras`, imports the case's layers and features, and answers:

```json
{
  "success": true,
  "data": [
    { "camera_id": "12", "name": "Gate 2", "zone": "North", "status": "online",
      "latitude": 25.2, "longitude": 55.27, "frs_case_id": "7",
      "coordinates_changed_at": null, "created_at": "...", "updated_at": "..." }
  ],
  "case_id": 123,
  "cameras": 2,
  "registry_created": 1, "registry_updated": 1, "cameras_moved": 0,
  "skipped_cameras": 0,
  "layers": [
    { "id": 40, "case_id": 123, "name": "FRS Camera 12",
      "layer_type": "camera", "module_slug": "face-recognition-system", "visible": true }
  ],
  "layers_created": 1, "layers_reused": 0, "layers_stale": 0,
  "features_created": 1, "features_updated": 0, "features_unchanged": 0
}
```

Without `?case_id=`, the same call (`GET /face-recognition-system/cameras`) syncs the registry, returns the identical `data` / registry / `skipped_cameras` fields, and reports `case_id: null` with empty `layers` and zero layer/feature counts — nothing was drawn, but `data` still carries every camera's latitude and longitude for the frontend to plot.

`cameras` is the provider's reported count **before** the coordinate filter, so comparing it with `layers_created` (or with `len(data)`) shows how many cameras were dropped for want of a fix. `data` is read back from `frs_cameras` in stable `camera_id` order, so retained cameras the provider no longer reports are still there.

The raw FRS payload is never returned to the frontend.

## Email Dump Origin IPs

```text
Frontend  →  GIS Backend  →  Email Dump Backend
```

The GIS backend is the integration layer. It does not replace or duplicate the Email Dump backend: email analysis, email records, email IDs, risk analysis, origin-IP analysis, and Email Dump authentication all stay upstream. The frontend never calls the Email Dump backend directly — it calls the GIS route, which forwards the request and converts the answer into GIS layers and features.

### Routes

```text
GET /cases/{case_id}/email-dump/origin-ips    import emails, targets and dumps
GET /cases/{case_id}/email-dump/targets       list targets, storing every one
GET /cases/{case_id}/email-dump/dumps?target_id={tid1},{tid2}   list and cache dumps
```

Upstream endpoints, called by GIS only:

```text
GET {EMAIL_DUMP_API_BASE_URL}/api/emails/single/origin-ips/{case_id}
GET {EMAIL_DUMP_API_BASE_URL}/api/cases/{case_id}/email-dump/targets
GET {EMAIL_DUMP_API_BASE_URL}/api/dumps/single/{case_id}?target_id={tid}
```

The provider URL is always built from `settings.EMAIL_DUMP_API_BASE_URL`; the host and port are never hard-coded in service logic.

Both listing routes write. `targets` upserts every target the provider returns, and `dumps` upserts the dumps of each selected target, so a target the user only picked from the dropdown is stored and its dumps become available before the email behind it has ever been imported. Both are keyed on the provider's own identifiers, so re-listing a case updates the rows it already has.

### Authentication

The route uses standard GIS authentication, and forwards the caller's own token so Email Dump applies its own authorization:

```python
access_token = Depends(get_access_token)
current_user = Depends(require_roles_for_case(CAN_WRITE))
```

The write role is required because the import creates layers and features. GIS never mints, stores, or logs provider credentials.

### Query parameters

The route accepts every parameter documented by the Email Dump Backend and forwards only those that were provided:

```text
view_type  target_id  dump_id  ip_type  limit  keyword  isp  country  risk_level  is_suspicious
```

### email_id → layer

Every item in the upstream `data` array maps to one GIS layer, named `f"Email {email_id}"`. Before creating anything, GIS looks for an existing layer matching `case_id` + `name` + `module_slug` and reuses it (`layers_reused`) rather than creating a duplicate. Layers are case-scoped, so the same `email_id` in a different case gets its own layer.

### IP → feature

Every valid IP coordinate becomes one Point feature in that email's layer. The provider reports the same IP more than once for a single email, once per role it played, and each of those is a genuinely different observation with its own count, timestamps, and geolocation. All persist as separate `emails` rows, while the **map** stays at one point per IP: two pins on one address is noise, and a dropped point understates the evidence.

```json
{
  "name": "IP 8.8.8.8",
  "geometry_type": "Point",
  "geometry": { "type": "Point", "coordinates": [73.8567, 18.5204] },
  "module_slug": "email-dump",
  "properties": {
    "email_id": 101,
    "ip": "8.8.8.8",
    "ip_type": "sender_origin_ip",
    "ip_roles": ["sender_origin_ip", "recipient_server_ip"],
    "ip_role_count": 2,
    "ip_occurrence_total": 7,
    "count": 5,
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

| Key | Meaning |
| --- | --- |
| `ip_type` | The role this point is filed under — the first by a fixed priority: `sender_origin_ip`, `sender_ip`, `origin_ip`, `recipient_server_ip`, `recipient_ip` |
| `ip_roles` | Every role the provider reported for this IP |
| `ip_role_count` | Number of roles |
| `ip_occurrence_total` | Sum of `count` across all those roles |
| `count` | Occurrences of the `ip_type` role only |

- Coordinates are stored as `[longitude, latitude]` in SRID 4326 through the existing PostGIS handling. Latitude must be within `-90..90` and longitude within `-180..180`; missing or invalid coordinates are counted in `skipped_coordinates`.
- The original `email_id` and `ip` are preserved in `properties` and are the feature's identity for duplicate detection.
- An email whose IPs have no usable coordinates is skipped whole: no layer, no broadcast, no `emails` row. The skips are still counted so the response totals add up, and the email imports normally once the provider sends coordinates.

Every layer and feature created by this integration uses `module_slug = "email-dump"`, validated against the whitelist in `utils/constants.py`. The response never contains a null `module_slug`.

### Stored tables

The same import also writes the payload to four normalised tables, so it can be queried in SQL instead of extracted from `features.properties` JSON.

| Table | One row per | Primary key |
| --- | --- | --- |
| `emails` | email and IP observation | `(case_id, email_id, ip, ip_type)` |
| `email_targets` | target reported for a case | `(case_id, target_id)` |
| `email_target_emails` | email that reported a target | `(case_id, target_id, email_id)` |
| `email_dumps` | dump belonging to a target | `(case_id, target_id, dump_id)` |

`emails` is the normalised form of the feature properties, plus `layer_id` and timestamps. `ip_type` is part of the key because the provider's evidence that an IP filled two roles is two facts, not one — under a key without it the second observation overwrote the first, losing one role's count and timestamps entirely. The keys are the provider's own identifiers, so there is no backend-assigned `id` to keep in step, and the composite foreign key `(case_id, target_id)` on `email_dumps` means deleting a target still takes its dumps with it.

**Targets reported by several emails.** A target is a person, and a person commonly has more than one address, so the same `target_id` arrives under several `email_id`s. `email_target_emails` keeps every address that reports a target; the single `email_id` column it replaced could only keep whichever was written last, so depending on payload order the import could silently connect the target to the wrong address. The target stays one row, so its dumps stay one row each. There is deliberately no `EmailRecord.targets` relationship — `emails` has one row per IP, so a collection hanging off an email row would repeat the target once per IP. The email → targets direction is a query, joining `email_target_emails` to `email_targets` on `(case_id, target_id)` and wanting `DISTINCT`.

`email_target_emails.email_id` is *not* a foreign key to `emails`, because that table holds one row per IP observation, so `(case_id, email_id)` is not unique and cannot be referenced. A target stored by the listing before any import has no rows here, which is the truth rather than a `NULL` standing in for it. Migration `20260928_07`'s downgrade is lossy by construction: the restored column has one slot, so a target reported by several emails keeps only the smallest `email_id`. They return on the next import.

**`layer_id` on `emails` only.** It is a **required** foreign key to `layers.id` `ON DELETE CASCADE`, because the import creates one `Email {email_id}` layer per email and the table is 1:1 with the point features. `email_targets` and `email_dumps` do not carry it: neither has geometry, and they were storing the *email's* layer as a proxy, which is not a property of a target or a dump — a target reported by emails in two different layers has no single answer. Migration `20260928_06` removes both columns and the link is derived:

```sql
SELECT DISTINCT e.layer_id
FROM email_targets AS t
JOIN email_target_emails AS te
  ON te.case_id = t.case_id AND te.target_id = t.target_id
JOIN emails AS e
  ON e.case_id = te.case_id AND e.email_id = te.email_id
WHERE t.case_id = :case_id AND t.target_id = :target_id
```

`DISTINCT` is needed twice over: `emails` has one row per IP so an email with four IPs matches four rows, and a target reported by two emails matches two more. All rows for one email carry the same `layer_id`, and a multi-email target legitimately spans several layers — which is exactly why `layer_id` never belonged on these tables. Dropping `NOT NULL` from the two columns is what unblocked the dropdown, since a selection names no email and therefore no layer; deleting a layer still cascades to `emails` but no longer to its neighbours, where the provider is the authority and the next listing or import rewrites the row.

`case_id` on all four tables is **not** a foreign key. GIS owns no `cases` table — cases and users belong to Central Intelligence, and migration `20260904_01` removed the local case and user FKs deliberately. It is a plain indexed integer, matching `layers.case_id` and `features.case_id`. Provider `target_id` and `dump_id` are stored as text so GIS does not assume the provider's identifier type, and integer identifiers are coerced to their digit form on the way in rather than rejected.

#### Multi-select in the dropdowns

Both dropdowns are multi-selects, so `target_id` arrives as one comma-separated string: `?target_id=1,2,3`. Values are trimmed, empty segments dropped and repeats collapsed. There is a cap of `MAX_TARGET_IDS_PER_REQUEST` (25) because a selection becomes that many upstream calls; a longer one is a 422. Ids are left opaque and not checked for being numeric, because the provider owns that type.

The provider's dumps endpoint declares `target_id` as a single `integer`, so a comma-separated value cannot be forwarded to it. The dumps route fans out, one provider call per target, issued concurrently so the request waits on the slowest target rather than the sum. A dump reported under two targets is one dropdown entry but two stored rows, since the row is keyed on `(case_id, target_id, dump_id)`; the merge keeps the first occurrence and drops the rest. A target that fails does not fail the request — the others are still returned and `target_ids` echoes the whole selection — but if every target fails there is nothing to return, and the provider's error is raised rather than answered with a silently empty list.

The origin-IP route forwards `target_id` and `dump_id` verbatim instead of fanning out, since the provider declares both as `string` there. That makes a comma-separated value type-legal and it reaches the provider intact, but nothing in the provider's spec says it splits the string — so a multi-select on *that* route depends on upstream behaviour that is not confirmed here.

### Reconciliation

The import is idempotent and case-scoped. It reconciles against the current payload rather than only inserting, so withdrawn data does not linger:

| Reconciliation step | Key |
| --- | --- |
| Layers | `case_id` + name + `module_slug` |
| Point features | Point features written, amended, left alone, or withdrawn |
| Normalised email observations | `(case_id, email_id, ip, ip_type)` |
| Targets | `(case_id, target_id)` |
| Dumps | `(case_id, target_id, dump_id)` |
| Skipped coordinates | IPs with missing or out-of-range coordinates |

There is no `features_reused`: a feature is either created, amended, untouched, or removed, and the three cases are reported separately because "nothing to do" and "changed" mean different things to a client waiting on a map.

The response does not carry those per-request counters. It returns five case-wide totals instead:

| Field | Meaning |
| --- | --- |
| `targets` | Target rows stored for the case |
| `dumps` | Dump rows stored for the case |
| `emails` | `COUNT(DISTINCT email_id)` over the case's `emails` rows |
| `ips` | Normalised IP observations stored for the case |
| `features` | Point features on the case whose `module_slug` is `email-dump` |

Three things about these numbers:

- They are cumulative for the case, not for the request. Re-importing the same filters returns the same totals instead of reporting what that one pass happened to rewrite. Counting rows after the import is also what stops a double count: a target reported both as a flat `record.target_id` and inside `record.targets[]` is stored once, and a dump reached through both paths is stored once.
- `ips` and `features` differ by design. One address seen in two roles is two `emails` rows (keyed on `case_id`, `email_id`, `ip`, `ip_type`) but a single Point feature, because the map groups by IP address. `features` is what is drawn; `ips` is the observations behind it.
- `features` is scoped by `module_slug = 'email-dump'` because a case also holds `gis` and `telecom-analysis` layers; GeoCLIP, hotspots, uploads and manual drawing are all `gis`. `targets`, `dumps`, `emails` and `ips` need no slug filter, since `email_targets`, `email_dumps` and `emails` hold only Email Dump rows.

`layers` is request-scoped: it is the list of layers *this* request produced, while the five counts are case-wide. On a filtered re-import the two will not agree, which is expected.

The per-request reconciliation is still computed and still written to the "Email Dump origin IPs imported" log line, together with a second "Email Dump case totals" line carrying the five totals. Only the returned shape changed.

### WebSocket events

New layers broadcast `layer.created`. Feature writes broadcast `feature.batch_created` for new points, `feature.batch_updated` for amended points, and `feature.batch_deleted` for withdrawn ones. Nothing new is registered.

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

```http
GET /cases/123/email-dump/origin-ips?risk_level=high&country=India
Authorization: Bearer <token>
```

GIS then calls `GET http://192.168.6.63:8002/api/emails/single/origin-ips/123?risk_level=high&country=India` with the same token, and answers:

```json
{
  "success": true,
  "case_id": 123,
  "targets": 1,
  "dumps": 2,
  "emails": 1,
  "ips": 6,
  "features": 4,
  "layers": [
    { "id": 25, "case_id": 123, "name": "Email 101",
      "layer_type": "email", "module_slug": "email-dump", "visible": true }
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

```text
feature.created            feature.batch_created
feature.updated            feature.batch_import_completed
feature.deleted            feature.batch_updated
                           feature.batch_deleted
layer.created              comment.created
layer.updated              comment.reply_created
layer.deleted              comment.deleted
```

## Measurement Features

Measurements are saved as normal features:

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

- Main application geometries use SRID 4326. MapServer OSM geometries commonly use SRID 3857, so hotspot queries transform geometries before spatial comparison.
- The backend uses typed application exceptions from `utils/exceptions.py`.
- Logs are written under `logs/`; uploaded files are stored under `uploads/`.
