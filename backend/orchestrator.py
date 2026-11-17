
"""
Agent E: Orchestrator and Human-in-the-Loop Agent.

Coordinates the end-to-end resilience lifecycle:
Data Ingestion -> Sensing (Agent A) -> Prediction (Agent B)
-> Impact (Agent C) -> Recovery Planning (Agent D)
-> Human Approval -> Audit Logging.

Agent execution records contain actual method execution status,
timestamps, duration, output summaries and errors.

All audit decisions are stored locally in the website database.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
import json
import time
import uuid

from .config import (
    ShipmentBaseline,
    SIMULATED_FLEET_INVENTORY,
    SIMULATED_HUB_INVENTORY,
    STATUS_DRAFT,
    STATUS_OPTIMAL,
    STATUS_WARNING,
    STATUS_PENDING_APPROVAL,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_MODIFIED,
    STATUS_ESCALATED
)

from .models import (
    TelemetryReading,
    WeatherCondition,
    DisruptionEvent,
    PredictiveRiskAssessment,
    ShipmentImpact,
    RecoveryAlternative,
    ApprovalDecision,
    AuditLogRecord
)

from .disruption_sensor import DisruptionSensingAgent
from .predictive_risk import PredictiveRiskAgent
from .impact_scoring import ImpactScoringAgent
from .scenario_planner import ScenarioPlanningAgent
from .audit_db import AuditDB


class OrchestratorAgent:
    """
    Agent E: Central control tower orchestrator.

    Coordinates Agents A-D and records their actual execution.
    Human approval remains a separate governance step.
    """

    def __init__(
        self,
        audit_db: Optional[AuditDB] = None
    ):
        self.sensor_agent = DisruptionSensingAgent()
        self.risk_agent = PredictiveRiskAgent()
        self.impact_agent = ImpactScoringAgent()
        self.planner_agent = ScenarioPlanningAgent()

        self.audit_db = audit_db or AuditDB()

        # Orchestration state
        self.workflow_stage: str = STATUS_DRAFT
        self.latest_events: List[DisruptionEvent] = []
        self.latest_risk: Optional[PredictiveRiskAssessment] = None
        self.latest_impact: Optional[ShipmentImpact] = None
        self.latest_alternatives: List[RecoveryAlternative] = []
        self.latest_decision: Optional[ApprovalDecision] = None

        # Agent execution monitoring
        self.execution_history: List[Dict[str, Any]] = []
        self.latest_execution_id: Optional[str] = None
        self.latest_execution_status: str = "NOT_STARTED"
        self.latest_execution_started_at: Optional[str] = None
        self.latest_execution_completed_at: Optional[str] = None
        self.latest_execution_duration_seconds: float = 0.0
        self.latest_execution_error: Optional[str] = None

    @staticmethod
    def _now_iso() -> str:
        """Return a local timestamp in ISO format."""
        return datetime.now().astimezone().isoformat(timespec="seconds")

    @staticmethod
    def _summarize_output(agent_id: str, output: Any) -> Dict[str, Any]:
        """Create a compact summary from the real agent output."""

        if agent_id == "A":
            events = output or []
            return {
                "events_detected": len(events),
                "events": [
                    {
                        "severity": getattr(event, "severity", "UNKNOWN"),
                        "headline": getattr(event, "headline", "Event")
                    }
                    for event in events[:8]
                ]
            }

        if agent_id == "B":
            return {
                "risk_score": getattr(output, "overall_risk_score", None),
                "risk_tier": getattr(output, "risk_tier", None),
                "risk_direction": getattr(output, "risk_direction", None),
                "time_to_breach_minutes": getattr(
                    output, "time_to_breach_envelope_mins", None
                ),
                "contributing_factors": len(
                    getattr(output, "contributing_factors", []) or []
                )
            }

        if agent_id == "C":
            return {
                "financial_exposure_usd": getattr(
                    output, "total_financial_exposure_usd", None
                ),
                "quantity_affected_kg": getattr(
                    output, "quantity_affected_kg", None
                ),
                "expected_delay_minutes": getattr(
                    output, "expected_delay_minutes", None
                )
            }

        if agent_id == "D":
            alternatives = output or []
            return {
                "alternatives_generated": len(alternatives),
                "feasible_alternatives": sum(
                    1 for item in alternatives
                    if getattr(item, "is_feasible", False)
                ),
                "recommended_alternative": next(
                    (
                        getattr(item, "name", None)
                        for item in alternatives
                        if getattr(item, "is_recommended", False)
                    ),
                    None
                )
            }

        return {"output_type": type(output).__name__}

    def _run_agent(
        self,
        agent_id: str,
        agent_name: str,
        method,
        **kwargs
    ):
        """
        Execute one real agent method and record its execution.

        The event is updated from RUNNING to COMPLETED or FAILED.
        """

        started_at = datetime.now().astimezone()
        start_clock = time.perf_counter()

        event = {
            "agent_id": agent_id,
            "agent_name": agent_name,
            "status": "RUNNING",
            "started_at": started_at.isoformat(timespec="seconds"),
            "completed_at": None,
            "duration_seconds": None,
            "output_summary": {},
            "error": None
        }

        self.execution_history.append(event)

        try:
            output = method(**kwargs)

            event["output_summary"] = self._summarize_output(
                agent_id,
                output
            )

            event["status"] = "COMPLETED"
            event["completed_at"] = self._now_iso()
            event["duration_seconds"] = round(
                time.perf_counter() - start_clock, 4
            )

            return output

        except Exception as exc:
            event["status"] = "FAILED"
            event["completed_at"] = self._now_iso()
            event["duration_seconds"] = round(
                time.perf_counter() - start_clock, 4
            )
            event["error"] = f"{type(exc).__name__}: {str(exc)}"

            raise

    def execute_resilience_pipeline(
        self,
        telemetry_history: List[TelemetryReading],
        current_weather: Optional[WeatherCondition],
        vehicle_status: Dict[str, Any],
        cold_hub_status: Dict[str, Any],
        buyer_order_status: Dict[str, Any],
        manual_scenario_flags: Optional[Dict[str, bool]] = None,
        missing_data_flags: Optional[Dict[str, bool]] = None
    ) -> Dict[str, Any]:
        """
        Execute Agents A-D and determine the workflow stage.

        Human approval is required before operational action.
        """

        # Start a fresh execution record for this pipeline run.
        self.latest_execution_id = (
            "RUN-" + uuid.uuid4().hex[:12].upper()
        )

        self.execution_history = []
        self.latest_execution_status = "RUNNING"
        self.latest_execution_started_at = self._now_iso()
        self.latest_execution_completed_at = None
        self.latest_execution_duration_seconds = 0.0
        self.latest_execution_error = None

        pipeline_clock = time.perf_counter()

        try:
            curr_telemetry = (
                telemetry_history[-1]
                if telemetry_history
                else None
            )

            # Agent A: Disruption Sensing
            self.latest_events = self._run_agent(
                "A",
                "Disruption Sensing",
                self.sensor_agent.evaluate_environment,
                current_telemetry=curr_telemetry,
                weather=current_weather,
                vehicle_status=vehicle_status,
                cold_hub_status=cold_hub_status,
                buyer_order_status=buyer_order_status,
                manual_scenario_flags=manual_scenario_flags
            )

            # Agent B: Predictive Risk Assessment
            self.latest_risk = self._run_agent(
                "B",
                "Predictive Risk Assessment",
                self.risk_agent.evaluate_predictive_risk,
                telemetry_history=telemetry_history,
                current_weather=current_weather,
                detected_events=self.latest_events,
                missing_data_flags=missing_data_flags
            )

            # Agent C: Business Impact Scoring
            shipment_qty = buyer_order_status.get(
                "requested_qty_kg",
                ShipmentBaseline.INITIAL_QTY_KG
            )

            self.latest_impact = self._run_agent(
                "C",
                "Business Impact Scoring",
                self.impact_agent.evaluate_business_impact,
                risk_assessment=self.latest_risk,
                current_shipment_qty_kg=shipment_qty,
                buyer_contracted_qty_kg=shipment_qty,
            )

            self.latest_alternatives = self._run_agent(
    "D",
    "Recovery Planning",
    self.planner_agent.generate_and_rank_scenarios,
    risk_assessment=self.latest_risk,
    current_impact=self.latest_impact,
    detected_events=self.latest_events,
    shipment_qty_kg=shipment_qty,
    fleet_inventory=[
        dict(item) for item in SIMULATED_FLEET_INVENTORY
    ],
    hub_inventory=[
        dict(item) for item in SIMULATED_HUB_INVENTORY
    ]
)

            # Agent E: Orchestration and workflow coordination.
            recommended_alt = next(
                (
                    alternative
                    for alternative in self.latest_alternatives
                    if alternative.is_recommended
                ),
                None
            )

            if (
                self.latest_risk.risk_tier == "CRITICAL"
                and not recommended_alt
            ):
                self.workflow_stage = STATUS_ESCALATED

            elif self.latest_risk.risk_tier in ["ELEVATED", "CRITICAL"]:
                self.workflow_stage = STATUS_PENDING_APPROVAL

            elif self.latest_risk.risk_tier == "MODERATE":
                self.workflow_stage = STATUS_WARNING

            else:
                self.workflow_stage = STATUS_OPTIMAL

            self.latest_execution_status = "COMPLETED"

            return {
                "workflow_stage": self.workflow_stage,
                "detected_events": self.latest_events,
                "risk_assessment": self.latest_risk,
                "business_impact": self.latest_impact,
                "recovery_alternatives": self.latest_alternatives,
                "recommended_alternative": recommended_alt,

                # Actual execution monitoring data
                "execution_id": self.latest_execution_id,
                "execution_status": self.latest_execution_status,
                "execution_history": self.execution_history,
                "execution_started_at": self.latest_execution_started_at,
                "execution_completed_at": self._now_iso(),
                "execution_duration_seconds": round(
                    time.perf_counter() - pipeline_clock, 4
                )
            }

        except Exception as exc:
            self.latest_execution_status = "FAILED"
            self.latest_execution_error = (
                f"{type(exc).__name__}: {str(exc)}"
            )
            raise

        finally:
            self.latest_execution_completed_at = self._now_iso()
            self.latest_execution_duration_seconds = round(
                time.perf_counter() - pipeline_clock, 4
            )

    def process_human_decision(
        self,
        shipment_id: str,
        decision_type: str,
        operator_name: str,
        operator_role: str,
        rationale_notes: str,
        selected_alt_id: Optional[str] = None,
        modified_params: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, str, AuditLogRecord]:
        """
        Record the human governance decision and persist it
        in the existing local audit database.
        """

        allowed_decisions = ["APPROVED", "REJECTED", "MODIFIED"]

        if decision_type not in allowed_decisions:
            raise ValueError(
                f"Invalid decision type: {decision_type}. "
                f"Allowed values: {allowed_decisions}"
            )

        now = datetime.now()

        alt_id = selected_alt_id or (
            self.latest_alternatives[0].alt_id
            if self.latest_alternatives
            else "NONE"
        )

        chosen_alt = next(
            (
                alternative
                for alternative in self.latest_alternatives
                if alternative.alt_id == alt_id
            ),
            None
        )

        if self.latest_alternatives and chosen_alt is None:
            raise ValueError(
                f"Invalid recovery alternative ID: {alt_id}"
            )

        if (
            decision_type in ["APPROVED", "MODIFIED"]
            and chosen_alt is not None
            and not chosen_alt.is_feasible
        ):
            raise ValueError(
                "An infeasible recovery alternative cannot be approved."
            )

        decision = ApprovalDecision(
            decision_id=f"DEC-{uuid.uuid4().hex[:12].upper()}",
            timestamp=now,
            shipment_id=shipment_id,
            selected_alt_id=alt_id,
            decision_status=decision_type,
            operator_name=operator_name or "Logistics Operations Lead",
            operator_role=operator_role or "Cold-Chain Fleet Controller",
            rationale_notes=(
                rationale_notes
                or "Standard governance review completed."
            ),
            modified_parameters=modified_params or {}
        )

        self.latest_decision = decision

        if decision_type == "APPROVED":
            self.workflow_stage = STATUS_APPROVED
        elif decision_type == "REJECTED":
            self.workflow_stage = STATUS_REJECTED
        elif decision_type == "MODIFIED":
            self.workflow_stage = STATUS_MODIFIED
        else:
            self.workflow_stage = STATUS_ESCALATED

        payload_dict: Dict[str, Any] = {
            "decision_type": decision_type,
            "shipment_id": shipment_id,
            "selected_alt_id": alt_id,
            "operator_name": operator_name,
            "operator_role": operator_role,
            "rationale_notes": rationale_notes,
            "modified_parameters": modified_params or {}
        }

        disruptions_summary = (
            "; ".join(
                event.headline
                for event in self.latest_events
            )
            if self.latest_events
            else "Nominal Conditions"
        )

        risk_score_val = (
            self.latest_risk.overall_risk_score
            if self.latest_risk
            else 0.0
        )

        risk_tier_val = (
            self.latest_risk.risk_tier
            if self.latest_risk
            else "LOW"
        )

        action_name = (
            chosen_alt.name
            if chosen_alt
            else "No Action Assigned"
        )

        audit_entry = AuditLogRecord(
            record_id=decision.decision_id,
            timestamp=now,
            shipment_id=shipment_id,
            disruptions_detected=disruptions_summary,
            risk_score=risk_score_val,
            risk_tier=risk_tier_val,
            recommended_action=action_name,
            alternatives_evaluated_count=len(
                self.latest_alternatives
            ),
            human_decision=decision_type,
            operator_id=(
                f"{decision.operator_name} "
                f"({decision.operator_role})"
            ),
            rationale_notes=decision.rationale_notes,
            raw_payload_json=json.dumps(
                payload_dict,
                indent=2
            )
        )

        self.audit_db.insert_audit_record(audit_entry)

        message = (
            f"Decision '{decision_type}' recorded successfully "
            "in the local audit trail."
        )

        return True, message, audit_entry
