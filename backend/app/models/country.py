from sqlalchemy import String, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class CountryRestriction(Base):
    __tablename__ = "country_restrictions"

    country_code: Mapped[str] = mapped_column(String(3), primary_key=True)
    allowed_exchanges: Mapped[list] = mapped_column(JSON)
