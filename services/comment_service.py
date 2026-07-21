from fastapi import UploadFile
from fastapi.responses import Response
from sqlalchemy import text

from database.database import engine
from utils.logger import logger
from utils.exception_handler import NotFoundError


# ===================================================
# CREATE COMMENT
# ===================================================

def create_comment(feature_id, user_id, comment, image: UploadFile | None = None):

    logger.info(f"Creating comment | feature_id={feature_id} | user_id={user_id}")

    image_data = None

    if image is not None:
        image.file.seek(0)
        image_data = image.file.read()

    with engine.begin() as conn:

        result = conn.execute(

            text("""

                INSERT INTO comments
                (
                    feature_id,
                    user_id,
                    comment,
                    image_data
                )

                VALUES
                (
                    :feature_id,
                    :user_id,
                    :comment,
                    :image_data
                )

                RETURNING id

            """),

            {
                "feature_id": feature_id,
                "user_id": user_id,
                "comment": comment,
                "image_data": image_data
            }

        )

        comment_id = result.scalar()

    logger.info(f"Comment created | comment_id={comment_id} | feature_id={feature_id}")

    return {
        "success": True,
        "comment_id": comment_id,
        "message": "Comment added successfully"
    }


# ===================================================
# GET COMMENTS OF A FEATURE
# ===================================================

def get_feature_comments(feature_id):

    logger.info(f"Fetching comments | feature_id={feature_id}")

    with engine.connect() as conn:

        result = conn.execute(

            text("""

                SELECT

                    id,
                    feature_id,
                    user_id,
                    comment,
                    image_data,
                    created_at

                FROM comments

                WHERE feature_id = :feature_id

                ORDER BY created_at ASC

            """),

            {
                "feature_id": feature_id
            }

        )

        comments = []

        for row in result:

            comments.append({

                "id": row.id,
                "feature_id": row.feature_id,
                "user_id": row.user_id,
                "comment": row.comment,
                "has_image": row.image_data is not None,
                "created_at": row.created_at

            })

    return comments


# ===================================================
# UPDATE COMMENT
# ===================================================

def update_comment(comment_id, comment):

    logger.info(f"Updating comment | comment_id={comment_id}")

    with engine.begin() as conn:

        conn.execute(

            text("""

                UPDATE comments

                SET

                    comment = :comment

                WHERE id = :id

            """),

            {
                "id": comment_id,
                "comment": comment.comment
            }

        )

    logger.info(f"Comment updated | comment_id={comment_id}")

    return {
        "success": True,
        "message": "Comment updated successfully"
    }


# ===================================================
# DELETE COMMENT
# ===================================================

def delete_comment(comment_id):

    logger.info(f"Deleting comment | comment_id={comment_id}")

    with engine.begin() as conn:

        conn.execute(

            text("""

                DELETE FROM comments

                WHERE id = :id

            """),

            {
                "id": comment_id
            }

        )

    logger.info(f"Comment deleted | comment_id={comment_id}")

    return {
        "success": True,
        "message": "Comment deleted successfully"
    }


# ===================================================
# GET COMMENT IMAGE
# ===================================================

def get_comment_image(comment_id):

    logger.info(f"Fetching comment image | comment_id={comment_id}")

    with engine.connect() as conn:

        result = conn.execute(

            text("""
                SELECT image_data
                FROM comments
                WHERE id = :id
            """),

            {
                "id": comment_id
            }

        )

        row = result.fetchone()

        if row is None:
            logger.warning(f"Comment image fetch failed: comment not found | comment_id={comment_id}")
            raise NotFoundError("Comment not found")

        if row.image_data is None:
            logger.warning(f"Comment image fetch failed: no image | comment_id={comment_id}")
            raise NotFoundError("No image found")

        return Response(
            content=row.image_data,
            media_type="image/jpeg"
        )
