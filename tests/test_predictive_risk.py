from datetime import datetime, timedelta

import pytest

from backend.models import (
    TelemetryReading,
    WeatherCondition,
    DisruptionEvent,
)
from backend.predictive_risk import PredictiveRiskAgent


@pytest.fixture
def agent():
    return PredictiveRiskAgent()


def make_reading(minutes_ago, temperature, compressor="NORMAL"):
    base_time = datetime(2026, 1, 1, 12, 0, 0)

    return TelemetryReading(
        timestamp=base_time - timedelta(minutes=minutes_ago),
        temperature_c=temperature,
        humidity_pct=85.0,
        compressor_status=compressor,
        gps_lat=12.91,
        gps_lon=74.85,
        battery_or_fuel_pct=90.0,
        source="SIMULATED",
    )


def make_weather(rain=0.0, passability=0.98, flood=False):
    return WeatherCondition(
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
        corridor_name="TEST-ROUTE",
        precipitation_mm_hr=rain,
        flood_warning_active=flood,
        road_passability_score=passability,
        forecast_rain_next_4h_mm=0.0,
        source="SIMULATED",
    )


def make_event(event_type, severity):
    return DisruptionEvent(
        event_id="TEST-EVENT-001",
        event_type=event_type,
        timestamp=datetime(2026, 1, 1, 12, 0, 0),
        source="SIMULATED",
        severity=severity,
        confidence_pct=95.0,
        headline="Test disruption",
        operational_relevance="Test event",
        is_observed_fact=True,
    )


def get_factor(result, factor_name):
    return next(
        factor for factor in result.contributing_factors
        if factor.factor_name == factor_name
    )


def test_normal_conditions_produce_low_risk(agent):
    readings = [
        make_reading(60, 2.0),
        make_reading(45, 2.0),
        make_reading(30, 2.0),
        make_reading(15, 2.0),
        make_reading(0, 2.0),
    ]

    result = agent.evaluate_predictive_risk(
        telemetry_history=readings,
        current_weather=make_weather(),
        detected_events=[],
    )

    assert result.risk_tier == "LOW"
    assert result.overall_risk_score == 5.0
    assert result.missing_or_unreliable_signals == []


def test_rapid_temperature_rise_generates_early_warning(agent):
    readings = [
        make_reading(60, 2.0),
        make_reading(0, 3.0),
    ]

    result = agent.evaluate_predictive_risk(
        telemetry_history=readings,
        current_weather=make_weather(),
        detected_events=[],
    )

    thermal = get_factor(result, "Thermal Trajectory & Stability")

    assert thermal.direction == "RISING"
    assert result.time_to_breach_envelope_mins == 60.0


def test_critical_temperature_breach_is_detected(agent):
    readings = [
        make_reading(60, 2.0),
        make_reading(0, 6.2),
    ]

    result = agent.evaluate_predictive_risk(
        telemetry_history=readings,
        current_weather=make_weather(),
        detected_events=[],
    )

    thermal = get_factor(result, "Thermal Trajectory & Stability")

    assert thermal.direction == "CRITICAL"
    assert thermal.score_contribution == 35.0
    assert result.time_to_breach_envelope_mins == 0.0


def test_missing_telemetry_and_weather_reduce_confidence(agent):
    result = agent.evaluate_predictive_risk(
        telemetry_history=[],
        current_weather=None,
        detected_events=[],
    )

    assert len(result.missing_or_unreliable_signals) == 2
    assert result.data_confidence_score == 60.0
    assert result.overall_risk_score > 0.0


def test_flooding_increases_route_risk(agent):
    result = agent.evaluate_predictive_risk(
        telemetry_history=[make_reading(0, 2.0)],
        current_weather=make_weather(
            rain=48.5,
            passability=0.18,
            flood=True,
        ),
        detected_events=[],
    )

    route = get_factor(
        result,
        "Transit Corridor Road & Weather Hazard",
    )

    assert route.direction == "CRITICAL"
    assert route.score_contribution == 28.5


def test_critical_vehicle_breakdown_increases_vehicle_risk(agent):
    event = make_event("VEHICLE_BREAKDOWN", "CRITICAL")

    result = agent.evaluate_predictive_risk(
        telemetry_history=[make_reading(0, 2.0)],
        current_weather=make_weather(),
        detected_events=[event],
    )

    vehicle = get_factor(
        result,
        "Vehicle & Compressor Mechanical Integrity",
    )

    assert vehicle.direction == "CRITICAL"
    assert vehicle.score_contribution == 20.0


def test_risk_score_and_calibration_flag_are_valid(agent):
    result = agent.evaluate_predictive_risk(
        telemetry_history=[make_reading(0, 2.0)],
        current_weather=make_weather(),
        detected_events=[],
    )

    assert 0.0 <= result.overall_risk_score <= 100.0
    assert result.is_statistically_calibrated is False
