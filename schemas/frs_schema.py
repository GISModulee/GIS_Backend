"""Payload shapes for the Face Recognition System (FRS) integration.

FRS declares HTTPBearer on every endpoint and reuses the caller's CI
token, so nothing here is about authentication. These models exist to
absorb the provider's field-name variation and its coordinate
conventions before anything reaches the map, and to keep one malformed
upstream record from failing an entire sync.
"""

import math
from datetime import datetime
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from schemas.layer_schema import LayerResponse
from utils.constants import (
    FRS_NULL_ISLAND_LATITUDE,
    FRS_NULL_ISLAND_LONGITUDE,
)


def _identifier(value: Any) -> str:
    """Normalize a provider id to its string form.

    The provider declares ids as integers, but a JSON payload, a
    hand-written fixture, or a future upstream change can deliver the
    same value as a string. Coercing both to one string form means int
    12 and "12" resolve to the *same* layer on every sync instead of
    producing a second, unreconcilable layer with an identical display
    name.

    bool is rejected explicitly: in Python ``True`` is an int, so it
    would otherwise be accepted as camera 1. Floats are accepted only
    when integral and finite, since 12.0 is a whole number in every
    sense that matters here but 12.5 is not an id.
    """
    if isinstance(value, bool):
        raise ValueError("identifier must not be a boolean")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer():
            raise ValueError("identifier must be a finite whole number")
        return str(int(value))
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValueError("identifier must not be empty")
        return stripped
    raise ValueError("identifier must be a string or a number")


