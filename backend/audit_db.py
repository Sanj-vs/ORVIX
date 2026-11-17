"""
Audit Database & Governance Store
Implements persistent local audit trail using SQLite to record every sensing event,
predictive risk calculation, recovery recommendation, and human approval decision.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from .models import AuditLogRecord

DB_PATH = Path(__file__).resolve().parent.parent / "orvix_audit.db"


class AuditDB:
    """Manages append-only audit trail of human-in-the-loop decisions."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = str(db_path or DB_PATH)
        self._init_db()

    def _init_db(self) -> None:
        """Create audit table if not exists."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_records (
                    record_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    shipment_id TEXT NOT NULL,
                    disruptions_detected TEXT,
                    risk_score REAL NOT NULL,
                    risk_tier TEXT NOT NULL,
                    recommended_action TEXT NOT NULL,
                    alternatives_evaluated_count INTEGER NOT NULL,
                    human_decision TEXT NOT NULL,
                    operator_id TEXT NOT NULL,
                    rationale_notes TEXT,
                    raw_payload_json TEXT
                )
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS prevent_audit_update
                BEFORE UPDATE ON audit_records
                BEGIN
                    SELECT RAISE(ABORT, 'Audit records cannot be modified');
                END
            """)
            cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS prevent_audit_delete
                BEFORE DELETE ON audit_records
                BEGIN
                    SELECT RAISE(ABORT, 'Audit records cannot be deleted');
                END
            """)
            conn.commit()
        finally:
            conn.close()
    def insert_audit_record(self, record: AuditLogRecord) -> None:
        """Insert a decision record into the audit log."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_records (
                    record_id, timestamp, shipment_id, disruptions_detected,
                    risk_score, risk_tier, recommended_action, alternatives_evaluated_count,
                    human_decision, operator_id, rationale_notes, raw_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.record_id,
                record.timestamp.isoformat(),
                record.shipment_id,
                record.disruptions_detected,
                record.risk_score,
                record.risk_tier,
                record.recommended_action,
                record.alternatives_evaluated_count,
                record.human_decision,
                record.operator_id,
                record.rationale_notes,
                record.raw_payload_json
            ))
            conn.commit()
        finally:
            conn.close()

    def get_all_records(self, limit: int = 50) -> List[AuditLogRecord]:
        """Fetch audit log records descending by timestamp."""
        records: List[AuditLogRecord] = []
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM audit_records
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            for row in cursor.fetchall():
                try:
                    ts = datetime.fromisoformat(row["timestamp"])
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"Invalid timestamp in audit record "
                        f"{row['record_id']}: {row['timestamp']!r}"
                    ) from exc

                records.append(
                    AuditLogRecord(
                        record_id=row["record_id"],
                        timestamp=ts,
                        shipment_id=row["shipment_id"],
                        disruptions_detected=row["disruptions_detected"] or "",
                        risk_score=float(row["risk_score"]),
                        risk_tier=row["risk_tier"],
                        recommended_action=row["recommended_action"],
                        alternatives_evaluated_count=int(row["alternatives_evaluated_count"]),
                        human_decision=row["human_decision"],
                        operator_id=row["operator_id"],
                        rationale_notes=row["rationale_notes"] or "",
                        raw_payload_json=row["raw_payload_json"] or "{}",
                    )
                )
            return records
        finally:
            conn.close()
