"""
Agent C: Shipment Impact and Scoring Agent
Translates operational risk signals into tangible commercial and SLA consequences:
financial exposure, delay projections, spoilage urgency, and unmet demand.
"""

from datetime import datetime
from typing import Dict, Any

from .config import ColdChainSpecs, ShipmentBaseline, ScoringWeights
from .models import PredictiveRiskAssessment, ShipmentImpact


class ImpactScoringAgent:
    """
    Evaluates business consequences without conflating risk scores with financial loss.
    All monetary calculations are transparent, configurable scenario projections.
    """

    def __init__(self, agent_name: str = "Shipment-Impact-Agent-03"):
        self.agent_name = agent_name

    def evaluate_business_impact(
        self,
        risk_assessment: PredictiveRiskAssessment,
        current_shipment_qty_kg: float = ShipmentBaseline.INITIAL_QTY_KG,
        buyer_contracted_qty_kg: float = ShipmentBaseline.INITIAL_QTY_KG,
        projected_delay_minutes: int = 0
    ) -> ShipmentImpact:
        """
        Compute commercial and operational impact.
        """
        now = datetime.now()
        risk_score = risk_assessment.overall_risk_score
        total_cargo_value_usd = current_shipment_qty_kg * ShipmentBaseline.COMMODITY_VALUE_PER_KG_USD

        # -------------------------------------------------------------
        # 1. Perishability Urgency & Spoilage Estimation
        # -------------------------------------------------------------
        # Determine quantity at risk of biological decay
        if risk_assessment.risk_tier == "CRITICAL":
            perishability_urgency = "IMMINENT_SPOILAGE"
            # In critical scenario without recovery, 60-100% of cargo is at risk of total write-off
            spoilage_fraction = min(1.0, 0.40 + (risk_score / 150.0))
            quantity_at_risk_kg = round(current_shipment_qty_kg * spoilage_fraction, 1)
            estimated_spoilage_loss_usd = round(quantity_at_risk_kg * ShipmentBaseline.COMMODITY_VALUE_PER_KG_USD, 2)
        elif risk_assessment.risk_tier == "ELEVATED":
            perishability_urgency = "URGENT"
            spoilage_fraction = 0.20 + (risk_score / 300.0)
            quantity_at_risk_kg = round(current_shipment_qty_kg * spoilage_fraction, 1)
            # Downgrade / salvage markdown loss rather than 100% destruction
            estimated_spoilage_loss_usd = round(quantity_at_risk_kg * (ShipmentBaseline.COMMODITY_VALUE_PER_KG_USD * 0.50), 2)
        elif risk_assessment.risk_tier == "MODERATE":
            perishability_urgency = "MONITORED"
            quantity_at_risk_kg = round(current_shipment_qty_kg * 0.10, 1)
            estimated_spoilage_loss_usd = 0.0  # Still recoverable with preventive cooling
        else:
            perishability_urgency = "NORMAL"
            quantity_at_risk_kg = 0.0
            estimated_spoilage_loss_usd = 0.0

        # -------------------------------------------------------------
        # 2. SLA Delay Penalties
        # -------------------------------------------------------------
        # Base delay + delay incurred by disruption
        effective_delay_mins = projected_delay_minutes
        if risk_assessment.risk_tier == "CRITICAL" and effective_delay_mins == 0:
            effective_delay_mins = 240  # 4-hour severe standstill estimate if unaddressed
        elif risk_assessment.risk_tier == "ELEVATED" and effective_delay_mins == 0:
            effective_delay_mins = 120  # 2-hour delay estimate

        deadline_breached = effective_delay_mins > ShipmentBaseline.MAX_ALLOWED_DELAY_MINUTES

        excess_delay_hours = max(0.0, (effective_delay_mins - ShipmentBaseline.MAX_ALLOWED_DELAY_MINUTES) / 60.0)
        sla_penalty_usd = round(excess_delay_hours * ShipmentBaseline.SLA_PENALTY_PER_HOUR_USD, 2)

        # -------------------------------------------------------------
        # 3. Logistics Emergency Costs & Demand Fulfillment
        # -------------------------------------------------------------
        if risk_assessment.risk_tier in ["CRITICAL", "ELEVATED"]:
            additional_logistics_usd = 450.0  # Standby driver / re-routing toll / emergency handling
        elif risk_assessment.risk_tier == "MODERATE":
            additional_logistics_usd = 120.0  # Priority reefer diagnostics
        else:
            additional_logistics_usd = 0.0

        unmet_demand_kg = max(0.0, buyer_contracted_qty_kg - (current_shipment_qty_kg - quantity_at_risk_kg if perishability_urgency == "IMMINENT_SPOILAGE" else current_shipment_qty_kg))

        total_exposure = estimated_spoilage_loss_usd + sla_penalty_usd + additional_logistics_usd

        scoring_weights = {
            "spoilage_exposure_usd": estimated_spoilage_loss_usd,
            "contractual_sla_penalty_usd": sla_penalty_usd,
            "emergency_logistics_usd": additional_logistics_usd,
            "total_cargo_asset_base_usd": total_cargo_value_usd
        }

        return ShipmentImpact(
            timestamp=now,
            quantity_affected_kg=quantity_at_risk_kg,
            expected_delay_minutes=effective_delay_mins,
            deadline_breached=deadline_breached,
            perishability_urgency=perishability_urgency,
            estimated_spoilage_cost_usd=estimated_spoilage_loss_usd,
            estimated_sla_penalty_usd=sla_penalty_usd,
            estimated_additional_logistics_usd=additional_logistics_usd,
            total_financial_exposure_usd=round(total_exposure, 2),
            unmet_demand_kg=round(unmet_demand_kg, 1),
            data_confidence_pct=risk_assessment.data_confidence_score,
            scoring_breakdown=scoring_weights,
            assumptions_statement=(
                f"Illustrative projection assuming seafood valuation of ${ShipmentBaseline.COMMODITY_VALUE_PER_KG_USD:.2f}/kg, "
                f"SLA delay penalty of ${ShipmentBaseline.SLA_PENALTY_PER_HOUR_USD:.2f}/hr beyond {ShipmentBaseline.MAX_ALLOWED_DELAY_MINUTES} mins, "
                f"and potential cargo write-off if unrecovered."
            )
        )
