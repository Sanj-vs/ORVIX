# ORVIX Platform Overview

ORVIX is a vendor-neutral supply-chain resilience application.

## Core workflow
1. Ingest shipment, vehicle, storage, weather and telemetry data.
2. Detect disruptions using the Disruption Sensing Agent.
3. Estimate operational risk using the Predictive Risk Agent.
4. Calculate business impact using the Impact Scoring Agent.
5. Generate and rank recovery options using the Scenario Planning Agent.
6. Require a human operator to approve, reject or modify a proposed action.
7. Store the decision and rationale in the local SQLite audit trail.

## Data and governance
The demonstration uses simulated shipment and telemetry inputs, with optional live
weather retrieval from Open-Meteo. Risk scoring and feasibility checks are deterministic
and explainable. Local language-model output is advisory only. Human approval remains
mandatory for consequential actions.
