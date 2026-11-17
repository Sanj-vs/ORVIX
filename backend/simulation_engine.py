"""
Simulation Engine & Scenario State Generator
Produces deterministic sensor telemetry, weather feeds, and side-by-side Proactive vs Reactive benchmarks.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple

from .config import ColdChainSpecs, ShipmentBaseline, DATA_SOURCE_SIMULATED
from .models import TelemetryReading, WeatherCondition


class SimulationEngine:
    """
    Generates realistic, repeatable cold-chain telemetry and disruption signals.
    """

    @staticmethod
    def get_baseline_telemetry(num_samples: int = 8) -> List[TelemetryReading]:
        """Generate normal, safe cold-chain telemetry readings around 2.1°C."""
        base_time = datetime.now() - timedelta(minutes=num_samples * 15)
        readings = []
        temps = [2.0, 2.1, 2.0, 2.2, 2.1, 2.0, 2.1, 2.2]
        for i in range(min(num_samples, len(temps))):
            readings.append(TelemetryReading(
                timestamp=base_time + timedelta(minutes=i * 15),
                temperature_c=temps[i],
                humidity_pct=88.0,
                compressor_status="NORMAL",
                gps_lat=12.91 + (i * 0.04),
                gps_lon=74.85 + (i * 0.05),
                battery_or_fuel_pct=94.0 - (i * 1.5),
                source=DATA_SOURCE_SIMULATED
            ))
        return readings

    @staticmethod
    def get_early_warning_telemetry(num_samples: int = 8) -> List[TelemetryReading]:
        """
        Generate telemetry sequence showing early warming trend (dT/dt > 0.5°C/hr).
        Crucial: Temperature is still under 4.0°C (not yet a breach!), but trending upward.
        """
        base_time = datetime.now() - timedelta(minutes=num_samples * 15)
        readings = []
        # Upward drift from 2.2°C to 3.6°C
        temps = [2.2, 2.4, 2.6, 2.9, 3.1, 3.3, 3.5, 3.7]
        for i in range(min(num_samples, len(temps))):
            status = "DEGRADED" if i >= 4 else "NORMAL"
            readings.append(TelemetryReading(
                timestamp=base_time + timedelta(minutes=i * 15),
                temperature_c=temps[i],
                humidity_pct=84.0 - (i * 1.0),
                compressor_status=status,
                gps_lat=13.05 + (i * 0.04),
                gps_lon=75.10 + (i * 0.05),
                battery_or_fuel_pct=88.0 - (i * 2.0),
                source=DATA_SOURCE_SIMULATED
            ))
        return readings

    @staticmethod
    def get_critical_breach_telemetry(num_samples: int = 8) -> List[TelemetryReading]:
        """Generate telemetry showing acute compressor failure and critical thermal breach (5.8°C+)."""
        base_time = datetime.now() - timedelta(minutes=num_samples * 15)
        readings = []
        temps = [2.5, 2.9, 3.4, 3.9, 4.4, 5.0, 5.6, 6.2]
        for i in range(min(num_samples, len(temps))):
            readings.append(TelemetryReading(
                timestamp=base_time + timedelta(minutes=i * 15),
                temperature_c=temps[i],
                humidity_pct=75.0 - (i * 1.5),
                compressor_status="OFFLINE" if i >= 4 else "DEGRADED",
                gps_lat=13.20 + (i * 0.04),
                gps_lon=75.35 + (i * 0.05),
                battery_or_fuel_pct=72.0 - (i * 3.0),
                source=DATA_SOURCE_SIMULATED
            ))
        return readings

    @staticmethod
    def get_weather_scenario(scenario_stage: str = "NORMAL") -> WeatherCondition:
        """Return weather condition matching simulation stage."""
        now = datetime.now()
        if scenario_stage == "EARLY_WARNING":
            return WeatherCondition(
                timestamp=now,
                corridor_name=ShipmentBaseline.PRIMARY_ROUTE_ID,
                precipitation_mm_hr=22.0,
                flood_warning_active=False,
                road_passability_score=0.72,
                forecast_rain_next_4h_mm=45.0,
                source=DATA_SOURCE_SIMULATED
            )
        elif scenario_stage == "CRITICAL_DISRUPTION":
            return WeatherCondition(
                timestamp=now,
                corridor_name=ShipmentBaseline.PRIMARY_ROUTE_ID,
                precipitation_mm_hr=48.5,
                flood_warning_active=True,
                road_passability_score=0.18,
                forecast_rain_next_4h_mm=85.0,
                source=DATA_SOURCE_SIMULATED
            )
        else:
            return WeatherCondition(
                timestamp=now,
                corridor_name=ShipmentBaseline.PRIMARY_ROUTE_ID,
                precipitation_mm_hr=3.0,
                flood_warning_active=False,
                road_passability_score=0.98,
                forecast_rain_next_4h_mm=5.0,
                source=DATA_SOURCE_SIMULATED
            )

    @staticmethod
    def get_proactive_vs_reactive_comparison(
        shipment_qty_kg: float = 800.0,
        cargo_val_per_kg: float = 18.50
    ) -> Dict[str, Any]:
        """
        Calculates a side-by-side comparison (simulated figures):
        Reactive approach (wait for failure) vs ORVIX Proactive approach (early warning).
        """
        # Reactive Scenario: No action taken until highway flooded and reefer compressor died
        reactive_delay_mins = 270  # 4.5 hours
        reactive_spoilage_kg = 350.0  # 43.7% of consignment compromised
        reactive_spoilage_cost = reactive_spoilage_kg * cargo_val_per_kg
        reactive_excess_delay_hrs = max(0.0, (reactive_delay_mins - 60) / 60.0)
        reactive_sla_penalty = reactive_excess_delay_hrs * 350.0
        reactive_emergency_towing = 650.0
        reactive_total_loss = reactive_spoilage_cost + reactive_sla_penalty + reactive_emergency_towing

        # Proactive Scenario: ORVIX triggered early warning; re-routed via elevated corridor
        proactive_delay_mins = 35  # within 60 min SLA
        proactive_spoilage_kg = 0.0  # no predicted loss in the simulation
        proactive_spoilage_cost = 0.0
        proactive_sla_penalty = 0.0
        proactive_reroute_cost = 380.0
        proactive_total_loss = proactive_reroute_cost

        net_savings_usd = reactive_total_loss - proactive_total_loss
        pct_improvement = ((reactive_total_loss - proactive_total_loss) / reactive_total_loss) * 100.0

        return {
            "reactive": {
                "action_trigger": "Post-Failure (After Reefer Excursion & Road Inundation)",
                "delay_minutes": reactive_delay_mins,
                "spoilage_kg": reactive_spoilage_kg,
                "spoilage_cost_usd": round(reactive_spoilage_cost, 2),
                "sla_penalty_usd": round(reactive_sla_penalty, 2),
                "emergency_logistics_usd": reactive_emergency_towing,
                "total_cost_usd": round(reactive_total_loss, 2),
                "delivered_kg": shipment_qty_kg - reactive_spoilage_kg,
                "customer_sla_met": False
            },
            "proactive": {
                "action_trigger": "Early Warning (ORVIX Stage 2 Gradient Alert)",
                "delay_minutes": proactive_delay_mins,
                "spoilage_kg": proactive_spoilage_kg,
                "spoilage_cost_usd": proactive_spoilage_cost,
                "sla_penalty_usd": proactive_sla_penalty,
                "emergency_logistics_usd": proactive_reroute_cost,
                "total_cost_usd": round(proactive_total_loss, 2),
                "delivered_kg": shipment_qty_kg,
                "customer_sla_met": True
            },
            "comparison": {
                "net_avoided_loss_usd": round(net_savings_usd, 2),
                "saved_cargo_kg": reactive_spoilage_kg,
                "delay_saved_minutes": reactive_delay_mins - proactive_delay_mins,
                "loss_reduction_pct": round(pct_improvement, 1)
            }
        }
