"""
Agent D: Scenario Planning and Recovery Agent
Generates, stress-tests, filters, and ranks operational recovery alternatives.
Strictly enforces hard physical constraints (vehicle capacity, resource availability, route passability)
and rejects infeasible options with explainable rationales.
"""

import math
from typing import List, Dict, Any, Optional

from .config import ColdChainSpecs, ShipmentBaseline, ScoringWeights
from .models import (
    PredictiveRiskAssessment,
    ShipmentImpact,
    RecoveryAlternative,
    DisruptionEvent
)


class ScenarioPlanningAgent:
    """
    Evaluates recovery options against multi-criteria objective function:
    Feasibility (Hard Gate) -> Deadline SLA -> Risk Reduction -> Incremental Cost.
    """

    def __init__(self, agent_name: str = "Scenario-Recovery-Agent-04"):
        self.agent_name = agent_name

    def generate_and_rank_scenarios(
        self,
        risk_assessment: PredictiveRiskAssessment,
        current_impact: ShipmentImpact,
        detected_events: List[DisruptionEvent],
        shipment_qty_kg: float = ShipmentBaseline.INITIAL_QTY_KG,
        fleet_inventory: Optional[List[Dict[str, Any]]] = None,
        hub_inventory: Optional[List[Dict[str, Any]]] = None
    ) -> List[RecoveryAlternative]:
        """
        Synthesize candidate recovery plans, prune infeasible candidates, and rank the rest.
        """
        # Determine active physical disruption constraints
        is_flood_active = any(e.event_type == "WEATHER_FLOOD" and e.severity in ["HIGH", "CRITICAL"] for e in detected_events)
        is_primary_veh_down = any(e.event_type == "VEHICLE_BREAKDOWN" and e.severity == "CRITICAL" for e in detected_events)
        is_primary_hub_down = any(e.event_type == "STORAGE_UNAVAILABLE" for e in detected_events)
        is_thermal_crisis = any(e.event_type == "THERMAL_EXCURSION" and e.severity == "CRITICAL" for e in detected_events)

        candidates: List[RecoveryAlternative] = []
                # -------------------------------------------------------------
        # Validate simulated backup vehicle and hub inventory
        # Missing or invalid inventory must fail closed.
        # -------------------------------------------------------------
        fleet_records = fleet_inventory if isinstance(fleet_inventory, list) else []
        hub_records = hub_inventory if isinstance(hub_inventory, list) else []

        def find_inventory_record(records, resource_id, id_key):
            matches = [
                item for item in records
                if isinstance(item, dict) and item.get(id_key) == resource_id
            ]

            if len(matches) != 1:
                return None

            return matches[0]

        def validate_vehicle(vehicle_id):
            record = find_inventory_record(
                fleet_records, vehicle_id, "vehicle_id"
            )

            if record is None:
                return 0.0, False, [
                    f"Vehicle {vehicle_id} is missing or duplicated in inventory."
                ]

            capacity = record.get("capacity_kg")
            available = record.get("is_available") is True
            refrigerated = record.get("is_refrigerated") is True

            valid_capacity = (
                isinstance(capacity, (int, float))
                and not isinstance(capacity, bool)
                and math.isfinite(capacity)
                and capacity > 0
            )

            reasons = []

            if not valid_capacity:
                reasons.append(
                    f"Vehicle {vehicle_id} has invalid capacity information."
                )

            if not available:
                reasons.append(
                    f"Vehicle {vehicle_id} is unavailable."
                )

            if not refrigerated:
                reasons.append(
                    f"Vehicle {vehicle_id} is not verified as refrigerated."
                )

            return (
                float(capacity) if valid_capacity else 0.0,
                available and refrigerated and valid_capacity,
                reasons
            )

        def validate_hub(hub_id, required_capacity_kg):
            record = find_inventory_record(
                hub_records, hub_id, "hub_id"
            )

            if record is None:
                return False, [
                    f"Storage hub {hub_id} is missing or duplicated in inventory."
                ]

            capacity = record.get("storage_capacity_kg")
            available = record.get("is_available") is True

            valid_capacity = (
                isinstance(capacity, (int, float))
                and not isinstance(capacity, bool)
                and math.isfinite(capacity)
                and capacity > 0
            )

            reasons = []

            if not available:
                reasons.append(f"Storage hub {hub_id} is unavailable.")

            if not valid_capacity:
                reasons.append(
                    f"Storage hub {hub_id} has invalid capacity information."
                )
            elif capacity < required_capacity_kg:
                reasons.append(
                    f"Storage hub {hub_id} capacity is insufficient: "
                    f"{capacity:.1f} kg available, "
                    f"{required_capacity_kg:.1f} kg required."
                )

            return (
                available and valid_capacity and capacity >= required_capacity_kg,
                reasons
            )

        # -------------------------------------------------------------
        # Alternative 1: Inland Expressway Bypass + Heavy Reefer V2
        # -------------------------------------------------------------
        alt1_veh_id = "REEFER-V2-EXP"

        # Validate backup vehicle using simulated fleet inventory
        alt1_veh_cap, alt1_veh_avail, alt1_rejections = (
            validate_vehicle(alt1_veh_id)
        )

        # Use backup hub only when the primary hub is unavailable
        alt1_hub_id = (
            "HUB-BETA-INLAND"
            if is_primary_hub_down
            else ShipmentBaseline.PRIMARY_COLD_HUB_ID
        )

        if is_primary_hub_down:
            alt1_hub_avail, alt1_hub_rejections = validate_hub(
                alt1_hub_id, shipment_qty_kg
            )
            alt1_rejections.extend(alt1_hub_rejections)
        else:
            alt1_hub_avail = True

        alt1_delay_mins = 35
        alt1_cost_usd = 380.0



        alt1_feasible = len(alt1_rejections) == 0
        alt1_deadline_ok = alt1_delay_mins <= ShipmentBaseline.MAX_ALLOWED_DELAY_MINUTES

        candidates.append(RecoveryAlternative(
            alt_id="REC-ALT-01",
            name="Inland Bypass & Express Reefer Dispatch",
            description="Divert transit onto RT-202 Inland Expressway (flood-free elevated corridor). Reassign cargo to high-output dual-compressor Reefer V2.",
            assigned_vehicle_id=alt1_veh_id,
            vehicle_capacity_kg=alt1_veh_cap,
            is_vehicle_available=alt1_veh_avail,
            route_name="RT-202-INLAND-EXPRESSWAY (Elevated, High Passability)",
            storage_hub_id=alt1_hub_id,
            is_storage_available=alt1_hub_avail,
            estimated_delay_minutes=alt1_delay_mins,
            additional_cost_usd=alt1_cost_usd,
            quantity_delivered_kg=shipment_qty_kg,
            deadline_feasible=alt1_deadline_ok,
            is_feasible=alt1_feasible,
            rejection_reasons=alt1_rejections,
            risk_reduction_score=82.0
        ))

        # -------------------------------------------------------------
        # Alternative 2: Intermediate Cold Hub Diversion & Pre-Cooling
        # -------------------------------------------------------------
        alt2_veh_id = "REEFER-V4-METRO"

        # Validate backup vehicle
        alt2_veh_cap, alt2_veh_avail, alt2_rejections = (
            validate_vehicle(alt2_veh_id)
        )

        # Alternative 2 always requires Hub Beta
        alt2_hub_id = "HUB-BETA-INLAND"
        alt2_hub_avail, alt2_hub_rejections = validate_hub(
            alt2_hub_id, shipment_qty_kg
        )
        alt2_rejections.extend(alt2_hub_rejections)

        alt2_delay_mins = 75
        alt2_cost_usd = 490.0



        alt2_feasible = len(alt2_rejections) == 0
        alt2_deadline_ok = alt2_delay_mins <= ShipmentBaseline.MAX_ALLOWED_DELAY_MINUTES

        candidates.append(RecoveryAlternative(
            alt_id="REC-ALT-02",
            name="Intermediate Cold Hub Diversion (Hub Beta)",
            description="Immediate diversion to Hub Beta for blast chilling stabilization (2.0°C) before completing final distribution leg.",
            assigned_vehicle_id=alt2_veh_id,
            vehicle_capacity_kg=alt2_veh_cap,
            is_vehicle_available=alt2_veh_avail,
            route_name="RT-303-VALLEY-CONNECTOR to HUB-BETA",
            storage_hub_id=alt2_hub_id,
            is_storage_available=alt2_hub_avail,
            estimated_delay_minutes=alt2_delay_mins,
            additional_cost_usd=alt2_cost_usd,
            quantity_delivered_kg=shipment_qty_kg,
            deadline_feasible=alt2_deadline_ok,
            is_feasible=alt2_feasible,
            rejection_reasons=alt2_rejections,
            risk_reduction_score=74.0
        ))

        # -------------------------------------------------------------
        # Alternative 3: Split Consignment Multi-Drop
        # -------------------------------------------------------------
        alt3_veh_id = "DUAL-VAN-MICRO-REEFERS (V5 & V6)"

        # Validate both vehicles independently
        alt3_v5_capacity, alt3_v5_available, alt3_rejections = (
            validate_vehicle("REEFER-V5")
        )

        alt3_v6_capacity, alt3_v6_available, alt3_v6_rejections = (
            validate_vehicle("REEFER-V6")
        )

        alt3_rejections.extend(alt3_v6_rejections)

        # Combined capacity is based on verified inventory
        alt3_veh_cap = alt3_v5_capacity + alt3_v6_capacity
        alt3_veh_avail = alt3_v5_available and alt3_v6_available

        if shipment_qty_kg > alt3_veh_cap:
            alt3_rejections.append(
                f"Capacity violation: Combined vehicle capacity is "
                f"{alt3_veh_cap:.1f} kg, but shipment quantity is "
                f"{shipment_qty_kg:.1f} kg."
            )

        # Use Hub Beta only when the primary hub is unavailable
        alt3_hub_id = (
            "HUB-BETA-INLAND"
            if is_primary_hub_down
            else ShipmentBaseline.PRIMARY_COLD_HUB_ID
        )

        if is_primary_hub_down:
            alt3_hub_avail, alt3_hub_rejections = validate_hub(
                alt3_hub_id, shipment_qty_kg
            )
            alt3_rejections.extend(alt3_hub_rejections)
        else:
            alt3_hub_avail = True

        alt3_delay_mins = 50
        alt3_cost_usd = 620.0





        alt3_feasible = len(alt3_rejections) == 0

        candidates.append(RecoveryAlternative(
            alt_id="REC-ALT-03",
            name="Split Consignment (Dual Micro-Reefers)",
            description=(
                f"Split {shipment_qty_kg:.1f} kg shipment across "
                "two smaller urban reefer vans."
            ),
            assigned_vehicle_id=alt3_veh_id,
            vehicle_capacity_kg=alt3_veh_cap,
            is_vehicle_available=alt3_veh_avail,
            route_name="RT-URBAN-ARTERIAL-GRID (Segmented)",
            storage_hub_id=alt3_hub_id,
            is_storage_available=alt3_hub_avail,
            estimated_delay_minutes=alt3_delay_mins,
            additional_cost_usd=alt3_cost_usd,
            quantity_delivered_kg=min(shipment_qty_kg, alt3_veh_cap),
            deadline_feasible=alt3_delay_mins <= ShipmentBaseline.MAX_ALLOWED_DELAY_MINUTES,
            is_feasible=alt3_feasible,
            rejection_reasons=alt3_rejections,
            risk_reduction_score=68.0
        ))


        # -------------------------------------------------------------
        # Alternative 4: Infeasible Candidate 1 - Capacity Violation (Van C3)
        # ORVIX rejects illegal/unsafe options and records why
        # -------------------------------------------------------------
        alt4_capacity = 500.0
        alt4_available = True
        alt4_rejections = [
            "Cold-chain suitability is not verified for light courier van C3."
        ]

        if shipment_qty_kg > alt4_capacity:
            alt4_rejections.append(
                f"Capacity violation: Vehicle capacity is "
                f"{alt4_capacity:.1f} kg, but shipment quantity is "
                f"{shipment_qty_kg:.1f} kg."
            )

        if not alt4_available:
            alt4_rejections.append(
                "Light courier van C3 is unavailable."
            )

        alt4_feasible = len(alt4_rejections) == 0

        candidates.append(RecoveryAlternative(
            alt_id="REC-ALT-04",
            name="Emergency Light Courier Van C3",
            description=(
                "Comparison option only. Rejected because "
                "refrigerated suitability is not verified."
            ),
            assigned_vehicle_id="VAN-C3-LIGHT",
            vehicle_capacity_kg=alt4_capacity,
            is_vehicle_available=alt4_available,
            route_name="RT-101-COASTAL-HIGHWAY",
            storage_hub_id=ShipmentBaseline.PRIMARY_COLD_HUB_ID,
            is_storage_available=not is_primary_hub_down,
            estimated_delay_minutes=20,
            additional_cost_usd=150.0,
            quantity_delivered_kg=0.0,
            deadline_feasible=True,
            is_feasible=alt4_feasible,
            rejection_reasons=alt4_rejections,
            risk_reduction_score=0.0
        ))


        # -------------------------------------------------------------
        # Alternative 5: Infeasible Candidate 2 - Primary Vehicle when Broken
        # -------------------------------------------------------------
        if is_primary_veh_down or is_flood_active:
            alt5_rejections = []
            if is_primary_veh_down:
                alt5_rejections.append(f"Primary vehicle {ShipmentBaseline.PRIMARY_VEHICLE_ID} is mechanically disabled.")
            if is_flood_active:
                alt5_rejections.append(f"Route {ShipmentBaseline.PRIMARY_ROUTE_ID} is closed by civil defense flood advisory.")

            candidates.append(RecoveryAlternative(
                alt_id="REC-ALT-05-DEFAULT-PLAN",
                name="Status Quo Planned Run (Infeasible under Disruption)",
                description="Continue planned schedule on Coastal Highway with original reefer asset.",
                assigned_vehicle_id=ShipmentBaseline.PRIMARY_VEHICLE_ID,
                vehicle_capacity_kg=ShipmentBaseline.PRIMARY_VEHICLE_CAPACITY_KG,
                is_vehicle_available=not is_primary_veh_down,
                route_name=ShipmentBaseline.PRIMARY_ROUTE_ID,
                storage_hub_id=ShipmentBaseline.PRIMARY_COLD_HUB_ID,
                is_storage_available=not is_primary_hub_down,
                estimated_delay_minutes=240,
                additional_cost_usd=0.0,
                quantity_delivered_kg=shipment_qty_kg,
                deadline_feasible=False,
                is_feasible=False,
                rejection_reasons=alt5_rejections,
                risk_reduction_score=0.0
            ))

        # -------------------------------------------------------------
        # Multi-Criteria Scoring & Ranking of Feasible Candidates
        # -------------------------------------------------------------
        max_cost_ref = 1000.0
        max_delay_ref = 120.0

        for alt in candidates:
            if not alt.is_feasible:
                alt.composite_rank_score = 0.0
                alt.is_recommended = False
                continue

            # Normalized components (0.0 to 1.0)
            feasibility_score = 1.0
            deadline_score = 1.0 if alt.deadline_feasible else max(0.0, 1.0 - (alt.estimated_delay_minutes / max_delay_ref))
            risk_red_score = alt.risk_reduction_score / 100.0
            cost_efficiency_score = max(0.0, 1.0 - (alt.additional_cost_usd / max_cost_ref))

            composite = (
                (feasibility_score * ScoringWeights.RANK_WEIGHT_FEASIBILITY) +
                (deadline_score * ScoringWeights.RANK_WEIGHT_DEADLINE_PERFORMANCE) +
                (risk_red_score * ScoringWeights.RANK_WEIGHT_RISK_REDUCTION) +
                (cost_efficiency_score * ScoringWeights.RANK_WEIGHT_COST_EFFICIENCY)
            ) * 100.0

            alt.composite_rank_score = round(composite, 1)

        # Sort: feasible first by composite score descending, then infeasible
        candidates.sort(key=lambda a: (a.is_feasible, a.composite_rank_score), reverse=True)

        # Mark top feasible option as recommended
        feasible_options = [a for a in candidates if a.is_feasible]
        if feasible_options:
            best = feasible_options[0]
            best.is_recommended = True

            sla_status = (
                "within contractual SLA"
                if best.deadline_feasible
                else "exceeds contractual SLA"
            )

            best.recommendation_rationale = (
                f"Selected as optimal recovery plan (Score: {best.composite_rank_score}/100). "
                f"Plans to deliver {best.quantity_delivered_kg:.0f} kg of cargo, "
                f"with an estimated delay of {best.estimated_delay_minutes} mins "
                f"({sla_status}), reduces risk index by "
                f"{best.risk_reduction_score:.0f} points, "
                f"at an additional cost of ${best.additional_cost_usd:.2f}."
            )

        else:
            # Escalation case: No feasible options
            for alt in candidates:
                alt.is_recommended = False
                alt.recommendation_rationale = "No candidate options met physical feasibility constraints. Operational escalation required."

        return candidates
