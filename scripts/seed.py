from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User, UserStatus, UserType
from app.repositories.user_repository import UserRepository

DEV_USER_EMAIL = "dev@nativelife.example"
DEV_USER_PASSWORD = "Password123!"


def seed_dev_user() -> None:
    db = SessionLocal()
    try:
        repository = UserRepository(db)
        if repository.get_by_email(DEV_USER_EMAIL) is not None:
            print(f"Dev user already exists: {DEV_USER_EMAIL}")
            return
        user = User(
            first_name="Dev",
            last_name="User",
            email=DEV_USER_EMAIL,
            password_hash=hash_password(DEV_USER_PASSWORD),
            status=UserStatus.ACTIVE,
            user_type=UserType.PRIVATE,
        )
        db.add(user)
        db.commit()
        print(f"Seeded dev user: {DEV_USER_EMAIL} / {DEV_USER_PASSWORD}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_dev_user()
