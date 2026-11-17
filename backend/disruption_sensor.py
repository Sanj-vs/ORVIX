"""
Agent A: Disruption Sensing Agent
Identifies current, reported, and emerging disruptions across IoT telemetry, weather feeds,
vehicle mechanical health, and facility availability.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional

from .config import (
    ColdChainSpecs,
    ShipmentBaseline,
    DATA_SOURCE_REAL,
    DATA_SOURCE_SIMULATED,
    DATA_SOURCE_MANUAL
)
from .models import DisruptionEvent, TelemetryReading, WeatherCondition


class DisruptionSensingAgent:
    """
    Senses operational anomalies and disruptions.
    Explicitly distinguishes between:
      1. Directly observed physical facts (e.g. temperature telemetry)
      2. External forecasts (e.g. weather rainfall models)
      3. Injected simulation / manual user scenario overrides
    """

    def __init__(self, agent_name: str = "Disruption-Sensing-Agent-01"):
        self.agent_name = agent_name

    def evaluate_environment(
        self,
        current_telemetry: Optional[TelemetryReading],
        weather: Optional[WeatherCondition],
        vehicle_status: Dict[str, Any],
        cold_hub_status: Dict[str, Any],
        buyer_order_status: Dict[str, Any],
        manual_scenario_flags: Optional[Dict[str, bool]] = None
    ) -> List[DisruptionEvent]:
        """
        Scan all sensor and business feeds and return detected disruption events.
        """
        events: List[DisruptionEvent] = []
        now = datetime.now()
        manual_flags = manual_scenario_flags or {}

        # 1. Telemetry / Temperature & Compressor Inspection
        if current_telemetry is None:
            events.append(DisruptionEvent(
                event_id=f"EVT-TEL-MISSING-{now.strftime('%H%M%S')}",
                event_type="TELEMETRY_DATA_LOSS",
                timestamp=now,
                source=DATA_SOURCE_SIMULATED,
                severity="HIGH",
                confidence_pct=60.0,
                headline="Reefer Telemetry Signal Missing / Stale",
                operational_relevance="Cargo environmental integrity cannot be verified. Automatic caution protocol invoked.",
                is_observed_fact=True
            ))
        else:
            temp = current_telemetry.temperature_c
            source_tag = current_telemetry.source or DATA_SOURCE_SIMULATED

            if temp >= ColdChainSpecs.CRITICAL_BREACH_TEMP_C:
                events.append(DisruptionEvent(
                    event_id=f"EVT-TEMP-CRIT-{now.strftime('%H%M%S')}",
                    event_type="THERMAL_EXCURSION",
                    timestamp=now,
                    source=source_tag,
                    severity="CRITICAL",
                    confidence_pct=95.0,
                    headline=f"Critical Thermal Breach: Cargo Bay at {temp:.1f}°C (Safe limit: {ColdChainSpecs.MAX_SAFE_TEMP_C}°C)",
                    operational_relevance="Direct threat of enzymatic decomposition and bacterial growth in fresh seafood.",
                    is_observed_fact=True
                ))
            elif temp >= ColdChainSpecs.WARNING_TEMP_C:
                events.append(DisruptionEvent(
                    event_id=f"EVT-TEMP-WARN-{now.strftime('%H%M%S')}",
                    event_type="THERMAL_EXCURSION",
                    timestamp=now,
                    source=source_tag,
                    severity="MEDIUM",
                    confidence_pct=90.0,
                    headline=f"Thermal Warning: Reefer temperature drifting up to {temp:.1f}°C",
                    operational_relevance="Operating inside buffer zone. If warming continues, safe shelf-life threshold will be breached.",
                    is_observed_fact=True
                ))

            if current_telemetry.compressor_status in ["DEGRADED", "OFFLINE"]:
                events.append(DisruptionEvent(
                    event_id=f"EVT-MECH-COMP-{now.strftime('%H%M%S')}",
                    event_type="VEHICLE_BREAKDOWN",
                    timestamp=now,
                    source=source_tag,
                    severity="HIGH" if current_telemetry.compressor_status == "OFFLINE" else "MEDIUM",
                    confidence_pct=92.0,
                    headline=f"Refrigeration Compressor Unit: {current_telemetry.compressor_status}",
                    operational_relevance="Active cooling impaired. Reefer relies entirely on passive insulation phase change.",
                    is_observed_fact=True
                ))

        # 2. Weather & Corridor Road Flooding Inspection
        if weather is not None:
            w_source = weather.source or DATA_SOURCE_SIMULATED
            if weather.flood_warning_active or weather.precipitation_mm_hr >= 30.0 or manual_flags.get("flood_active", False):
                events.append(DisruptionEvent(
                    event_id=f"EVT-WX-FLOOD-{now.strftime('%H%M%S')}",
                    event_type="WEATHER_FLOOD",
                    timestamp=now,
                    source=w_source if not manual_flags.get("flood_active", False) else DATA_SOURCE_MANUAL,
                    severity="CRITICAL" if weather.precipitation_mm_hr >= 45.0 or weather.road_passability_score < 0.3 else "HIGH",
                    confidence_pct=88.0,
                    headline=f"Severe Corridor Flash Flooding along {ShipmentBaseline.PRIMARY_ROUTE_ID}",
                    operational_relevance=f"Precipitation {weather.precipitation_mm_hr:.1f} mm/h. Road passability index reduced to {weather.road_passability_score:.2f}. Severe transit stoppage expected.",
                    is_observed_fact=False  # Weather observations combine radar & forecast models
                ))
            elif weather.precipitation_mm_hr >= 15.0:
                events.append(DisruptionEvent(
                    event_id=f"EVT-WX-RAIN-{now.strftime('%H%M%S')}",
                    event_type="WEATHER_FLOOD",
                    timestamp=now,
                    source=w_source,
                    severity="LOW",
                    confidence_pct=85.0,
                    headline=f"Moderate Rainfall along {ShipmentBaseline.PRIMARY_ROUTE_ID} ({weather.precipitation_mm_hr:.1f} mm/h)",
                    operational_relevance="Speeds reduced by 15-25%. Minor transit delays anticipated.",
                    is_observed_fact=False
                ))

        # 3. Vehicle Availability Inspection
        primary_veh_avail = vehicle_status.get("is_available", True)
        if not primary_veh_avail or manual_flags.get("vehicle_unavailable", False):
            events.append(DisruptionEvent(
                event_id=f"EVT-FLT-UNAVAIL-{now.strftime('%H%M%S')}",
                event_type="VEHICLE_BREAKDOWN",
                timestamp=now,
                source=DATA_SOURCE_MANUAL if manual_flags.get("vehicle_unavailable") else DATA_SOURCE_SIMULATED,
                severity="CRITICAL",
                confidence_pct=98.0,
                headline=f"Primary Vehicle Unavailable: {ShipmentBaseline.PRIMARY_VEHICLE_ID}",
                operational_relevance="Mechanical failure or unscheduled depot maintenance. Carrier cannot dispatch planned reefer.",
                is_observed_fact=True
            ))

        # 4. Cold Storage Hub Availability Inspection
        primary_hub_avail = cold_hub_status.get("is_available", True)
        if not primary_hub_avail or manual_flags.get("storage_unavailable", False):
            events.append(DisruptionEvent(
                event_id=f"EVT-HUB-UNAVAIL-{now.strftime('%H%M%S')}",
                event_type="STORAGE_UNAVAILABLE",
                timestamp=now,
                source=DATA_SOURCE_MANUAL if manual_flags.get("storage_unavailable") else DATA_SOURCE_SIMULATED,
                severity="HIGH",
                confidence_pct=95.0,
                headline=f"Preferred Cold Storage Depot {ShipmentBaseline.PRIMARY_COLD_HUB_ID} Unavailable",
                operational_relevance="Capacity overload or grid backup failure. Inbound receiving docks temporarily closed.",
                is_observed_fact=True
            ))

        # 5. Buyer Order Adjustment / Demand Shift
        requested_qty = buyer_order_status.get("requested_qty_kg", ShipmentBaseline.INITIAL_QTY_KG)
        if requested_qty != ShipmentBaseline.INITIAL_QTY_KG or manual_flags.get("demand_shift", False):
            shift_delta = requested_qty - ShipmentBaseline.INITIAL_QTY_KG
            events.append(DisruptionEvent(
                event_id=f"EVT-DMD-SHIFT-{now.strftime('%H%M%S')}",
                event_type="DEMAND_SHIFT",
                timestamp=now,
                source=DATA_SOURCE_MANUAL if manual_flags.get("demand_shift") else DATA_SOURCE_SIMULATED,
                severity="MEDIUM",
                confidence_pct=99.0,
                headline=f"Buyer Order Quantity Revised: {requested_qty:.0f} kg ({shift_delta:+.0f} kg delta)",
                operational_relevance="Buyer adjusted purchase commitment due to inventory replenishment cycle.",
                is_observed_fact=True
            ))

        return events
