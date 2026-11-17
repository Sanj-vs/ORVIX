"""
Configuration constants, business thresholds, and operational parameters for ORVIX.
All thresholds are transparent, configurable, and grounded in cold-chain logistics practices.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ColdChainSpecs:
    """Cold chain temperature tolerances for perishable seafood (chilled species)."""
    COMMODITY_NAME: str = "Fresh Chilled Atlantic Salmon & Tiger Prawns"
    TARGET_TEMP_C: float = 2.0
    MIN_SAFE_TEMP_C: float = 0.0
    MAX_SAFE_TEMP_C: float = 4.0
    WARNING_TEMP_C: float = 3.8
    CRITICAL_BREACH_TEMP_C: float = 6.0
    RAPID_RISE_GRADIENT_C_PER_HR: float = 0.5  # Warning slope


@dataclass(frozen=True)
class ShipmentBaseline:
    """Baseline operational parameters for the primary demonstration shipment."""
    SHIPMENT_ID: str = "SHP-2026-SEAFOOD-800"
    BUYER_NAME: str = "Metro Grand Culinary Logistics (Tier-1 Hospitality Buyer)"
    ORIGIN: str = "Coastal Aquaculture Logistics Terminal (Gate 4)"
    DESTINATION: str = "Metro Cold Distribution Hub (Bay 12)"
    INITIAL_QTY_KG: float = 800.0
    COMMODITY_VALUE_PER_KG_USD: float = 18.50  # Total cargo value = $14,800
    PLANNED_TRANSIT_MINUTES: int = 360  # 6.0 Hours
    MAX_ALLOWED_DELAY_MINUTES: int = 60  # Contractual SLA limit
    SLA_PENALTY_PER_HOUR_USD: float = 350.0
    PRIMARY_ROUTE_ID: str = "RT-101-COASTAL-HIGHWAY"
    PRIMARY_VEHICLE_ID: str = "REEFER-V1-K2"
    PRIMARY_VEHICLE_CAPACITY_KG: float = 1000.0
    PRIMARY_COLD_HUB_ID: str = "HUB-ALPHA-BAY"


# -------------------------------------------------------------
# SIMULATED BACKUP INVENTORY — DEMONSTRATION DATA ONLY
# These values are not connected to live fleet or hub systems.
# -------------------------------------------------------------

SIMULATED_FLEET_INVENTORY = [
    {
        "vehicle_id": "REEFER-V2-EXP",
        "capacity_kg": 1200.0,
        "is_available": True,
        "is_refrigerated": True,
        "source": "SIMULATED"
    },
    {
        "vehicle_id": "REEFER-V4-METRO",
        "capacity_kg": 900.0,
        "is_available": True,
        "is_refrigerated": True,
        "source": "SIMULATED"
    },
    {
        "vehicle_id": "REEFER-V5",
        "capacity_kg": 500.0,
        "is_available": True,
        "is_refrigerated": True,
        "source": "SIMULATED"
    },
    {
        "vehicle_id": "REEFER-V6",
        "capacity_kg": 500.0,
        "is_available": True,
        "is_refrigerated": True,
        "source": "SIMULATED"
    }
]

SIMULATED_HUB_INVENTORY = [
    {
        "hub_id": "HUB-BETA-INLAND",
        "storage_capacity_kg": 1500.0,
        "is_available": True,
        "source": "SIMULATED"
    }
]

@dataclass(frozen=True)
class ScoringWeights:
    """Configurable weights for transparent risk and multi-criteria recovery ranking."""
    # Predictive Risk Component Weights (sum = 1.0)
    WEIGHT_THERMAL_DRIFT: float = 0.35
    WEIGHT_ROUTE_HAZARD: float = 0.30
    WEIGHT_VEHICLE_INTEGRITY: float = 0.20
    WEIGHT_HUB_CONGESTION: float = 0.15

    # Recovery Plan Evaluation Weights (sum = 1.0)
    RANK_WEIGHT_FEASIBILITY: float = 0.30
    RANK_WEIGHT_DEADLINE_PERFORMANCE: float = 0.25
    RANK_WEIGHT_RISK_REDUCTION: float = 0.25
    RANK_WEIGHT_COST_EFFICIENCY: float = 0.20


# Data source provenance labels
DATA_SOURCE_REAL = "REAL"
DATA_SOURCE_SIMULATED = "SIMULATED"
DATA_SOURCE_MANUAL = "MANUAL"

# System status constants
STATUS_DRAFT = "DRAFT_PLAN"
STATUS_OPTIMAL = "NORMAL_OPERATIONS"
STATUS_WARNING = "PREDICTIVE_WARNING"
STATUS_DISRUPTED = "ACTIVE_DISRUPTION"
STATUS_PENDING_APPROVAL = "RECOMMENDATION_PENDING"
STATUS_APPROVED = "APPROVED_ACTION"
STATUS_REJECTED = "REJECTED_ACTION"
STATUS_MODIFIED = "MODIFIED_ACTION"
STATUS_ESCALATED = "ESCALATED_TO_HUMAN"
