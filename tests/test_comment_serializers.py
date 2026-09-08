from datetime import datetime
from types import SimpleNamespace

from services.comment.serializers import _comment_to_dict, remember_comment_author


def test_comment_serializer_includes_distinct_author_details():
    remember_comment_author(
        {
            "user_id": 1,
            "first_name": "Sahil",
            "last_name": "Chaudhari",
            "email": "sahil@example.com",
        }
    )
    remember_comment_author(
        {
            "user_id": 2,
            "first_name": "Parth",
            "last_name": "Kulkarni",
            "email": "parth@example.com",
            "username": "parthk",
        }
    )

    first = _comment_to_dict(_comment(1))
    second = _comment_to_dict(_comment(2))

    assert first["user_full_name"] == "Sahil Chaudhari"
    assert first["user_first_name"] == "Sahil"
    assert first["user_last_name"] == "Chaudhari"
    assert first["user_email"] == "sahil@example.com"
    assert first["username"] == "sahil@example.com"

    assert second["user_full_name"] == "Parth Kulkarni"
    assert second["user_first_name"] == "Parth"
    assert second["user_last_name"] == "Kulkarni"
    assert second["user_email"] == "parth@example.com"
    assert second["username"] == "parthk"


def _comment(user_id: int):
    return SimpleNamespace(
        id=user_id,
        feature_id=10,
        feature_number=20,
        layer_id=30,
        case_id=40,
        user_id=user_id,
        parent_comment_id=None,
        root_comment_id=None,
        comment="Hello",
        attachment_filename=None,
        attachment_content_type=None,
        created_at=datetime(2026, 1, 1),
    )
