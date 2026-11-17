
import sqlite3
from datetime import datetime, timezone

import pytest

from backend.audit_db import AuditDB
from backend.models import AuditLogRecord


@pytest.fixture
def audit_db(tmp_path):
    db_path = tmp_path / "test_audit.db"
    return AuditDB(db_path=db_path)


def make_audit_record(record_id="DEC-TEST-001"):
    return AuditLogRecord(
        record_id=record_id,
        timestamp=datetime.now(timezone.utc),
        shipment_id="SHIP-001",
        disruptions_detected="Vehicle breakdown",
        risk_score=75.0,
        risk_tier="HIGH",
        recommended_action="Use alternative refrigerated vehicle",
        alternatives_evaluated_count=3,
        human_decision="APPROVED",
        operator_id="operator_test",
        rationale_notes="Test approval",
        raw_payload_json='{"selected_alt_id": "ALT-001"}',
    )


def test_insert_and_retrieve_audit_record(audit_db):
    record = make_audit_record()

    audit_db.insert_audit_record(record)
    results = audit_db.get_all_records()

    assert len(results) == 1
    assert results[0].record_id == record.record_id
    assert results[0].shipment_id == record.shipment_id
    assert results[0].human_decision == record.human_decision


def test_duplicate_record_id_is_rejected(audit_db):
    first_record = make_audit_record()
    second_record = make_audit_record()

    audit_db.insert_audit_record(first_record)

    with pytest.raises(sqlite3.IntegrityError):
        audit_db.insert_audit_record(second_record)

    results = audit_db.get_all_records()

    assert len(results) == 1
    assert results[0].record_id == first_record.record_id


def test_different_record_ids_are_preserved(audit_db):
    first_record = make_audit_record("DEC-TEST-001")
    second_record = make_audit_record("DEC-TEST-002")

    audit_db.insert_audit_record(first_record)
    audit_db.insert_audit_record(second_record)

    results = audit_db.get_all_records(limit=50)

    assert len(results) == 2
    assert {record.record_id for record in results} == {
        "DEC-TEST-001",
        "DEC-TEST-002",
    }


def test_audit_records_can_be_retrieved_with_limit(audit_db):
    for number in range(3):
        audit_db.insert_audit_record(
            make_audit_record(f"DEC-TEST-{number:03d}")
        )

    results = audit_db.get_all_records(limit=2)

    assert len(results) == 2
def test_audit_record_cannot_be_updated(audit_db):
    record = make_audit_record()
    audit_db.insert_audit_record(record)

    with sqlite3.connect(audit_db.db_path) as connection:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="Audit records cannot be modified",
        ):
            connection.execute(
                "UPDATE audit_records SET human_decision = ? WHERE record_id = ?",
                ("REJECTED", record.record_id),
            )

    results = audit_db.get_all_records()
    assert results[0].human_decision == "APPROVED"


def test_audit_record_cannot_be_deleted(audit_db):
    record = make_audit_record()
    audit_db.insert_audit_record(record)

    with sqlite3.connect(audit_db.db_path) as connection:
        with pytest.raises(
            sqlite3.IntegrityError,
            match="Audit records cannot be deleted",
        ):
            connection.execute(
                "DELETE FROM audit_records WHERE record_id = ?",
                (record.record_id,),
            )

    results = audit_db.get_all_records()
    assert len(results) == 1
    assert results[0].record_id == record.record_id

def test_invalid_audit_timestamp_is_rejected(audit_db):
    record = make_audit_record()
    audit_db.insert_audit_record(record)

    # Temporarily remove the update-protection trigger in this
    # isolated test database so we can simulate corrupted data.
    with sqlite3.connect(audit_db.db_path) as connection:
        connection.execute("DROP TRIGGER prevent_audit_update")
        connection.execute(
            """
            UPDATE audit_records
            SET timestamp = ?
            WHERE record_id = ?
            """,
            ("not-a-valid-timestamp", record.record_id),
        )

    with pytest.raises(ValueError, match="Invalid timestamp"):
        audit_db.get_all_records()
