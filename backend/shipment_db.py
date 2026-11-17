"""SQLite persistence for shipment registration and status tracking."""

import math
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union


DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "shipments.db"


class ShipmentValidationError(ValueError):
    """Raised when shipment data or a shipment status is invalid."""


class ShipmentDB:
    """Create, retrieve, and update shipment records stored in SQLite."""

    ALLOWED_STATUSES = {
        "REGISTERED",
        "IN_TRANSIT",
        "DELIVERED",
        "DELAYED",
        "DISRUPTED",
        "CANCELLED",
    }

    def __init__(self, db_path: Optional[Union[str, Path]] = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else DEFAULT_DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(str(self.db_path), timeout=30)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        connection = self._connect()
        try:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS shipments (
                    shipment_id TEXT PRIMARY KEY,
                    submission_token TEXT UNIQUE,
                    supplier_name TEXT NOT NULL,
                    contact_number TEXT NOT NULL,
                    fish_type TEXT NOT NULL,
                    quantity_kg REAL NOT NULL CHECK (quantity_kg > 0),
                    pickup_location TEXT NOT NULL,
                    destination TEXT NOT NULL,
                    vehicle_number TEXT NOT NULL,
                    vehicle_storage_info TEXT NOT NULL,
                    initial_temperature_c REAL,
                    expected_pickup_at TEXT,
                    expected_delivery_at TEXT,
                    additional_notes TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_shipments_created_at "
                "ON shipments (created_at DESC)"
            )
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _clean_text(
        shipment_data: Mapping[str, Any],
        field: str,
        *,
        required: bool = False,
    ) -> Optional[str]:
        value = shipment_data.get(field)
        if value is None:
            cleaned = ""
        else:
            cleaned = str(value).strip()
        if required and not cleaned:
            raise ShipmentValidationError(f"{field.replace('_', ' ').capitalize()} is required.")
        return cleaned or None

    @staticmethod
    def _clean_datetime(value: Any, field: str) -> Optional[str]:
        if value is None or value == "":
            return None
        if isinstance(value, datetime):
            return value.isoformat(timespec="seconds")
        if isinstance(value, date):
            return datetime.combine(value, datetime.min.time()).isoformat(timespec="seconds")
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return None
            try:
                return datetime.fromisoformat(cleaned).isoformat(timespec="seconds")
            except ValueError as exc:
                raise ShipmentValidationError(
                    f"{field.replace('_', ' ').capitalize()} must be an ISO date or datetime."
                ) from exc
        raise ShipmentValidationError(
            f"{field.replace('_', ' ').capitalize()} must be a date or datetime."
        )

    @classmethod
    def _validate_shipment(cls, shipment_data: Mapping[str, Any]) -> Dict[str, Any]:
        if not isinstance(shipment_data, Mapping):
            raise ShipmentValidationError("Shipment data must be a mapping.")

        cleaned: Dict[str, Any] = {
            "supplier_name": cls._clean_text(shipment_data, "supplier_name", required=True),
            "contact_number": cls._clean_text(shipment_data, "contact_number", required=True),
            "fish_type": cls._clean_text(shipment_data, "fish_type", required=True),
            "pickup_location": cls._clean_text(shipment_data, "pickup_location", required=True),
            "destination": cls._clean_text(shipment_data, "destination", required=True),
            "vehicle_number": cls._clean_text(shipment_data, "vehicle_number") or "",
            "vehicle_storage_info": cls._clean_text(shipment_data, "vehicle_storage_info") or "",
            "additional_notes": cls._clean_text(shipment_data, "additional_notes") or "",
            "expected_pickup_at": cls._clean_datetime(
                shipment_data.get("expected_pickup_at"), "expected_pickup_at"
            ),
            "expected_delivery_at": cls._clean_datetime(
                shipment_data.get("expected_delivery_at"), "expected_delivery_at"
            ),
        }

        try:
            quantity = float(shipment_data["quantity_kg"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ShipmentValidationError("Quantity kg must be a positive number.") from exc
        if not math.isfinite(quantity) or quantity <= 0:
            raise ShipmentValidationError("Quantity kg must be a positive number.")
        cleaned["quantity_kg"] = quantity

        temperature = shipment_data.get("initial_temperature_c")
        if temperature is None or (isinstance(temperature, str) and not temperature.strip()):
            cleaned["initial_temperature_c"] = None
        else:
            try:
                temperature_value = float(temperature)
            except (TypeError, ValueError) as exc:
                raise ShipmentValidationError(
                    "Initial temperature c must be a finite number."
                ) from exc
            if not math.isfinite(temperature_value):
                raise ShipmentValidationError("Initial temperature c must be a finite number.")
            cleaned["initial_temperature_c"] = temperature_value

        pickup = cleaned["expected_pickup_at"]
        delivery = cleaned["expected_delivery_at"]
        if pickup and delivery:
            pickup_dt = datetime.fromisoformat(pickup)
            delivery_dt = datetime.fromisoformat(delivery)
            if pickup_dt.tzinfo != delivery_dt.tzinfo:
                pickup_dt = pickup_dt.astimezone() if pickup_dt.tzinfo else pickup_dt
                delivery_dt = delivery_dt.astimezone() if delivery_dt.tzinfo else delivery_dt
            if delivery_dt <= pickup_dt:
                raise ShipmentValidationError(
                    "Expected delivery must be later than expected pickup."
                )

        return cleaned

    @staticmethod
    def generate_shipment_id() -> str:
        return f"SHP-{datetime.now().astimezone():%Y%m%d}-{uuid.uuid4().hex[:8].upper()}"

    def save_shipment(
        self,
        shipment_data: Mapping[str, Any],
        submission_token: Optional[str] = None,
    ) -> tuple[Dict[str, Any], bool]:
        """Save a shipment and return its record and whether it was created.

        Reusing a submission token returns the existing record, preventing
        duplicate records when a form submission is retried.
        """
        cleaned = self._validate_shipment(shipment_data)
        token = str(submission_token).strip() if submission_token else None
        token = token or None

        connection = self._connect()
        try:
            if token:
                existing = connection.execute(
                    "SELECT * FROM shipments WHERE submission_token = ?", (token,)
                ).fetchone()
                if existing:
                    return dict(existing), False

            now = datetime.now().astimezone().isoformat(timespec="seconds")
            shipment_id = self.generate_shipment_id()
            connection.execute(
                """
                INSERT INTO shipments (
                    shipment_id, submission_token, supplier_name, contact_number,
                    fish_type, quantity_kg, pickup_location, destination,
                    vehicle_number, vehicle_storage_info, initial_temperature_c,
                    expected_pickup_at, expected_delivery_at, additional_notes,
                    status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'REGISTERED', ?, ?)
                """,
                (
                    shipment_id,
                    token,
                    cleaned["supplier_name"],
                    cleaned["contact_number"],
                    cleaned["fish_type"],
                    cleaned["quantity_kg"],
                    cleaned["pickup_location"],
                    cleaned["destination"],
                    cleaned["vehicle_number"],
                    cleaned["vehicle_storage_info"],
                    cleaned["initial_temperature_c"],
                    cleaned["expected_pickup_at"],
                    cleaned["expected_delivery_at"],
                    cleaned["additional_notes"],
                    now,
                    now,
                ),
            )
            connection.commit()
            saved = connection.execute(
                "SELECT * FROM shipments WHERE shipment_id = ?", (shipment_id,)
            ).fetchone()
            if saved is None:
                raise sqlite3.DatabaseError("Saved shipment could not be read back.")
            return dict(saved), True
        except sqlite3.IntegrityError:
            connection.rollback()
            if token:
                existing = connection.execute(
                    "SELECT * FROM shipments WHERE submission_token = ?", (token,)
                ).fetchone()
                if existing:
                    return dict(existing), False
            raise
        finally:
            connection.close()

    def get_shipment(self, shipment_id: str) -> Optional[Dict[str, Any]]:
        connection = self._connect()
        try:
            row = connection.execute(
                "SELECT * FROM shipments WHERE shipment_id = ?", (shipment_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def get_all_shipments(self, limit: int = 500) -> List[Dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 5000))
        connection = self._connect()
        try:
            rows = connection.execute(
                "SELECT * FROM shipments ORDER BY created_at DESC LIMIT ?",
                (safe_limit,),
            ).fetchall()
            return [dict(row) for row in rows]
        finally:
            connection.close()

    def update_status(self, shipment_id: str, new_status: str) -> bool:
        """Update a shipment's operational status; return False if not found."""
        status = str(new_status).strip().upper()
        if status not in self.ALLOWED_STATUSES:
            allowed = ", ".join(sorted(self.ALLOWED_STATUSES))
            raise ShipmentValidationError(f"Status must be one of: {allowed}.")

        now = datetime.now().astimezone().isoformat(timespec="seconds")
        connection = self._connect()
        try:
            cursor = connection.execute(
                """
                UPDATE shipments
                SET status = ?, updated_at = ?
                WHERE shipment_id = ?
                """,
                (status, now, shipment_id),
            )
            connection.commit()
            return cursor.rowcount > 0
        finally:
            connection.close()

    def create_shipment(self, shipment_data, submission_token=None):
        """
        Compatibility method for the shipment registration page.
        Reuses the existing save_shipment database implementation.
        """
        return self.save_shipment(
            shipment_data,
            submission_token=submission_token
        )
