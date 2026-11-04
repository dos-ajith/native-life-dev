import random
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.storage import MEDIA_URL_PREFIX
from app.models.post import Post
from app.models.post_media import PostMedia, PostMediaType
from app.models.user import User
from app.repositories.post_media_repository import PostMediaRepository
from scripts.seed_test_posts import TEST_EMAIL_DOMAIN

SAMPLE_IMAGES_SUBDIR = "sample_images"
IMAGES_PER_POST = 5


def _sample_image_urls(upload_dir: str) -> list[str]:
    directory = Path(upload_dir) / SAMPLE_IMAGES_SUBDIR
    names = sorted(path.name for path in directory.glob("*.jpg"))
    if not names:
        raise RuntimeError(f"No sample images found in {directory}")
    return [f"{MEDIA_URL_PREFIX}/{SAMPLE_IMAGES_SUBDIR}/{name}" for name in names]


def _test_posts(db: Session) -> list[Post]:
    stmt = (
        select(Post)
        .join(User, User.id == Post.user_id)
        .where(User.email.endswith(f"@{TEST_EMAIL_DOMAIN}"), Post.deleted_at.is_(None))
        .order_by(Post.created_at)
    )
    return list(db.scalars(stmt))


def seed_post_images() -> None:
    image_urls = _sample_image_urls(get_settings().upload_dir)
    db = SessionLocal()
    try:
        media = PostMediaRepository(db)
        posts = _test_posts(db)
        added = 0
        for post in posts:
            existing = media.list_by_post(post.id)
            used_urls = {item.file_url for item in existing}
            available = [url for url in image_urls if url not in used_urls]
            missing = max(IMAGES_PER_POST - len(existing), 0)
            picked = random.sample(available, min(missing, len(available)))
            for offset, url in enumerate(picked):
                media.add(
                    PostMedia(
                        post_id=post.id,
                        media_type=PostMediaType.IMAGE,
                        file_url=url,
                        sort_order=len(existing) + offset,
                    )
                )
            added += len(picked)
        print(f"Added {added} sample images across {len(posts)} test posts")
    finally:
        db.close()


if __name__ == "__main__":
    seed_post_images()
