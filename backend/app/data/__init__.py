"""Data access layer.

Each module here is a repository — a thin wrapper around DB operations
for one entity. The API layer and engine layer never call SQLAlchemy
directly; they call functions from these modules.

This isolation gives us:
  - testability (can mock at the repository boundary)
  - swap-ability (could move from Postgres to anything else)
  - one place to look when a query needs optimization
"""
