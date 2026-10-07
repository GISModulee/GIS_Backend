"""Face Recognition System integration.

Three modules, three jobs:

- `cameras` fetches the provider's global camera registry, stores it,
  and — when the caller supplies the optional case_id — writes one layer
  per camera, one Point feature each.
- `persons` fetches a case's persons and one person's sighting history,
  collapsing per-detection entries into one point per camera for the map.
- `registry` holds the provider's records as real rows (cameras, persons,
  raw sightings) so the full detection detail and its time ordering
  survive. It is read by the route endpoint, which answers "in what order
  was this person seen" — something the map layer cannot, because the
  collapse that makes the map readable is exactly what destroys the
  ordering.
"""

from services.frs.cameras import (
    CameraLayerImport,
    CameraRegistrySync,
    build_cameras_url,
    fetch_cameras,
    fetch_json,
    import_camera_layers,
    layer_name_for_camera,
    read_camera_registry,
    sync_camera_registry,
)
from services.frs.persons import (
    build_person_history_url,
    build_persons_url,
    collapse_sightings,
    fetch_person_history,
    fetch_persons,
    feature_name_for_point,
    import_person_history,
    layer_name_for_person,
)
from services.frs.registry import (
    link_person_layer,
    list_cameras,
    list_route,
    person_route,
    upsert_cameras,
    upsert_persons,
    upsert_sightings,
)

__all__ = [
    "build_cameras_url",
    "build_person_history_url",
    "build_persons_url",
    "CameraLayerImport",
    "CameraRegistrySync",
    "collapse_sightings",
    "fetch_cameras",
    "fetch_json",
    "fetch_person_history",
    "fetch_persons",
    "feature_name_for_point",
    "import_camera_layers",
    "import_person_history",
    "layer_name_for_camera",
    "layer_name_for_person",
    "link_person_layer",
    "list_cameras",
    "list_route",
    "person_route",
    "read_camera_registry",
    "sync_camera_registry",
    "upsert_cameras",
    "upsert_persons",
    "upsert_sightings",
]