def _optional_float(value: Any) -> float | None:
    """Coerce an upstream number to a finite float, or None.

    A field the provider declares nullable is not thereby guaranteed to
    arrive as null — it can be an empty string, a sentinel, or a
    boolean. None means "no usable number", which downstream code treats
    as missing rather than as zero.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _optional_text(value: Any) -> str | None:
    """Coerce an upstream string, or None when there is nothing to show.

    A blank display string is worse than an explicit null in the
    properties payload: the frontend renders "" as an empty cell with no
    way to tell it apart from a value the provider genuinely sent.
    """
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_longitude(value: Any) -> float | None:
    """Fold a 0-360 east-positive longitude into the -180..180 window.

    The provider's longitude convention is undocumented, and both
    conventions are in use in this field: some records report 359 for
    1 degree west, others report -1. Folding the 0-360 window (values in
    (180.0, 360.0] become value - 360.0) accepts the first form without
    relocating anything.

    Values outside the window are deliberately left untouched. Folding
    is only defensible for a whole-number rotation of a plausible
    longitude; anything else — 361, 2000, a latitude that landed in the
    wrong column — is corrupt data, and the range check must reject it
    rather than silently move the camera somewhere plausible.
    """
    parsed = _optional_float(value)
    if parsed is None:
        return None
    if 180.0 < parsed <= 360.0:
        return parsed - 360.0
    return parsed


def _validate_coordinate_ranges(model: Any) -> Any:
    """Reject coordinates outside the valid lat/long windows.

    Latitude and longitude are checked separately, with latitude bounded
    to -90..90 and longitude to -180..180. Note that only longitude is
    run through _normalize_longitude: folding applies to longitude only
    because it is the axis that wraps. A shared folding step over both
    axes would turn an out-of-range latitude into an in-range one
    (lat=359 becomes -1.0, lat=270 becomes -90.0) and quietly relocate
    a camera with corrupt data, which is worse than dropping it.
    """
    latitude = getattr(model, "latitude", None)
    if latitude is not None and not -90.0 <= latitude <= 90.0:
        raise ValueError(f"latitude out of range: {latitude}")

    longitude = getattr(model, "longitude", None)
    if longitude is not None and not -180.0 <= longitude <= 180.0:
        raise ValueError(f"longitude out of range: {longitude}")
    return model


def _has_usable_coordinates(latitude: float | None, longitude: float | None) -> bool:
    """Whether a coordinate pair can be plotted on the map.

    (0, 0) is a real point in the Gulf of Guinea, but FRS uses it as its
    "no fix" sentinel — an uncalibrated or unmounted camera reports it
    rather than null. Plotting it would place a fake observation in the
    middle of the Atlantic, and it is the single most common value in a
    fresh install, so it is treated as unset.
    """
    if latitude is None or longitude is None:
        return False
    if (
        latitude == FRS_NULL_ISLAND_LATITUDE
        and longitude == FRS_NULL_ISLAND_LONGITUDE
    ):
        return False
    return True


def _camera_key(camera_id: Any, longitude: float | None, latitude: float | None) -> str:
    """Build the grouping key shared by a sighting entry and its point.

    Both sides must produce byte-identical keys, because the key is what
    reconciles an incoming sighting against a feature already on the
    map. The camera id is preferred; entries with no camera id fall back
    to their coordinates.

    The coordinate fallback is sound, not a guess, because the provider
    reports the CAMERA's own lat/long on a sighting, not the subject's
    position. That is confirmed with the provider: two detections at
    identical coordinates are therefore the same camera by construction,
    since a camera does not move between two entries of one response.
    If the provider ever switched these fields to the subject's tracked
    position, the fallback would silently merge sightings taken from two
    different cameras into one map feature.
    """
    if camera_id is not None:
        return f"camera:{camera_id}"
    return f"point:{longitude},{latitude}"


class FrsCamera(BaseModel):
    """One record from GET /api/cameras."""

    camera_id: str = Field(validation_alias=AliasChoices("id", "camera_id"))
    name: str | None = Field(
        default=None,
        validation_alias=AliasChoices("name", "camera_name", "label"),
    )
    zone: str | None = None
    status: str | None = None
    latitude: float | None = Field(
        default=None, validation_alias=AliasChoices("lat", "latitude")
    )
    longitude: float | None = Field(
        default=None,
        validation_alias=AliasChoices("long", "longitude", "lng", "lon"),
    )
    frs_case_id: str | None = Field(
        default=None, validation_alias=AliasChoices("case_id", "frs_case_id")
    )

    @field_validator("camera_id", mode="before")
    @classmethod
    def _coerce_camera_id(cls, value: Any) -> str:
        return _identifier(value)

    @field_validator("name", "zone", "status", mode="before")
    @classmethod
    def _coerce_text(cls, value: Any) -> str | None:
        return _optional_text(value)

    @field_validator("latitude", mode="before")
    @classmethod
    def _coerce_latitude(cls, value: Any) -> float | None:
        # Deliberately no longitude-style folding here: latitude does not
        # wrap, and folding it would convert corrupt values into valid
        # ones. See _normalize_longitude.
        return _optional_float(value)

    @field_validator("longitude", mode="before")
    @classmethod
    def _coerce_longitude(cls, value: Any) -> float | None:
        return _normalize_longitude(value)

    @field_validator("frs_case_id", mode="before")
    @classmethod
    def _coerce_frs_case_id(cls, value: Any) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _check_ranges(self) -> "FrsCamera":
        return _validate_coordinate_ranges(self)

    @property
    def has_usable_coordinates(self) -> bool:
        return _has_usable_coordinates(self.latitude, self.longitude)


class FrsCamerasPayload(BaseModel):
    """Envelope around GET /api/cameras.

    `data` is deliberately typed as a bare list of raw values rather
    than list[FrsCamera]. FRS returns a bare array today, but a
    `{"data": [...]}` envelope is the common shape and an unwrapper
    accepts it. More importantly, holding the items raw means the
    service can validate each one independently: a single camera record
    with a corrupt coordinate is skipped and counted, instead of
    failing the entire sync because one element of a 200-camera list
    does not parse.
    """

    data: list[Any]

    @model_validator(mode="before")
    @classmethod
    def _unwrap(cls, value: Any) -> Any:
        if isinstance(value, list):
            return {"data": value}
        if isinstance(value, dict):
            for key in ("data", "cameras", "results", "items"):
                candidate = value.get(key)
                if isinstance(candidate, list):
                    return {"data": candidate}
        return value


class FrsCameraRegistryRow(BaseModel):
    """One stored row from `frs_cameras`, as the cameras route returns it.

    A read of what GIS holds, not a provider payload, so the values come
    back as they are stored — including `coordinates_changed_at`, which is
    the only record that a camera has since moved, since sightings keep
    the position they were captured at.
    """

    model_config = ConfigDict(from_attributes=True)

    camera_id: str
    name: str | None = None
    zone: str | None = None
    status: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    frs_case_id: str | None = None
    coordinates_changed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class FrsCameraRegistryResponse(BaseModel):
    """The global camera registry, synced from FRS and read back.

    One response for one cameras route, in both of its modes:

    - No `case_id` was supplied: registry half only. `data` holds the
      stored rows with their lat/long for the frontend to plot, and every
      layer/feature field below is empty or zero because nothing was
      drawn.
    - `case_id` was supplied: the same registry half, plus the layer and
      feature counts the import produced, so the caller can show the pins
      that were just written.

    `data` holds the stored rows rather than an echo of the provider
    payload: a camera the provider stops reporting is retained, so `data`
    can hold rows the current response's `cameras` count does not
    mention. Nothing is ever pruned.
    """

    success: bool = True
    # Stored registry rows, in stable camera_id order — the lat/long the
    # frontend draws from in the case-less mode.
    data: list[FrsCameraRegistryRow]
    # The case the pins were imported into, or None when the caller asked
    # for the registry alone and no case_id query parameter was sent.
    case_id: int | None = None
    # Count of cameras the provider reported, before the coordinate
    # filter. Comparing this with layers_created shows how many
    # cameras were dropped for want of a usable fix.
    cameras: int
    # Registry rows this sync inserted or amended.
    registry_created: int
    registry_updated: int
    # Stored rows whose position changed on this sync. Sightings are
    # deliberately not relocated with them; they keep their own snapshot.
    cameras_moved: int
    # Malformed records plus cameras with no usable fix (missing
    # coordinates, an out-of-range value, or the (0, 0) "no fix"
    # sentinel). Counted together because neither can be stored.
    skipped_cameras: int

    # --- Layer/feature half, written only when case_id was supplied ----
    layers: list[LayerResponse] = Field(default_factory=list)
    # Layers created by this request.
    layers_created: int = 0
    # Layers whose name and module_slug already existed and were reused.
    layers_reused: int = 0
    # FRS layers in this case whose names are no longer reported. They
    # are deliberately left untouched: an analyst may have commented on
    # them or attached evidence, and a camera being withdrawn upstream
    # is not a reason to destroy the record of what was observed from
    # it. This is reported, never deleted.
    layers_stale: int = 0
    # Point features written by this request.
    features_created: int = 0
    # Features whose stored name, geometry or properties differed from
    # the current payload.
    features_updated: int = 0
    # Features that already matched the payload exactly. Nothing was
    # written and no update was broadcast for these.
    features_unchanged: int = 0


class FrsPerson(BaseModel):
    """One record from GET /api/persons.

    `thumbnail_base64` is forwarded verbatim from the upstream payload: it
    is display-only, so it rides along on this model for the /persons
    response instead of being stored — `frs_persons` has no thumbnail
    column, and none is wanted. The value is passed through unchanged; the
    frontend is responsible for checking whether it already carries a
    `data:` prefix before rendering it.
    """

    person_id: str = Field(validation_alias=AliasChoices("id", "person_id"))
    name: str | None = None
    organization: str | None = None
    # The provider's own face image, base64-encoded. Tens of kilobytes per
    # person, which is why it is read-only here: /persons forwards it so
    # the dropdown gets a face per row in one request, and no write path
    # ever touches it.
    thumbnail_base64: str | None = None
    tags: list[str] = Field(default_factory=list)
    # The provider's multi-case membership array. A person can belong to
    # several cases at once, which is why this is a list and not the
    # single frs_case_id the camera payload carries.
    case_ids: list[str] = Field(default_factory=list)

    @field_validator("person_id", mode="before")
    @classmethod
    def _coerce_person_id(cls, value: Any) -> str:
        return _identifier(value)

    @field_validator("name", "organization", "thumbnail_base64", mode="before")
    @classmethod
    def _coerce_text(cls, value: Any) -> str | None:
        return _optional_text(value)

    @field_validator("tags", "case_ids", mode="before")
    @classmethod
    def _coerce_tags(cls, value: Any) -> list[str]:
        # case_ids shares this validator: both are arrays of display strings
        # on the same provider payload, and a malformed one becomes an
        # empty list rather than failing the whole person record.
        if not isinstance(value, (list, tuple)):
            return []
        return [tag for tag in (_optional_text(item) for item in value) if tag]


class FrsPersonsResponse(BaseModel):
    success: bool = True
    case_id: int
    persons: list[FrsPerson]


class FrsPersonHistoryEntry(BaseModel):
    """One record from GET /api/persons/{person_id}/history.

    The provider emits one entry per *detection*, so the same camera
    with the same coordinates appears many times. camera_id, camera_name,
    lat and long are all nullable upstream: an entry may be reconstructed
    from a stored clip with no camera attribution, or from a detection
    whose coordinates were never recovered.
    """

    source: str | None = None
    camera_id: str | None = Field(
        default=None, validation_alias=AliasChoices("camera_id", "camera")
    )
    camera_name: str | None = None
    latitude: float | None = Field(
        default=None, validation_alias=AliasChoices("lat", "latitude")
    )
    longitude: float | None = Field(
        default=None,
        validation_alias=AliasChoices("long", "longitude", "lng", "lon"),
    )
    confidence: float | None = None
    similarity: float | None = None
    started_at: str | None = None
    ended_at: str | None = None
    # The provider declares video_id as an integer, but it is the key half
    # of a sighting's ordering, so it goes through the same _identifier
    # coercion as the other ids: 0 must become "0" and match the string the
    # database stores, or the same detection would insert twice.
    video_id: str | None = None
    video_filename: str | None = None

    @field_validator("camera_id", mode="before")
    @classmethod
    def _coerce_camera_id(cls, value: Any) -> str | None:
        if value is None:
            return None
        return _identifier(value)

    @field_validator("video_id", mode="before")
    @classmethod
    def _coerce_video_id(cls, value: Any) -> str | None:
        if value is None:
            return None
        return _identifier(value)

    @field_validator("source", "camera_name", "video_filename", mode="before")
    @classmethod
    def _coerce_text(cls, value: Any) -> str | None:
        return _optional_text(value)

    @field_validator("latitude", mode="before")
    @classmethod
    def _coerce_latitude(cls, value: Any) -> float | None:
        # Longitude-only folding, for the same reason as FrsCamera.
        return _optional_float(value)

    @field_validator("longitude", mode="before")
    @classmethod
    def _coerce_longitude(cls, value: Any) -> float | None:
        return _normalize_longitude(value)

    @field_validator("confidence", "similarity", mode="before")
    @classmethod
    def _coerce_score(cls, value: Any) -> float | None:
        return _optional_float(value)

    @field_validator("started_at", "ended_at", mode="before")
    @classmethod
    def _coerce_timestamp(cls, value: Any) -> str | None:
        return _optional_text(value)

    @model_validator(mode="after")
    def _check_ranges(self) -> "FrsPersonHistoryEntry":
        return _validate_coordinate_ranges(self)

    @property
    def has_usable_coordinates(self) -> bool:
        return _has_usable_coordinates(self.latitude, self.longitude)

    @property
    def has_timestamp(self) -> bool:
        """Whether this entry can be placed in time at all.

        The provider issues no per-detection id, so (video_id, started_at)
        used to be the only key a sighting could have. Camera-source
        detections break that: they carry a camera and a started_at but no
        video, and they are exactly the detections with coordinates, so
        they must reach the registry. The one thing that is never
        negotiable is the timestamp — an entry without one cannot be
        ordered against anything, and grafting a clock onto it would
        fabricate a sequence the data does not support, so it is skipped
        and counted instead.
        """
        return self.started_at is not None

    @property
    def camera_key(self) -> str:
        return _camera_key(self.camera_id, self.longitude, self.latitude)


class FrsPersonHistoryPoint(BaseModel):
    """A collapse of many detections at one place into one map feature.

    The provider reports one history entry per detection, so a person
    walking past a camera produces a long run of entries at the same
    coordinates. One feature per entry would stack near-identical pins on
    top of each other and bury the places that actually matter, so
    entries are collapsed per camera into a single point carrying the
    sighting count and the time window.
    """

    person_id: str | None = None
    person_name: str | None = None
    camera_id: str | None = None
    camera_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    # Number of detections collapsed into this point. A single sighting
    # yields 1, so the value distinguishes "seen once" from "seen many
    # times" on the map without opening a popup.
    sighting_count: int = 1
    confidence: float | None = None
    similarity: float | None = None
    source: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None
    # Distinct video filenames the detections were drawn from, so an
    # analyst can pull the underlying footage for this place.
    videos: list[str] = Field(default_factory=list)

    @property
    def camera_key(self) -> str:
        return _camera_key(self.camera_id, self.longitude, self.latitude)


class FrsPersonHistoryImportResponse(BaseModel):
    success: bool = True
    case_id: int
    person_id: int
    person_name: str | None = None
    # Set when the person's detections carry no usable coordinates, so the
    # reason there are no points is explicit instead of a bare matter of
    # counting. Null means no message is needed.
    message: str | None = None
    # Raw detections the provider reported, before the coordinate
    # filter and the per-camera collapse.
    entries: int
    # Map features after collapsing: one per place the person was seen,
    # not one per detection.
    points: int
    layers: list[LayerResponse]
    layers_created: int
    # Detections dropped for missing coordinates, an out-of-range value,
    # or the (0, 0) "no fix" sentinel.
    skipped_entries: int
    # Detections written to frs_person_sightings as stored rows. This is the
    # durable, ordered record the route view reads; `points` above is the
    # collapsed map layer and will always be much smaller.
    sightings_created: int = 0
    # Stored sightings whose payload changed. Nothing is ever deleted, so a
    # sighting the provider stops reporting is retained, not counted here.
    sightings_updated: int = 0
    # Detections with no video_id or no started_at, so they cannot be placed
    # in time. Counted separately from skipped_entries on purpose: "cannot be
    # ordered" and "has no coordinates" are different failures and the
    # frontend has to show them differently.
    sightings_unordered: int = 0


class FrsSightingPoint(BaseModel):
    """One stored detection, as returned for a route.

    Every point is a detection AT a camera, not a measured position of the
    subject: the provider reports the camera's own coordinates, so a person
    walking ten metres past a lens is still reported at the lens. The
    sequence is a sequence of observations, not of locations travelled.

    `sequence` is assigned by the server from database order so the frontend
    can index a polyline directly instead of re-deriving the sort and
    risking a different order than the one it stored.
    """

    sequence: int
    person_id: str | None = None
    video_id: str | None = None
    started_at: datetime
    ended_at: datetime | None = None
    camera_id: str | None = None
    camera_name: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    confidence: float | None = None
    similarity: float | None = None
    source: str | None = None
    video_filename: str | None = None
    # True when the camera had a registry position at import time and this
    # sighting's coordinates disagreed with it, i.e. the camera has since
    # moved. The stored coordinates are deliberately left as captured.
    camera_moved: bool = False


class FrsPersonRouteResponse(BaseModel):
    """One person's sightings in time order.

    `single_video` reports how far the ordering can be trusted. Within a
    single video_id the sequence is sound: one camera, one clock, so the
    timestamps are mutually consistent. Across videos it rests on the
    provider normalising every camera to UTC, which it asserts but exposes
    no way to verify — there is no clock-sync or NTP field anywhere in the
    camera payload. A multi-camera route should therefore be presented as an
    INFERRED sequence rather than a measured path.

    `camera_ids` is deduplicated in first-seen order. Revisiting a camera is
    legitimate; the caller asked for the distinct stops, not for the raw
    sequence, which is already in `sightings`.
    """

    success: bool = True
    case_id: int
    person_id: str
    person_name: str | None = None
    single_video: bool
    camera_ids: list[str] = Field(default_factory=list)
    sightings: list[FrsSightingPoint] = Field(default_factory=list)
    sightings_count: int = 0
    moved_camera_sightings: int = 0
