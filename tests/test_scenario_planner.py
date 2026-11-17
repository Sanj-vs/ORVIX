
from datetime import datetime

from backend.config import (
    SIMULATED_FLEET_INVENTORY,
    SIMULATED_HUB_INVENTORY,
)
from backend.models import (
    PredictiveRiskAssessment,
    ShipmentImpact,
)
from backend.scenario_planner import ScenarioPlanningAgent
def make_inventory():
    """Return copies of the simulated ORVIX backup inventory."""
    return {
        "fleet_inventory": [
            dict(item) for item in SIMULATED_FLEET_INVENTORY
        ],
        "hub_inventory": [
            dict(item) for item in SIMULATED_HUB_INVENTORY
        ],
    }


def make_inputs(events=None):
    """Create valid input objects for Agent D tests."""
    now = datetime.now()

    risk = PredictiveRiskAssessment(
        timestamp=now,
        overall_risk_score=80.0,
        risk_tier="CRITICAL",
        direction_of_change="WORSENING",
    )

    impact = ShipmentImpact(
        timestamp=now,
        quantity_affected_kg=100.0,
        expected_delay_minutes=60,
        deadline_breached=True,
        perishability_urgency="URGENT",
        estimated_spoilage_cost_usd=500.0,
        estimated_sla_penalty_usd=350.0,
        estimated_additional_logistics_usd=450.0,
        total_financial_exposure_usd=1300.0,
        unmet_demand_kg=100.0,
        data_confidence_pct=90.0,
    )

    return risk, impact, events or []


def test_dual_van_rejects_shipment_above_combined_capacity():
    risk, impact, events = make_inputs()

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
    risk,
    impact,
    events,
    shipment_qty_kg=1300.0,
    **make_inventory()
)

    dual_van = next(a for a in alternatives if a.alt_id == "REC-ALT-03")

    assert dual_van.is_feasible is False
    assert dual_van.is_recommended is False
    assert dual_van.rejection_reasons


def test_light_van_is_rejected_when_cold_chain_suitability_is_unverified():
    risk, impact, events = make_inputs()

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
    risk,
    impact,
    events,
    shipment_qty_kg=300.0,
    **make_inventory()
)

    light_van = next(
        a for a in alternatives
        if a.assigned_vehicle_id == "VAN-C3-LIGHT"
    )

    assert light_van.is_feasible is False
    assert light_van.is_recommended is False
    assert light_van.quantity_delivered_kg == 0.0
    assert any(
        "Cold-chain suitability is not verified" in reason
        for reason in light_van.rejection_reasons
    )


def test_recommendation_does_not_claim_sla_compliance_when_delay_exceeds_limit(monkeypatch):
    monkeypatch.setattr(
        "backend.scenario_planner.ShipmentBaseline.MAX_ALLOWED_DELAY_MINUTES",
        30
    )

    risk, impact, events = make_inputs()

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
    risk,
    impact,
    events,
    shipment_qty_kg=800.0,
    **make_inventory()
)

    recommended = next(a for a in alternatives if a.is_recommended)

    assert recommended.deadline_feasible is False
    assert recommended.estimated_delay_minutes > 30
    assert "exceeds contractual SLA" in recommended.recommendation_rationale
    assert "within contractual SLA" not in recommended.recommendation_rationale
def test_missing_backup_vehicle_is_rejected():
    risk, impact, events = make_inputs()
    inventory = make_inventory()
    inventory["fleet_inventory"] = [
        item for item in inventory["fleet_inventory"]
        if item["vehicle_id"] != "REEFER-V2-EXP"
    ]

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
        risk, impact, events, shipment_qty_kg=800.0, **inventory
    )

    alt1 = next(a for a in alternatives if a.alt_id == "REC-ALT-01")
    assert alt1.is_feasible is False
    assert any("missing or duplicated" in reason for reason in alt1.rejection_reasons)


