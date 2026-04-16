from sqlalchemy.orm import Session

from app.data.country_data import COUNTRY_EXCHANGES
from app.models.country import CountryRestriction


def seed_country_restrictions(db: Session) -> None:
    for code, exchanges in COUNTRY_EXCHANGES.items():
        existing = db.query(CountryRestriction).filter(CountryRestriction.country_code == code).first()
        if not existing:
            db.add(CountryRestriction(country_code=code, allowed_exchanges=exchanges))
    db.commit()
