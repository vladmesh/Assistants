from datetime import UTC

from sqlmodel import Field

from models.base import BaseModel, get_utc_now


class Dummy(BaseModel, table=True):
    id: int | None = Field(default=None, primary_key=True)


def test_get_utc_now_returns_aware():
    dt = get_utc_now()
    assert dt.tzinfo is UTC


def test_base_model_datetimes_are_aware_by_default():
    instance = Dummy()
    assert instance.created_at.tzinfo is UTC
    assert instance.updated_at.tzinfo is UTC
