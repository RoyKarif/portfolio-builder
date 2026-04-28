"""Re-export all ORM models so they get registered on Base.metadata.

Alembic's autogenerate inspects Base.metadata to detect schema changes.
For a class to appear in Base.metadata, the class must be *imported*
somewhere — Python only "knows" about a class once its module runs.

Importing them here means anyone doing `from app.models import ...` or
even `import app.models` ensures the registration happens.
"""

from app.models.user import User
from app.models.asset import Asset
from app.models.price import Price
from app.models.portfolio import Portfolio

# Explicit __all__ so `from app.models import *` works predictably.
__all__ = ["User", "Asset", "Price", "Portfolio"]
