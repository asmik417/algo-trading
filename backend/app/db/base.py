"""SQLAlchemy declarative base shared by every table in app/models/.
Import Base from here; never create a second DeclarativeBase.
"""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
