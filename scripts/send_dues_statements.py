from app.core.database import SessionLocal
from app.services.dues_service import DuesService


def main() -> None:
    with SessionLocal() as db:
        sent = DuesService(db).send_statements()
    print(f"Sent {sent} COD dues statement(s)")


if __name__ == "__main__":
    main()
