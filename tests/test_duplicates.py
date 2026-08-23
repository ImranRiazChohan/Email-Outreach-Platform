import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database.connection import Base
from database import crud
import database.models  # noqa: F401 - registers models on Base
from services.duplicate_service import DuplicateReason, check_duplicate


@pytest.fixture()
def session():
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, future=True)
    db_session = SessionLocal()
    try:
        yield db_session
    finally:
        db_session.close()


def _make_lead(session, **overrides):
    fields = dict(
        google_place_id="place_1",
        business_name="Test School",
        website_domain="testschool.com",
        normalized_phone="923001234567",
    )
    fields.update(overrides)
    return crud.create_lead(session, **fields)


def test_duplicate_by_place_id(session):
    _make_lead(session)
    result = check_duplicate(session, google_place_id="place_1", website_domain=None, normalized_phone=None)
    assert result.is_duplicate
    assert result.reason == DuplicateReason.PLACE_ID


def test_duplicate_by_website_domain(session):
    _make_lead(session)
    result = check_duplicate(
        session, google_place_id="place_2", website_domain="testschool.com", normalized_phone=None
    )
    assert result.is_duplicate
    assert result.reason == DuplicateReason.WEBSITE_DOMAIN


def test_duplicate_by_normalized_phone(session):
    _make_lead(session)
    result = check_duplicate(
        session, google_place_id="place_3", website_domain=None, normalized_phone="923001234567"
    )
    assert result.is_duplicate
    assert result.reason == DuplicateReason.PHONE


def test_not_a_duplicate_when_nothing_matches(session):
    _make_lead(session)
    result = check_duplicate(
        session, google_place_id="place_4", website_domain="other.com", normalized_phone="923009999999"
    )
    assert not result.is_duplicate
    assert result.reason == DuplicateReason.NONE


def test_google_place_id_unique_constraint_enforced(session):
    _make_lead(session)
    with pytest.raises(Exception):
        crud.create_lead(session, google_place_id="place_1", business_name="Duplicate Place ID")
        session.flush()