def test_unavailable_backup_vehicle_is_rejected():
    risk, impact, events = make_inputs()
    inventory = make_inventory()

    for item in inventory["fleet_inventory"]:
        if item["vehicle_id"] == "REEFER-V4-METRO":
            item["is_available"] = False

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
        risk, impact, events, shipment_qty_kg=800.0, **inventory
    )

    alt2 = next(a for a in alternatives if a.alt_id == "REC-ALT-02")
    assert alt2.is_feasible is False
    assert any("unavailable" in reason for reason in alt2.rejection_reasons)


def test_non_refrigerated_backup_vehicle_is_rejected():
    risk, impact, events = make_inputs()
    inventory = make_inventory()

    for item in inventory["fleet_inventory"]:
        if item["vehicle_id"] == "REEFER-V4-METRO":
            item["is_refrigerated"] = False

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
        risk, impact, events, shipment_qty_kg=800.0, **inventory
    )

    alt2 = next(a for a in alternatives if a.alt_id == "REC-ALT-02")
    assert alt2.is_feasible is False
    assert any(
        "not verified as refrigerated" in reason
        for reason in alt2.rejection_reasons
    )


def test_insufficient_backup_hub_capacity_is_rejected():
    risk, impact, events = make_inputs()
    inventory = make_inventory()

    for item in inventory["hub_inventory"]:
        if item["hub_id"] == "HUB-BETA-INLAND":
            item["storage_capacity_kg"] = 500.0

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
        risk, impact, events, shipment_qty_kg=800.0, **inventory
    )

    alt2 = next(a for a in alternatives if a.alt_id == "REC-ALT-02")
    assert alt2.is_feasible is False
    assert any("capacity is insufficient" in reason for reason in alt2.rejection_reasons)


def test_unavailable_backup_hub_is_rejected():
    risk, impact, events = make_inputs()
    inventory = make_inventory()

    for item in inventory["hub_inventory"]:
        if item["hub_id"] == "HUB-BETA-INLAND":
            item["is_available"] = False

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
        risk, impact, events, shipment_qty_kg=800.0, **inventory
    )

    alt2 = next(a for a in alternatives if a.alt_id == "REC-ALT-02")
    assert alt2.is_feasible is False
    assert any("unavailable" in reason for reason in alt2.rejection_reasons)


def test_duplicate_backup_hub_records_are_rejected():
    risk, impact, events = make_inputs()
    inventory = make_inventory()
    duplicate = dict(inventory["hub_inventory"][0])
    inventory["hub_inventory"].append(duplicate)

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
        risk, impact, events, shipment_qty_kg=800.0, **inventory
    )

    alt2 = next(a for a in alternatives if a.alt_id == "REC-ALT-02")
    assert alt2.is_feasible is False
    assert any("missing or duplicated" in reason for reason in alt2.rejection_reasons)


def test_dual_van_rejects_when_one_vehicle_is_missing():
    risk, impact, events = make_inputs()
    inventory = make_inventory()

    inventory["fleet_inventory"] = [
        item for item in inventory["fleet_inventory"]
        if item["vehicle_id"] != "REEFER-V6"
    ]

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
        risk, impact, events, shipment_qty_kg=800.0, **inventory
    )

    alt3 = next(a for a in alternatives if a.alt_id == "REC-ALT-03")
    assert alt3.is_feasible is False
    assert alt3.is_recommended is False
    assert alt3.rejection_reasons


def test_dual_van_rejects_when_one_vehicle_is_unavailable():
    risk, impact, events = make_inputs()
    inventory = make_inventory()

    for item in inventory["fleet_inventory"]:
        if item["vehicle_id"] == "REEFER-V5":
            item["is_available"] = False

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
        risk, impact, events, shipment_qty_kg=800.0, **inventory
    )

    alt3 = next(a for a in alternatives if a.alt_id == "REC-ALT-03")
    assert alt3.is_feasible is False
    assert alt3.is_recommended is False
    assert alt3.rejection_reasons

    alternatives = ScenarioPlanningAgent().generate_and_rank_scenarios(
        risk, impact, events, shipment_qty_kg=800.0, **inventory
    )

    alt3 = next(a for a in alternatives if a.alt_id == "REC-ALT-03")
    assert alt3.is_feasible is False
    assert alt3.is_recommended is False
    assert alt3.rejection_reasons