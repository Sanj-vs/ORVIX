
import pytest

from backend.shipment_db import ShipmentDB, ShipmentValidationError


@pytest.fixture
def shipment_db(tmp_path):
    """Use a temporary SQLite database for every test."""
    return ShipmentDB(tmp_path / "test_shipments.db")


@pytest.fixture
def valid_shipment():
    return {
        "supplier_name": "Test Supplier",
        "contact_number": "9999999999",
        "fish_type": "Atlantic Salmon",
        "quantity_kg": 800,
        "pickup_location": "Harbour A",
        "destination": "Cold Storage B",
        "vehicle_number": "KA01TEST1234",
        "vehicle_storage_info": "Refrigerated",
        "initial_temperature_c": 2.0,
        "expected_pickup_at": "2026-11-15T10:00:00",
        "expected_delivery_at": "2026-11-15T16:00:00",
        "additional_notes": "Automated database test",
    }


def test_register_shipment_successfully(shipment_db, valid_shipment):
    record, was_created = shipment_db.create_shipment(
        valid_shipment, submission_token="token-001"
    )

    assert was_created is True
    assert record["supplier_name"] == "Test Supplier"
    assert record["quantity_kg"] == 800
    assert record["status"] == "REGISTERED"


def test_duplicate_token_does_not_create_second_shipment(
    shipment_db, valid_shipment
):
    first, first_created = shipment_db.create_shipment(
        valid_shipment, submission_token="same-token"
    )

    second, second_created = shipment_db.create_shipment(
        valid_shipment, submission_token="same-token"
    )

    assert first_created is True
    assert second_created is False
    assert first["shipment_id"] == second["shipment_id"]
    assert len(shipment_db.get_all_shipments()) == 1


def test_different_tokens_create_separate_shipments(
    shipment_db, valid_shipment
):
    first, first_created = shipment_db.create_shipment(
        valid_shipment, submission_token="token-A"
    )
    second, second_created = shipment_db.create_shipment(
        valid_shipment, submission_token="token-B"
    )

    assert first_created is True
    assert second_created is True
    assert first["shipment_id"] != second["shipment_id"]
    assert len(shipment_db.get_all_shipments()) == 2


def test_missing_supplier_is_rejected(shipment_db, valid_shipment):
    valid_shipment["supplier_name"] = ""

    with pytest.raises(ShipmentValidationError):
        shipment_db.create_shipment(valid_shipment)


@pytest.mark.parametrize("quantity", [0, -1, float("inf"), float("nan")])
def test_invalid_quantity_is_rejected(
    shipment_db, valid_shipment, quantity
):
    valid_shipment["quantity_kg"] = quantity

    with pytest.raises(ShipmentValidationError):
        shipment_db.create_shipment(valid_shipment)


@pytest.mark.parametrize("temperature", ["invalid", float("inf"), float("nan")])
def test_invalid_temperature_is_rejected(
    shipment_db, valid_shipment, temperature
):
    valid_shipment["initial_temperature_c"] = temperature

    with pytest.raises(ShipmentValidationError):
        shipment_db.create_shipment(valid_shipment)


def test_delivery_before_pickup_is_rejected(shipment_db, valid_shipment):
    valid_shipment["expected_delivery_at"] = "2026-11-15T09:00:00"

    with pytest.raises(ShipmentValidationError):
        shipment_db.create_shipment(valid_shipment)


def test_update_shipment_status(shipment_db, valid_shipment):
    record, _ = shipment_db.create_shipment(valid_shipment)

    updated = shipment_db.update_status(
        record["shipment_id"], "IN_TRANSIT"
    )

    assert updated is True
    saved = shipment_db.get_shipment(record["shipment_id"])
    assert saved["status"] == "IN_TRANSIT"
