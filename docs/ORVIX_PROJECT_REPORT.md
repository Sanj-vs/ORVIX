# ORVIX — Project Report

## Overview
ORVIX is a standalone supply-chain resilience website that helps operations teams monitor
shipments, detect disruptions, estimate business impact, compare recovery plans and record
human decisions.

## Architecture
- **Website:** Streamlit interface with operational dashboards and management pages.
- **Application logic:** Python services and a five-agent workflow.
- **Data storage:** SQLite for shipment records and local audit history.
- **Climate information:** Open-Meteo API when internet access is available.
- **Optional language model:** Ollama / Phi-3 for advisory explanations.

## Agent workflow
A. Disruption Sensing — evaluates telemetry, weather and operational flags.
B. Predictive Risk — calculates an explainable heuristic risk index.
C. Impact Scoring — estimates delay, spoilage and logistics exposure.
D. Scenario Planning — generates, validates and ranks recovery alternatives.
E. Orchestration and Human Approval — coordinates the workflow and records operator decisions.

## Responsible-use boundaries
Demonstration shipment and telemetry values are simulated unless explicitly identified
otherwise. The risk score is not statistically calibrated. Recovery plans are recommendations,
not autonomous commands. A human operator must review and approve consequential actions.
The software does not certify food safety.
