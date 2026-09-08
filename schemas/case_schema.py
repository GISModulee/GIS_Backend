from typing import Optional

from pydantic import BaseModel


class CaseResponse(BaseModel):
    """A case as represented by Central Intelligence.

    GIS does not own a local Case source of truth. ``id`` is the
    external CI Case ID referenced by GIS data (case_id columns) as a
    plain integer.
    """
    id: int
    case_number: str
    case_name: str
    is_active: bool
