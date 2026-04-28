"""Pydantic schemas — request and response shapes for the API.

Different from ORM models: ORM models map to DB rows. Schemas describe
the JSON over the wire. They share fields, but separating them lets us
control exactly what gets sent (e.g., never password_hash).
"""
