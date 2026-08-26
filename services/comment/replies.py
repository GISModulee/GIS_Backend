from fastapi import UploadFile

from services.comment.create import create_comment

def create_reply(case_id, layer_id, feature_number, parent_comment_id, user_id, comment, attachment: UploadFile | None = None):
    return create_comment(
        case_id,
        layer_id,
        feature_number,
        user_id,
        comment,
        attachment,
        parent_comment_id=parent_comment_id,
    )
