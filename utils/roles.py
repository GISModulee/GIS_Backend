# ============================================================
# Role groups — single source of truth for who can do what.
#
# Priority (highest to lowest): Admin > Officer > Analyst > Viewer
#
#   Admin   — full control. Only role that can delete a Case (the
#             top-level container) or manage users.
#   Officer — runs day-to-day investigations. Can create/edit
#             cases/layers/features, delete layers/features (tactical
#             data), but cannot delete a Case itself.
#   Analyst — contributes intelligence: creates/edits features, layers,
#             comments, uploads GeoCLIP images. Cannot delete anything
#             at the case/layer level, and cannot delete a case.
#   Viewer  — read-only everywhere. No create/update/delete of any kind.
#
# Every authenticated user (any of the four roles) can read. Only the
# groups below need explicit role checks — reads just use
# Depends(get_current_user) with no role restriction.
# ============================================================

ADMIN = "Admin"
OFFICER = "Officer"
ANALYST = "Analyst"
VIEWER = "Viewer"

ALL_ROLES = [ADMIN, OFFICER, ANALYST, VIEWER]

# Can create/update cases, layers, features (day-to-day investigation work)
CAN_WRITE = [ADMIN, OFFICER, ANALYST]

# Can delete layers, features, comments, GeoCLIP layers (tactical/operational data)
CAN_DELETE_OPERATIONAL = [ADMIN, OFFICER]

# Can delete a Case outright (the top-level, destructive action)
CAN_DELETE_CASE = [ADMIN]

# Can upload files (GeoCLIP images, KML/CSV/TIFF imports)
CAN_UPLOAD = [ADMIN, OFFICER, ANALYST]

# Can post comments (Viewer is read-only, doesn't participate)
CAN_COMMENT = [ADMIN, OFFICER, ANALYST]

# Admin-only actions (user management, etc.)
ADMIN_ONLY = [ADMIN]