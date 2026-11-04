from app.core.database import SessionLocal
from app.services.deal_expiry_service import DealExpiryService


def expire_deals() -> int:
    with SessionLocal() as db:
        return DealExpiryService(db).expire_overdue()


if __name__ == "__main__":
    print(f"Expired {expire_deals()} deal(s) awaiting acceptance past their deadline")
