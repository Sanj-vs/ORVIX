"""
Agent B: Predictive Risk Agent
Estimates emerging operational risks BEFORE failures manifest.
Analyzes temperature telemetry sequences, rate of warming (dT/dt), corridor weather forecasts,
and transit timeline constraints using an explainable, transparent early-warning heuristic.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any

from .config import ColdChainSpecs, ShipmentBaseline, ScoringWeights
from .models import (
    TelemetryReading,
    WeatherCondition,
    DisruptionEvent,
    PredictiveRiskAssessment,
    RiskSignal
)


class PredictiveRiskAgent:
    """
    Computes an illustrative early-warning risk score (0-100) and identifies
    leading risk signals before operational failures become irreversible.
    """

    def __init__(self, agent_name: str = "Predictive-Risk-Agent-02"):
        self.agent_name = agent_name

    def evaluate_predictive_risk(
        self,
        telemetry_history: List[TelemetryReading],
        current_weather: Optional[WeatherCondition],
        detected_events: List[DisruptionEvent],
        elapsed_transit_minutes: int = 120,
        missing_data_flags: Optional[Dict[str, bool]] = None
    ) -> PredictiveRiskAssessment:
        """
        Execute multi-factor predictive evaluation.
        """
        now = datetime.now()
        factors: List[RiskSignal] = []
        missing_signals: List[str] = []
        flags = missing_data_flags or {}

        # -------------------------------------------------------------
        # 1. Thermal Trajectory & Time-to-Breach Analysis
        # -------------------------------------------------------------
        thermal_score = 0.0
        time_to_breach_mins: Optional[float] = None
        temp_trend_direction = "STABLE"

        if flags.get("missing_telemetry", False) or not telemetry_history:
            missing_signals.append("Missing Reefer Bay Telemetry Data")
            # Missing data is NOT zero risk: apply a conservative data-uncertainty risk penalty
            thermal_score = 45.0
            factors.append(RiskSignal(
                factor_name="Thermal Telemetry Integrity",
                current_value_repr="NO SIGNAL (Stale/Disconnected)",
                threshold_repr=f"Normal: {ColdChainSpecs.TARGET_TEMP_C:.1f}°C",
                direction="CRITICAL",
                weight_pct=ScoringWeights.WEIGHT_THERMAL_DRIFT * 100,
                score_contribution=round(thermal_score * ScoringWeights.WEIGHT_THERMAL_DRIFT, 1),
                explanation="Lack of live sensor data creates acute operational uncertainty. In cold chain compliance, unmonitored transit is high risk."
            ))
        else:
            current_reading = telemetry_history[-1]
            curr_temp = current_reading.temperature_c

            # Compute temperature slope (degrees C per hour) if we have history
            slope_c_per_hr = 0.0
            if len(telemetry_history) >= 2:
                first_reading = telemetry_history[0]
                delta_temp = curr_temp - first_reading.temperature_c
                # Estimate elapsed hours across samples (assuming 15-min intervals if timestamps identical)
                time_diff_hours = (current_reading.timestamp - first_reading.timestamp).total_seconds() / 3600.0
                if time_diff_hours <= 0.05:
                    time_diff_hours = (len(telemetry_history) - 1) * 0.25  # 15 mins per step
                slope_c_per_hr = delta_temp / max(time_diff_hours, 0.1)

            # Determine thermal risk score & time to breach
            if curr_temp >= ColdChainSpecs.CRITICAL_BREACH_TEMP_C:
                thermal_score = 100.0
                temp_trend_direction = "CRITICAL"
                time_to_breach_mins = 0.0
                thermal_expl = f"Critical threshold ({ColdChainSpecs.CRITICAL_BREACH_TEMP_C}°C) breached. Cargo actively degrading at {curr_temp:.1f}°C."
            elif curr_temp >= ColdChainSpecs.MAX_SAFE_TEMP_C:
                thermal_score = 75.0 + min(25.0, (curr_temp - ColdChainSpecs.MAX_SAFE_TEMP_C) * 12.5)
                temp_trend_direction = "CRITICAL"
                time_to_breach_mins = 0.0
                thermal_expl = f"Safe ceiling ({ColdChainSpecs.MAX_SAFE_TEMP_C}°C) exceeded at {curr_temp:.1f}°C. Microbial safety envelope breached."
            elif slope_c_per_hr >= ColdChainSpecs.RAPID_RISE_GRADIENT_C_PER_HR:
                # Early warning! Still below 4°C, but rising fast!
                degrees_remaining = ColdChainSpecs.MAX_SAFE_TEMP_C - curr_temp
                time_to_breach_mins = round((degrees_remaining / max(slope_c_per_hr, 0.01)) * 60.0, 0)
                thermal_score = min(65.0, 30.0 + (slope_c_per_hr * 25.0))
                temp_trend_direction = "RISING"
                thermal_expl = f"Predictive Warning: Rising temperature gradient of +{slope_c_per_hr:.2f}°C/hr. Safe envelope will breach in ~{time_to_breach_mins:.0f} mins if unaddressed."
            elif curr_temp > ColdChainSpecs.TARGET_TEMP_C:
                thermal_score = ((curr_temp - ColdChainSpecs.TARGET_TEMP_C) / (ColdChainSpecs.MAX_SAFE_TEMP_C - ColdChainSpecs.TARGET_TEMP_C)) * 30.0
                temp_trend_direction = "STABLE"
                thermal_expl = f"Slight thermal drift ({curr_temp:.1f}°C), within acceptable buffer zone."
            else:
                thermal_score = 5.0
                temp_trend_direction = "STABLE"
                thermal_expl = f"Nominal chilled storage temperature maintained at {curr_temp:.1f}°C."

            factors.append(RiskSignal(
                factor_name="Thermal Trajectory & Stability",
                current_value_repr=f"{curr_temp:.1f}°C (Slope: {slope_c_per_hr:+.2f}°C/h)",
                threshold_repr=f"Target: {ColdChainSpecs.TARGET_TEMP_C:.1f}°C | Limit: {ColdChainSpecs.MAX_SAFE_TEMP_C:.1f}°C",
                direction=temp_trend_direction,
                weight_pct=ScoringWeights.WEIGHT_THERMAL_DRIFT * 100,
                score_contribution=round(thermal_score * ScoringWeights.WEIGHT_THERMAL_DRIFT, 1),
                explanation=thermal_expl
            ))

        # -------------------------------------------------------------
        # 2. Weather & Route Flood Hazard Analysis
        # -------------------------------------------------------------
        route_score = 0.0
        route_direction = "STABLE"

        if flags.get("missing_weather", False) or current_weather is None:
            missing_signals.append("Missing Corridor Weather Feed")
            route_score = 35.0  # Uncertainty buffer
            factors.append(RiskSignal(
                factor_name="Corridor Weather Visibility",
                current_value_repr="UNAVAILABLE (Fallback heuristic applied)",
                threshold_repr="Rain < 15 mm/h",
                direction="RISING",
                weight_pct=ScoringWeights.WEIGHT_ROUTE_HAZARD * 100,
                score_contribution=round(route_score * ScoringWeights.WEIGHT_ROUTE_HAZARD, 1),
                explanation="No live radar or meteorological feed. Regional monsoon climatology suggests moderate flood vulnerability."
            ))
        else:
            rain = current_weather.precipitation_mm_hr
            passability = current_weather.road_passability_score
            has_flood = current_weather.flood_warning_active

            if has_flood or passability < 0.35:
                route_score = 95.0
                route_direction = "CRITICAL"
                route_expl = f"Corridor {ShipmentBaseline.PRIMARY_ROUTE_ID} impassable due to flash flooding. Road passability index {passability:.2f}."
            elif rain >= 25.0 or passability < 0.70:
                route_score = 65.0
                route_direction = "RISING"
                route_expl = f"Heavy localized rainfall ({rain:.1f} mm/h). Road friction and waterlogging creating severe delays."
            elif rain >= 10.0:
                route_score = 25.0
                route_direction = "STABLE"
                route_expl = f"Moderate rain ({rain:.1f} mm/h). Traffic speeds throttled by ~15-20%."
            else:
                route_score = 5.0
                route_direction = "STABLE"
                route_expl = "Corridor meteorological conditions clear; normal transit speeds attainable."

            factors.append(RiskSignal(
                factor_name="Transit Corridor Road & Weather Hazard",
                current_value_repr=f"Precip: {rain:.1f} mm/h | Passability: {passability:.0%}",
                threshold_repr="Safe Passability >= 80%",
                direction=route_direction,
                weight_pct=ScoringWeights.WEIGHT_ROUTE_HAZARD * 100,
                score_contribution=round(route_score * ScoringWeights.WEIGHT_ROUTE_HAZARD, 1),
                explanation=route_expl
            ))

        # -------------------------------------------------------------
        # 3. Vehicle & Refrigeration Mechanical Integrity
        # -------------------------------------------------------------
        vehicle_score = 0.0
        vehicle_direction = "STABLE"
        has_veh_breakdown = any(e.event_type == "VEHICLE_BREAKDOWN" and e.severity == "CRITICAL" for e in detected_events)
        has_mech_warning = any(e.event_type == "VEHICLE_BREAKDOWN" and e.severity != "CRITICAL" for e in detected_events)

        if has_veh_breakdown:
            vehicle_score = 100.0
            vehicle_direction = "CRITICAL"
            veh_expl = "Primary transport vehicle mechanically stranded or canceled. Active propulsion halted."
        elif has_mech_warning:
            vehicle_score = 60.0
            vehicle_direction = "RISING"
            veh_expl = "Reefer compressor functioning in degraded/offline state. Rapid passive warm-up anticipated."
        else:
            vehicle_score = 5.0
            vehicle_direction = "STABLE"
            veh_expl = "Vehicle engine and dual-stage refrigeration unit reporting nominal operational telemetry."

        factors.append(RiskSignal(
            factor_name="Vehicle & Compressor Mechanical Integrity",
            current_value_repr="FAILURE / OFFLINE" if has_veh_breakdown else ("DEGRADED" if has_mech_warning else "HEALTHY"),
            threshold_repr="Status: HEALTHY / DUAL-POWER ON",
            direction=vehicle_direction,
            weight_pct=ScoringWeights.WEIGHT_VEHICLE_INTEGRITY * 100,
            score_contribution=round(vehicle_score * ScoringWeights.WEIGHT_VEHICLE_INTEGRITY, 1),
            explanation=veh_expl
        ))

        # -------------------------------------------------------------
        # 4. Destination & Cold Storage Hub Congestion
        # -------------------------------------------------------------
        hub_score = 0.0
        hub_direction = "STABLE"
        has_hub_outage = any(e.event_type == "STORAGE_UNAVAILABLE" for e in detected_events)

        if has_hub_outage:
            hub_score = 90.0
            hub_direction = "CRITICAL"
            hub_expl = f"Designated cold reception hub {ShipmentBaseline.PRIMARY_COLD_HUB_ID} closed. Risk of unloading into unconditioned ambient air."
        else:
            hub_score = 5.0
            hub_direction = "STABLE"
            hub_expl = f"Cold hub {ShipmentBaseline.PRIMARY_COLD_HUB_ID} confirmed dock availability with active pre-cooling."

        factors.append(RiskSignal(
            factor_name="Cold Hub Receiving Node Capacity",
            current_value_repr="UNAVAILABLE / GRID LOCKOUT" if has_hub_outage else "OPERATIONAL",
            threshold_repr="Dock Reserved & Available",
            direction=hub_direction,
            weight_pct=ScoringWeights.WEIGHT_HUB_CONGESTION * 100,
            score_contribution=round(hub_score * ScoringWeights.WEIGHT_HUB_CONGESTION, 1),
            explanation=hub_expl
        ))

        # -------------------------------------------------------------
        # 5. Composite Risk Calculation (Transparent Weighted Heuristic)
        # -------------------------------------------------------------
        composite_score = (
            (thermal_score * ScoringWeights.WEIGHT_THERMAL_DRIFT) +
            (route_score * ScoringWeights.WEIGHT_ROUTE_HAZARD) +
            (vehicle_score * ScoringWeights.WEIGHT_VEHICLE_INTEGRITY) +
            (hub_score * ScoringWeights.WEIGHT_HUB_CONGESTION)
        )

        # Clamping to [0, 100]
        composite_score = max(0.0, min(100.0, round(composite_score, 1)))

        # Determine Tier
        if composite_score >= 75.0:
            tier = "CRITICAL"
            overall_direction = "ACCELERATING"
            preventive_action = "IMMEDIATE ESCALATION: Halt transit on compromised route. Dispatch emergency replacement reefer or divert to nearest secondary cold hub."
        elif composite_score >= 50.0:
            tier = "ELEVATED"
            overall_direction = "WORSENING"
            preventive_action = "ACTIVE RECOVERY: Initiate contingency routing bypass and alert receiving distribution center of revised delivery window."
        elif composite_score >= 25.0:
            tier = "MODERATE"
            overall_direction = "WORSENING" if (temp_trend_direction == "RISING" or route_direction == "RISING") else "STABLE"
            preventive_action = "PREVENTIVE WATCH: Increase IoT polling frequency to 5-min intervals; verify backup reefer compressor readiness."
        else:
            tier = "LOW"
            overall_direction = "STABLE"
            preventive_action = "CONTINUE PLANNED RUN: All telemetry within certified cold-chain limits. Standard milestone tracking active."

        # Compute data confidence
        confidence = 100.0 - (len(missing_signals) * 20.0)

        return PredictiveRiskAssessment(
            timestamp=now,
            overall_risk_score=composite_score,
            risk_tier=tier,
            direction_of_change=overall_direction,
            contributing_factors=factors,
            time_to_breach_envelope_mins=time_to_breach_mins,
            recommended_preventive_action=preventive_action,
            missing_or_unreliable_signals=missing_signals,
            data_confidence_score=max(30.0, confidence),
            is_statistically_calibrated=False  # Explicit honesty flag: heuristic, not calibrated
        )
