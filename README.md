@'
# ORVIX - Supply Chain Resilience Platform

ORVIX is a standalone Streamlit application demonstrating shipment monitoring, disruption detection, predictive risk analysis, business impact assessment, recovery planning, human approval, and audit tracking for seafood cold-chain logistics.

The platform combines deterministic Python processing with optional local AI explanations using Ollama and Phi-3.

## Application Workspaces

ORVIX contains 11 application pages:

1. Command Centre - Shipment condition, alerts, predictive risk, estimated exposure, and recovery recommendations.
2. Register Shipment - Register new shipment information.
3. Shipment Management - Review, search, and manage registered shipments.
4. Live Shipment Map - Demonstration of simulated route progress along a coastal Karnataka corridor.
5. Predictive Risk - Explainable thermal risk assessment, time-to-threshold estimates, and contributing signals.
6. Impact Scoring - Estimate commercial exposure from potential spoilage, delays, and emergency logistics.
7. Recovery Scenarios - Compare recovery alternatives and review feasibility and recommendations.
8. Agent Operations - Monitor the execution status, duration, and outputs of the five ORVIX agents.
9. Manager Dashboard - Manager-level operational overview and recovery decision entry point.
10. Human Approval - Approve, reject, or modify proposed recovery actions.
11. Audit Trail - Review recorded human decisions and governance events.

## Five-Agent Architecture

ORVIX uses five role-specific AI agents:

- Agent A - Disruption Sensor: Explains detected shipment disruptions.
- Agent B - Predictive Risk: Explains risk assessment results.
- Agent C - Impact Scoring: Explains estimated business impact.
- Agent D - Scenario Planner: Explains recovery alternatives and feasibility.
- Agent E - Orchestrator: Summarizes the analysis and supports the final decision workflow.

The deterministic Python pipeline remains authoritative for risk calculations, financial estimates, capacity validation, scenario feasibility, ranking, and approval governance.

AI-generated outputs are advisory. They cannot independently approve or execute recovery actions.

## Technology Stack

- Language: Python 3.11
- Frontend: Streamlit
- Database: SQLite
- AI Runtime: Ollama
- AI Model: Phi-3
- Testing: pytest

Two local SQLite databases are used:

- shipments.db - Stores registered shipment information.
- orvix_audit.db - Stores audit records of human decisions and governance events.

## Prototype Transparency and Limitations

- Shipment, vehicle, telemetry, route, and operational scenario data are simulated unless explicitly identified otherwise.
- The displayed route and GPS movement are demonstrations, not production live tracking.
- Scenario weather and operational inputs are simulated.
- The predictive risk score is a transparent heuristic and is not statistically calibrated.
- Financial exposure and recovery estimates are illustrative.
- Registered shipment information is integrated into selected analysis inputs, but not every registered field drives the simulated operational scenario.
- Recovery recommendations require human review and approval.
- Audit records are stored locally in SQLite. Database protections help prevent ordinary record modification and deletion, but do not provide cryptographic tamper-proofing.
- ORVIX is a demonstration and decision-support prototype, not a production logistics system or food-safety certification tool.

## Installation and Setup (Windows)

### Requirements

- Python 3.11
- Ollama (optional, for local AI explanations)

### 1. Create a virtual environment

```powershell
py -3.11 -m venv .venv

```

### 2. Activate the virtual environment

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Run the application

```powershell
python -m streamlit run app.py
```

### 5. Enable local AI explanations (optional)

Install Ollama, then download the Phi-3 model:

```powershell
ollama pull phi3:latest
```

Ensure Ollama is running before using the AI agent workflow.

## Running Tests

Run the automated test suite:

```powershell
python -m pytest -v
```

Check Python syntax:

```powershell
python -m compileall -q .\backend .\frontend .\app.py
```

## Project Structure

```text
ORVIX_Finale_Website/
├── app.py
├── backend/
├── frontend/
├── tests/
├── requirements.txt
├── README.md
├── shipments.db
└── orvix_audit.db
```

The SQLite database files are created locally when the application runs and should not be committed to GitHub.

## Responsible Use

ORVIX demonstrates AI-assisted operational decision support. Human operators remain responsible for reviewing and approving recovery decisions.
