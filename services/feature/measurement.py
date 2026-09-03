from schemas.feature_schema import FeatureCreate
from services.feature.create import create_feature
from services.feature.queries import get_feature


async def save_measurement_feature(
    db,
    case_id: int,
    layer_id: int,
    geometry: dict,
    measurement_type: str,
    distance_meters: float,
    user_id: int,
) -> dict:
    result = await create_feature(
        FeatureCreate(
            case_id=case_id,
            layer_id=layer_id,
            name=f"{measurement_type.title()} measurement",
            geometry=geometry,
            geometry_type="measurement",
            properties={
                "measurement_type": measurement_type,
                "distance_meters": distance_meters,
            },
        ),
        db,
        user_id,
    )
    return await get_feature(result["feature_id"], db)
