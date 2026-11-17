"""Lets the tests import the package under its original name 'orvix_core' (the code now lives in backend/)."""
import sys, importlib
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import backend
sys.modules.setdefault("orvix_core", backend)
for name in ("config", "models", "disruption_sensor", "predictive_risk", "impact_scoring", "scenario_planner",
             "orchestrator", "audit_db", "simulation_engine"):
    sys.modules.setdefault(f"orvix_core.{name}", importlib.import_module(f"backend.{name}"))
