# Changes in this refactor

Applied against the 17-item review plus two feature requests from this
conversation. Numbers below match the original review's numbering.

## New features (this conversation)
- **`layer_name` on both upload endpoints.** `POST /upload` (GeoCLIP)
  and `POST /import` (KML/CSV/TIFF) now accept an optional
  `layer_name` form field. If provided, it's used as the new layer's
  name. If omitted, both fall back to their previous auto-naming
  (`"Untitled {layer_id}"` for GeoCLIP, the file's basename for
  imports) — fully backward compatible with callers that don't send it.

## Critical
1. **Duplicate "group"/"auto" layer on feature draw** — `layer_service.
   create_layer()` now detects `layer_type: "group"` requests and
   reuses an existing layer with the same `case_id` + `name` instead of
   inserting a duplicate. This papers over the symptom; the actual fix
   is in your frontend, which should stop calling `POST /layers` with
   `layer_type: "group"` before drawing a feature.
2. **Layer creation duplicated across 4 code paths** — `geoclip_service.
   upload_image()` no longer builds ORM `Layer`/`Feature` objects
   directly. It now goes through `layer_service.create_layer`/
   `patch_layer` and `feature_service.create_feature`, the same
   functions the KML import path uses. This also fixes the root cause
   of GeoCLIP layers/features never showing up correctly on the
   frontend: they previously had `case_id = NULL` because the old ORM
   code never set it.
3. **Race condition in auto-layer numbering** — `create_untitled_layer`
   now takes a transaction-scoped Postgres advisory lock
   (`pg_advisory_xact_lock`, keyed on `case_id`) around the
   read-max/insert sequence, so two concurrent draw requests in the
   same case can't both compute the same next number.
4. **Path traversal via unsanitized filename** — `upload_service.
   process_upload` now sanitizes the on-disk filename via
   `os.path.basename()` plus a random prefix. The original filename is
   still used for layer naming, hashing, and logs.
5. **Client-supplied `created_by`** — `CaseCreate` and `FeatureCreate`
   no longer accept `created_by` from the request body. `create_case`
   and `create_feature` now take `created_by` as an explicit argument,
   supplied by the router from `current_user['user_id']` — the same
   pattern `comments.py` already used correctly.
6. **Dead duplicate auth system** — `utils/jwt_utils.py` deleted.
   `python-jose` removed from `requirements.txt` (only consumer was
   this file).

## High
7 & 8. **`comment_service` write ops + missing exception handling** —
   `update_comment`/`delete_comment` now check `rowcount` and raise
   `NotFoundError` on a miss. Every function in the file now wraps its
   DB call in `try/except SQLAlchemyError` → `ServiceUnavailableError`,
   consistent with `case_service.py`/`layer_service.py`.
9. **CORS wildcard** — `main.py` now uses `settings.allowed_origins_list`
   instead of `["*"]`. **You must set `ALLOWED_ORIGINS` in your `.env`**
   (see `.env.example`) or the app will reject all cross-origin requests.

## Medium
10. **`success: false` instead of proper HTTP errors** — `extract_csv`,
    `extract_kml`, and `extract_tiff` in `upload_service.py` now raise
    `BadRequestError`/`UnprocessableEntityError` instead of returning
    `{"success": False, ...}` with a 200 status.
11. **Raw SQL vs ORM split** — narrowed, not eliminated. GeoCLIP layer
    and feature creation now goes through the same raw-SQL services as
    everything else (see #2). `ImageRecord` persistence is still ORM
    since there's no raw-SQL equivalent service for images — flagged
    with a comment in `geoclip_service.py` about the resulting
    transaction-boundary trade-off (a failed image insert can no longer
    roll back the layer/features created just before it).
12. **`patch_feature` router inconsistency** — `edit_feature_partial` in
    `api/features.py` now does the same `get_feature` existence check
    before calling the service function as every other route in that
    file.
13. **`init_db.py` not wired into startup** — `main.py`'s lifespan now
    calls `init_tables()` on startup, before `geo_model.load_model()`.
    `Base.metadata.create_all()` is idempotent, so this is safe to run
    on every boot.
14. **Dual logging configuration** — removed the extra
    `logging.basicConfig(...)` call in `utils/logger.py` that attached
    a second, non-rotating file handler to the root logger.
15. **Unpinned dependency versions** — pinned in `requirements.txt`:
    `python-dotenv`, `shapely`, `geojson`, `geopandas`, `rasterio`.
    `pydantic[email]` merged into the single pinned `pydantic` line.

## Low / not changed
16. `schemas/comment_schema.py`'s `CommentCreate` is still unused by
    `api/comments.py` (which takes fields via `Form(...)` instead) —
    left as-is since removing it has no behavioral effect and no other
    file was confirmed to import it.
17. KML import still inserts features one at a time in a loop rather
    than bulk-inserting — left as-is; only worth revisiting if large
    KML files become a measured performance problem.

## Files NOT included in this zip
- `.env` (your real secrets — use `.env.example` as a template)
- `logs/`, `uploads/` sample data, `.vscode/`, `__pycache__/` — dev/local
  artifacts, regenerated automatically
- `utils/jwt_utils.py` — intentionally deleted (see #6)


