import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
from datetime import datetime
from backend.orchestrator import OrchestratorAgent
from backend.llm_agents import ORVIXLLMAgents
from backend.simulation_engine import SimulationEngine
from backend.config import ShipmentBaseline
from backend.audit_db import AuditDB
import json
# Shipment registration modules
from backend.shipment_db import ShipmentDB
from frontend.shipment_pages import render_register_shipment
from frontend.shipment_management import render_shipment_management
from frontend.manager_dashboard import render_manager_dashboard

# ---------------------------------------------------------
# 1. PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="ORVIX",
    page_icon="🌊",
    layout="wide"
)

# ---------------------------------------------------------
# 2. NAVIGATION DEFINITIONS AND EARLY SESSION STATE
# ---------------------------------------------------------

NAV_GROUPS = [
    ("OPERATIONS", [
        "Command Centre",
        "Register Shipment",
        "Shipment Management",
        "Live Shipment Map",
    ]),
    ("INTELLIGENCE", [
        "Predictive Risk",
        "Impact Scoring",
        "Recovery Scenarios",
        "Agent Operations",
    ]),
    ("GOVERNANCE", [
        "Manager Dashboard",
        "Human Approval",
        "Audit Trail",
    ]),
]

page_options = [item for _, items in NAV_GROUPS for item in items]

PAGE_GROUP = {
    item: group for group, items in NAV_GROUPS for item in items
}

PAGE_DESCRIPTIONS = {
    "Command Centre": "Shipment condition, predictive risk, estimated exposure and recovery options for the selected scenario.",
    "Register Shipment": "Create a new shipment record in the shipment database.",
    "Shipment Management": "Review and manage registered shipments.",
    "Live Shipment Map": "Simulated route progress along the coastal Karnataka demonstration corridor.",
    "Predictive Risk": "Explainable thermal risk index, time-to-threshold estimate and contributing signals.",
    "Impact Scoring": "Estimated commercial exposure from spoilage, delay penalties and emergency logistics.",
    "Recovery Scenarios": "Compare recovery options and review the recommended next step.",
    "Manager Dashboard": "Manager overview and entry point for recovery decisions.",
    "Human Approval": "Manager review workspace: approve, reject or modify the recommended recovery action.",
    "Audit Trail": "Persistent record of human decisions and governance events.",
    "Agent Operations": "Execution history, status, duration and actual outputs from the ORVIX processing agents.",
}


def go_to(page_name):
    """Button callback: switch the active workspace page."""
    st.session_state.selected_page = page_name


if "appearance" not in st.session_state:
    st.session_state.appearance = "Light"

if "selected_page" not in st.session_state:
    st.session_state.selected_page = "Command Centre"

# Manager dashboard can request navigation to the approval workspace.
if st.session_state.pop("manager_approval_navigation", False):
    st.session_state.selected_page = "Human Approval"

if st.session_state.selected_page not in page_options:
    st.session_state.selected_page = "Command Centre"

# ---------------------------------------------------------
# 3. ORVIX DESIGN SYSTEM (OCEAN ENTERPRISE)
# ---------------------------------------------------------

dark_mode = st.session_state.appearance == "Dark"

if dark_mode:
    THEME = {
        "BG": "#0B1924",
        "SURFACE": "#142735",
        "TEXT": "#E8F1F2",
        "MUTED": "#A4BBC4",
        "BORDER": "#294451",
        "TEAL_TEXT": "#4FD1D0",
        "AMBER_TEXT": "#F4B860",
        "RED_TEXT": "#FF8A80",
    }
else:
    THEME = {
        "BG": "#F2F7F8",
        "SURFACE": "#FFFFFF",
        "TEXT": "#102638",
        "MUTED": "#607782",
        "BORDER": "#DCE8EB",
        "TEAL_TEXT": "#087E83",
        "AMBER_TEXT": "#9A6412",
        "RED_TEXT": "#B3261E",
    }

CSS_TEMPLATE = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@600;700;800&display=swap');

:root {
    --ocean-navy: #102638;
    --ocean-teal: #087E83;
    --ocean-ice: #E8F1F2;
    --ocean-amber: #F4B860;
    --app-bg: __BG__;
    --surface: __SURFACE__;
    --text: __TEXT__;
    --muted: __MUTED__;
    --border: __BORDER__;
    --teal-text: __TEAL_TEXT__;
    --amber-text: __AMBER_TEXT__;
    --red-text: __RED_TEXT__;
}

html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

.stApp {
    background: var(--app-bg);
    color: var(--text);
}

header[data-testid="stHeader"] {
    background: var(--app-bg);
}

[data-testid="stDecoration"], #MainMenu, footer {
    display: none !important;
}

.block-container {
    padding-top: 3rem;
    padding-bottom: 2rem;
    max-width: 1550px;
}

h1, h2, h3, h4 {
    font-family: 'Manrope', sans-serif;
    color: var(--text);
    letter-spacing: -0.01em;
}

h3 {
    font-size: 1.05rem !important;
    font-weight: 700 !important;
    margin-top: 0.4rem;
}

p, li, label, span {
    color: var(--text);
}

/* ---------- Sidebar (always deep navy) ---------- */

[data-testid="stSidebar"] {
    background: #102638 !important;
    border-right: 1px solid #1D3A52;
}

[data-testid="stSidebar"] *,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label {
    color: #E8F1F2;
}

[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
[data-testid="stSidebar"] .stCaption {
    color: #9DB7C2 !important;
}

[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
    gap: 0.3rem;
}

[data-testid="stSidebar"] .stButton > button {
    width: 100%;
    justify-content: flex-start;
    text-align: left;
    background: transparent;
    border: 1px solid transparent;
    color: #D5E4E8;
    font-weight: 500;
    padding: 0.35rem 0.8rem;
    border-radius: 8px;
    box-shadow: none;
}

[data-testid="stSidebar"] .stButton > button div,
[data-testid="stSidebar"] .stButton > button p {
    justify-content: flex-start;
    text-align: left;
    width: 100%;
    color: inherit;
}

[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255, 255, 255, 0.08);
    border-color: transparent;
    color: #FFFFFF;
}

[data-testid="stSidebar"] .stButton > button[kind="primary"],
[data-testid="stSidebar"] .stButton button[data-testid^="stBaseButton-primary"] {
    background: #087E83 !important;
    color: #FFFFFF !important;
    font-weight: 600;
    border: none;
}

[data-testid="stSidebar"] [data-baseweb="select"] > div {
    background: #173549 !important;
    border: 1px solid #2B4D63 !important;
}

[data-testid="stSidebar"] [data-baseweb="select"] * {
    color: #E8F1F2 !important;
}

[data-testid="stSidebar"] [data-baseweb="select"] svg {
    fill: #E8F1F2 !important;
}

.sb-brand {
    display: flex;
    align-items: center;
    gap: 10px;
    margin: 4px 0 2px;
}

.sb-wordmark {
    font-family: 'Manrope', sans-serif;
    font-size: 24px;
    font-weight: 800;
    letter-spacing: 0.08em;
    color: #FFFFFF !important;
}

.sb-tagline {
    font-size: 12px;
    color: #B7CCD3 !important;
    line-height: 1.4;
    margin-top: 2px;
}

.sb-slogan {
    font-size: 10px;
    letter-spacing: 0.12em;
    font-weight: 700;
    color: #7FD6D3 !important;
    margin-top: 8px;
}

.sb-label {
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.12em;
    color: #8FB2BD !important;
    margin: 6px 0 2px;
}

.nav-group {
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.14em;
    color: #7FD6D3 !important;
    margin: 12px 0 2px;
    padding-left: 4px;
}

.sb-notice {
    background: rgba(255, 255, 255, 0.06);
    border: 1px solid #2B4D63;
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 11.5px;
    line-height: 1.5;
    color: #C9DCE2 !important;
}

.sb-notice b {
    color: #FFFFFF !important;
}

/* ---------- Metrics, tables, forms ---------- */

[data-testid="stMetric"] {
    background: var(--surface);
    border: 1px solid var(--border);
    padding: 14px 16px;
    border-radius: 14px;
}

[data-testid="stMetricLabel"],
[data-testid="stMetricValue"],
[data-testid="stMetricDelta"] {
    color: var(--text) !important;
}

[data-testid="stMetricValue"] {
    font-family: 'Manrope', sans-serif;
    font-size: 1.35rem;
}

[data-testid="stMetricValue"] div {
    white-space: normal;
}

[data-testid="stCaptionContainer"],
.stCaption {
    color: var(--muted) !important;
}

[data-testid="stDataFrame"],
[data-testid="stTable"] {
    border: 1px solid var(--border);
    border-radius: 12px;
}

[data-testid="stForm"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 18px;
}

[data-testid="stExpander"] {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
}

[data-testid="stVerticalBlockBorderWrapper"] {
    border-color: var(--border) !important;
    border-radius: 14px;
}

[data-testid="stAlert"] {
    border-radius: 12px;
    border: 1px solid var(--border);
}

.stAlert p {
    color: var(--text) !important;
}

iframe {
    border-radius: 12px;
    border: 1px solid var(--border);
}

/* ---------- Inputs (readable in both themes) ---------- */

[data-baseweb="input"] > div,
[data-baseweb="textarea"],
[data-baseweb="select"] > div {
    background: var(--surface) !important;
    border-color: var(--border) !important;
    border-radius: 10px !important;
}

input, textarea {
    color: var(--text) !important;
    -webkit-text-fill-color: var(--text) !important;
}

[data-testid="stNumberInput"] button {
    background: var(--surface) !important;
    color: var(--text) !important;
}

[data-baseweb="popover"] > div,
[data-baseweb="menu"],
ul[role="listbox"] {
    background: var(--surface) !important;
}

[data-baseweb="menu"] li,
[role="option"] {
    background: transparent !important;
    color: var(--text) !important;
}

[role="option"]:hover,
[data-baseweb="menu"] li:hover {
    background: rgba(8, 126, 131, 0.14) !important;
}

/* ---------- Buttons ---------- */

.stButton > button,
button[data-testid^="stBaseButton-secondary"] {
    border-radius: 10px;
    font-weight: 600;
    border: 1px solid var(--border);
    background: var(--surface);
    color: var(--text);
}

.stButton > button:hover {
    border-color: var(--ocean-teal);
    color: var(--teal-text);
}

.stButton > button[kind="primary"],
button[data-testid^="stBaseButton-primary"],
.stFormSubmitButton > button {
    background: var(--ocean-teal);
    color: white;
    border: none;
}

.stButton > button[kind="primary"]:hover,
button[data-testid^="stBaseButton-primary"]:hover {
    background: #06666B;
    color: white;
}

/* ---------- Page header, KPI cards, badges ---------- */

.page-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 16px;
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 4px solid var(--ocean-teal);
    border-radius: 14px;
    padding: 16px 20px;
    margin-bottom: 14px;
}

.ph-eyebrow {
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    color: var(--teal-text);
}

.ph-title {
    font-family: 'Manrope', sans-serif;
    font-size: 24px;
    font-weight: 800;
    color: var(--text);
    margin: 2px 0;
}

.ph-desc {
    color: var(--muted);
    font-size: 13.5px;
    margin: 0;
}

.ph-chips {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    justify-content: flex-end;
}

.badge {
    display: inline-block;
    font-size: 10.5px;
    font-weight: 700;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    padding: 3px 9px;
    border-radius: 999px;
    border: 1px solid transparent;
    white-space: nowrap;
}

.badge-teal  { color: var(--teal-text) !important;  background: rgba(8, 126, 131, 0.12);  border-color: rgba(8, 126, 131, 0.35); }
.badge-amber { color: var(--amber-text) !important; background: rgba(244, 184, 96, 0.16); border-color: rgba(244, 184, 96, 0.45); }
.badge-red   { color: var(--red-text) !important;   background: rgba(217, 69, 58, 0.12);  border-color: rgba(217, 69, 58, 0.40); }
.badge-grey  { color: var(--muted) !important;      background: rgba(96, 119, 130, 0.12); border-color: var(--border); }

.kpi {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px;
    min-height: 105px;
}

.kpi-label {
    color: var(--muted);
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 0.08em;
    text-transform: uppercase;
}

.kpi-value {
    font-family: 'Manrope', sans-serif;
    color: var(--text);
    font-size: 26px;
    font-weight: 800;
    margin-top: 5px;
}

.kpi-sub {
    color: var(--muted);
    font-size: 11px;
    margin-top: 2px;
}

.agent {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px;
    margin-bottom: 9px;
}

.muted {
    color: var(--muted);
    font-size: 12px;
}

.arrow-down {
    text-align: center;
    color: var(--ocean-teal);
    font-size: 20px;
}

/* Dashboard visual cards and circular indicators */
.visual-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 18px;
    min-height: 220px;
}

.gauge-wrap {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 18px 0 10px;
}

.gauge {
    --gauge-value: 50%;
    --gauge-color: #087E83;

    width: 168px;
    height: 168px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;

    background: conic-gradient(
        var(--gauge-color) var(--gauge-value),
        var(--border) 0
    );

    position: relative;
    transition: background 0.4s ease;
    box-shadow: 0 5px 20px rgba(0, 0, 0, 0.07);
}

.gauge::before {
    content: "";
    position: absolute;
    inset: 13px;
    border-radius: 50%;
    background: var(--surface);
    box-shadow: inset 0 2px 8px rgba(0, 0, 0, 0.05);
}

.gauge-inner {
    position: relative;
    z-index: 1;
    text-align: center;
}

.gauge-value {
    font-family: 'Manrope', sans-serif;
    font-size: 32px;
    font-weight: 800;
    color: var(--text);
    line-height: 1.15;
}

.gauge-label {
    font-size: 12px;
    color: var(--muted);
    margin-top: 5px;
}

.visual-title { font-family:'Manrope',sans-serif; font-weight:800; font-size:15px; color:var(--text); }
.visual-sub { font-size:12px; color:var(--muted); }
.status-line { display:flex; justify-content:space-between; gap:12px; padding:10px 0; border-bottom:1px solid var(--border); font-size:13px; }
.status-line:last-child { border-bottom:0; }
"""

_css = CSS_TEMPLATE
for _key, _value in THEME.items():
    _css = _css.replace("__" + _key + "__", _value)

st.markdown("<style>" + _css + "</style>", unsafe_allow_html=True)




# ---------------------------------------------------------
# 4. SESSION STATE AND ORCHESTRATOR
# ---------------------------------------------------------

if "stage" not in st.session_state:
    st.session_state.stage = "EARLY_WARNING"

if "pipeline" not in st.session_state:
    st.session_state.pipeline = None

if "pipeline_stage" not in st.session_state:
    st.session_state.pipeline_stage = None

if "last_map_step" not in st.session_state:
    st.session_state.last_map_step = 5

if "orchestrator" not in st.session_state:
    db = AuditDB()
    st.session_state.orchestrator = OrchestratorAgent(
        audit_db=db
    )


# ---------------------------------------------------------
# 5. UI HELPER FUNCTIONS
# ---------------------------------------------------------

def badge(text, tone="teal"):
    """Small status pill. tone: teal, amber, red or grey."""
    return f'<span class="badge badge-{tone}">{text}</span>'


def tier_tone(tier_text):
    t = str(tier_text).upper()

    if any(k in t for k in ("CRIT", "HIGH", "SEVERE", "RED")):
        return "red"

    if any(k in t for k in ("MED", "MOD", "WARN", "ELEV", "AMBER", "EARLY")):
        return "amber"

    if any(k in t for k in ("LOW", "NORMAL", "GREEN", "SAFE")):
        return "teal"

    return "grey"


def stage_tone(stage_name):
    if stage_name == "NORMAL":
        return "teal"
    if stage_name == "EARLY_WARNING":
        return "amber"
    return "red"


def kpi(col, label, value, sub):

    col.markdown(
        f"""
        <div class="kpi">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div>
        </div>
        """,
        unsafe_allow_html=True
    )
# ---------------------------------------------------------
# AGENT EXECUTION MONITOR
# ---------------------------------------------------------

AGENT_NAMES = {
    "A": "Disruption Sensing",
    "B": "Predictive Risk",
    "C": "Business Impact",
    "D": "Scenario Planning",
}


def get_agent_history():
    result = st.session_state.get("pipeline")

    if isinstance(result, dict):
        history = result.get("execution_history", [])
        if history:
            return history

    orchestrator = st.session_state.get("orchestrator")

    if orchestrator:
        return getattr(orchestrator, "execution_history", [])

    return []

def render_agent_monitor(compact=False):

    history = get_agent_history()

    if not history:
        st.info("No agent execution records available yet.")
        return

    result = st.session_state.get("pipeline", {})

    execution_id = result.get("execution_id", "Not available")
    execution_status = result.get("execution_status", "UNKNOWN")
    duration = result.get("execution_duration_seconds")

    if not compact:
        st.markdown("### Pipeline execution")
    else:
        st.markdown("### Processing status")

    c1, c2, c3 = st.columns(3)

    c1.metric("Agents recorded", len(history))
    c2.metric("Pipeline status", execution_status)

    if isinstance(duration, (int, float)):
        duration_text = (
            "<0.001 sec" if duration == 0
            else f"{duration:.3f} sec"
        )
    else:
        duration_text = "—"

    c3.metric("Execution duration", duration_text)

    if not compact:
        st.caption(f"Execution ID: {execution_id}")

    for item in history:

        agent_id = str(item.get("agent_id", ""))
        agent_name = item.get(
            "agent_name",
            AGENT_NAMES.get(agent_id, f"Agent {agent_id}")
        )

        status = str(item.get("status", "UNKNOWN")).upper()

        raw_summary = item.get("output_summary", {})

        # Convert stored JSON text into structured data
        if isinstance(raw_summary, str):
            try:
                summary = json.loads(raw_summary)
            except (ValueError, TypeError):
                summary = {}
        elif isinstance(raw_summary, dict):
            summary = raw_summary
        else:
            summary = {}

        with st.container(border=True):

            left, right = st.columns([4, 1])

            left.markdown(f"### {agent_name}")

            if status == "COMPLETED":
                right.success("COMPLETED")
            elif status == "RUNNING":
                right.info("RUNNING")
            else:
                right.error(status)

            # Agent A: Disruption Sensing
            if "events_detected" in summary:

                count = summary.get("events_detected", 0)
                st.metric("Disruptions detected", count)

                detected_events = summary.get("events", [])

                if detected_events:
                    st.markdown("**Detected events**")

                    for event in detected_events:
                        severity = str(
                            event.get("severity", "UNKNOWN")
                        ).upper()

                        headline = event.get(
                            "headline",
                            "Disruption detected"
                        )

                        if severity in ("CRITICAL", "HIGH"):
                            st.error(f"{severity} · {headline}")
                        elif severity in ("MEDIUM", "MODERATE"):
                            st.warning(f"{severity} · {headline}")
                        else:
                            st.info(f"{severity} · {headline}")

            # Agent B: Predictive Risk
            elif "risk_score" in summary:

                score = float(summary.get("risk_score", 0))

                r1, r2, r3 = st.columns(3)

                r1.metric("Risk score", f"{score:.1f}/100")
                r2.metric(
                    "Risk category",
                    str(summary.get("risk_tier", "Unknown"))
                )

                breach = summary.get("time_to_breach_minutes")

                r3.metric(
                    "Time to threshold",
                    f"{breach} min" if breach is not None else "—"
                )

                st.progress(max(0.0, min(1.0, score / 100)))

                factors = summary.get("contributing_factors", 0)

                if isinstance(factors, list):
                    factor_count = len(factors)
                else:
                    factor_count = factors

                st.caption(
                    f"Risk assessment based on {factor_count} contributing factors."
                )

            # Agent C: Business Impact
            elif "financial_exposure_usd" in summary:

                r1, r2, r3 = st.columns(3)

                r1.metric(
                    "Financial exposure",
                    f"${float(summary.get('financial_exposure_usd', 0)):,.0f}"
                )

                r2.metric(
                    "Cargo affected",
                    f"{float(summary.get('quantity_affected_kg', 0)):,.0f} kg"
                )

                r3.metric(
                    "Expected delay",
                    f"{summary.get('expected_delay_minutes', 0)} min"
                )

            # Agent D: Recovery Planning
            elif "alternatives_generated" in summary:

                r1, r2 = st.columns(2)

                r1.metric(
                    "Recovery alternatives",
                    summary.get("alternatives_generated", 0)
                )

                r2.metric(
                    "Feasible alternatives",
                    summary.get("feasible_alternatives", 0)
                )

                recommendation = summary.get(
                    "recommended_alternative"
                )

                if recommendation:
                    st.success(
                        f"Recommended recovery plan: {recommendation}"
                    )

            else:
                st.caption(
                    "Agent execution recorded. No structured summary available."
                )

            agent_duration = item.get("duration_seconds")

            if isinstance(agent_duration, (int, float)):
                display_duration = (
                    "<0.001 sec" if agent_duration == 0
                    else f"{agent_duration:.3f} sec"
                )

                st.caption(f"Execution time: {display_duration}")

            if item.get("error"):
                st.error(f"Execution error: {item['error']}")

    if not compact:
        st.caption(
            "Execution records are captured from the actual Python agents. "
            "The current pipeline runs sequentially."
        )



# ---------------------------------------------------------
# 6. SIDEBAR NAVIGATION AND CONTROLS
# ---------------------------------------------------------

WAVE_SVG = """
<svg width="30" height="30" viewBox="0 0 32 32" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="M2 11c3-4 6-4 9 0s6 4 9 0 6-4 10 0" stroke="#7FD6D3" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M2 18c3-4 6-4 9 0s6 4 9 0 6-4 10 0" stroke="#2FB3B0" stroke-width="2.4" stroke-linecap="round"/>
  <path d="M2 25c3-4 6-4 9 0s6 4 9 0 6-4 10 0" stroke="#087E83" stroke-width="2.4" stroke-linecap="round"/>
</svg>
"""

with st.sidebar:

    st.markdown(
        f"""
        <div class="sb-brand">{WAVE_SVG}<span class="sb-wordmark">ORVIX</span></div>
        <div class="sb-tagline">Resilient Seafood Supply Chains</div>
        <div class="sb-slogan">PREDICT EARLY · PLAN RECOVERY · HUMAN IN CONTROL</div>
        """,
        unsafe_allow_html=True
    )

    st.divider()

    st.markdown('<div class="sb-label">APPEARANCE</div>', unsafe_allow_html=True)
    st.radio(
        "Choose theme",
        ["Light", "Dark"],
        horizontal=True,
        key="appearance",
        label_visibility="collapsed"
    )

    st.divider()

    for group_name, group_items in NAV_GROUPS:

        st.markdown(
            f'<div class="nav-group">{group_name}</div>',
            unsafe_allow_html=True
        )

        for item in group_items:

            st.button(
                item,
                key=f"nav_{item}",
                width="stretch",
                type="primary" if st.session_state.selected_page == item else "secondary",
                on_click=go_to,
                args=(item,)
            )

    page = st.session_state.selected_page

    st.divider()

    st.markdown('<div class="sb-label">SCENARIO</div>', unsafe_allow_html=True)

    stage_options = [
        "NORMAL",
        "EARLY_WARNING",
        "CRITICAL_DISRUPTION"
    ]

    st.session_state.stage = st.selectbox(
    "Scenario stage",
    stage_options,
    index=stage_options.index(st.session_state.stage)
)

# ---------------------------------------------------------
# SELECT SHIPMENT FOR ANALYSIS
# ---------------------------------------------------------

shipment_records = ShipmentDB().get_all_shipments()

shipment_lookup = {
    str(item["shipment_id"]): item
    for item in shipment_records
    if item.get("shipment_id")
}

shipment_options = ["DEMO"] + list(shipment_lookup.keys())

if st.session_state.get("active_shipment_id") not in shipment_options:
    st.session_state.active_shipment_id = "DEMO"

selected_shipment_id = st.selectbox(
    "Shipment for analysis",
    options=shipment_options,
    format_func=lambda shipment_id: (
        "Demo shipment (800 kg)"
        if shipment_id == "DEMO"
        else (
            f'{shipment_lookup[shipment_id].get("fish_type", "Unknown")} | '
            f'{shipment_lookup[shipment_id].get("quantity_kg", 0)} kg | '
            f'{shipment_id}'
        )
    ),
    key="active_shipment_id"
)

active_shipment = shipment_lookup.get(selected_shipment_id)

st.divider()


# ---------------------------------------------------------
# 7. COMPACT PAGE HEADER
# ---------------------------------------------------------

current_stage_label = st.session_state.stage

st.markdown(
    f"""
    <div class="page-header">
        <div>
            <div class="ph-eyebrow">ORVIX · {PAGE_GROUP.get(page, "")}</div>
            <div class="ph-title">{page}</div>
            <p class="ph-desc">{PAGE_DESCRIPTIONS.get(page, "")}</p>
        </div>
        <div class="ph-chips">
            {badge(current_stage_label.replace("_", " "), stage_tone(current_stage_label))}
            {badge("Simulated operational data", "grey")}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


# ---------------------------------------------------------
# 8. ROUTE DATA
# ---------------------------------------------------------

route = [
    (12.9141, 74.8560),
    (13.05, 74.82),
    (13.20, 74.79),
    (13.34, 74.7421),
    (13.65, 74.70),
    (14.0434, 74.51)
]

route_places = [
    "Mangaluru coastal dispatch",
    "Mulki corridor",
    "Udupi region",
    "Kundapura region",
    "Bhatkal region",
    "Honnavar distribution approach"
]

step = st.session_state.last_map_step

truck_pos = route[min(step, len(route) - 1)]

truck_place = route_places[min(step, len(route_places) - 1)]


# ---------------------------------------------------------
# 9. AUTOMATIC SCENARIO PIPELINE
# ---------------------------------------------------------

# Run once on first launch and again only when the selected scenario changes.
# Normal page navigation and theme changes do not rerun the calculations.
selected_shipment_qty = (
    float(active_shipment["quantity_kg"])
    if active_shipment
    else 800.0
)

if (
    st.session_state.pipeline is None
    or st.session_state.get("pipeline_stage") != st.session_state.stage
    or st.session_state.get("pipeline_shipment_id") != selected_shipment_id
):

    stage = st.session_state.stage

    if stage == "NORMAL":
        telemetry = SimulationEngine.get_baseline_telemetry()
    elif stage == "EARLY_WARNING":
        telemetry = SimulationEngine.get_early_warning_telemetry()
    else:
        telemetry = SimulationEngine.get_critical_breach_telemetry()

    weather = SimulationEngine.get_weather_scenario(stage)
    flags = {
        "flood_active": stage == "CRITICAL_DISRUPTION",
        "vehicle_unavailable": stage == "CRITICAL_DISRUPTION",
        "storage_unavailable": stage == "CRITICAL_DISRUPTION"
    }

    with st.spinner("Updating shipment outlook..."):
        result = st.session_state.orchestrator.execute_resilience_pipeline(
            telemetry_history=telemetry,
            current_weather=weather,
            vehicle_status={"is_available": stage != "CRITICAL_DISRUPTION"},
            cold_hub_status={"is_available": stage != "CRITICAL_DISRUPTION"},
            buyer_order_status={"requested_qty_kg": selected_shipment_qty},
            manual_scenario_flags=flags,
            missing_data_flags={}
        )

    st.session_state.pipeline = result
          # -----------------------------------------------------
    # LOCAL AI REASONING — OLLAMA / PHI-3
    # -----------------------------------------------------

    with st.spinner("Phi-3 is analysing the shipment outlook..."):

        ai_agents = ORVIXLLMAgents()

        ai_analysis = ai_agents.run(
            pipeline_result=result,
            shipment_context={
                "scenario": stage,
                "latest_telemetry": (
                    telemetry[-1] if telemetry else None
                ),
                "weather": weather,
                "requested_quantity_kg": selected_shipment_qty,
"shipment_id": selected_shipment_id,
"fish_type": (
    active_shipment.get("fish_type")
    if active_shipment
    else "Demo seafood shipment"
),
            }
        )

        result["ai_analysis"] = ai_analysis

    st.session_state.pipeline = result
    st.session_state.pipeline_stage = stage
    st.session_state.pipeline_shipment_id = selected_shipment_id

    st.session_state.telemetry = telemetry
    st.session_state.weather = weather
# ---------------------------------------------------------
# 11. EXTRACT PIPELINE RESULTS
# ---------------------------------------------------------
result = st.session_state.pipeline
risk = result["risk_assessment"]
impact = result["business_impact"]
events = result["detected_events"]
alts = result["recovery_alternatives"]

recommended = result.get("recommended_alternative")

telemetry = st.session_state.telemetry

latest = telemetry[-1]

risk_score = float(risk.overall_risk_score)

tier = risk.risk_tier

stage = st.session_state.stage


# ---------------------------------------------------------
# 10. PAGE ROUTING
# ---------------------------------------------------------

if page == "Manager Dashboard":
    render_manager_dashboard()

elif page == "Register Shipment":
    render_register_shipment(ShipmentDB())

elif page == "Shipment Management":
    render_shipment_management(ShipmentDB())


# ---------------------------------------------------------
# COMMAND CENTRE
# ---------------------------------------------------------

elif page == "Command Centre":
    st.markdown("### Shipment overview")
    cols = st.columns(5)
    kpi(cols[0], "Shipment", "SHP-800", "800 kg · Fresh seafood")
    kpi(cols[1], "Cargo temperature", f"{latest.temperature_c:.1f}°C", "Current simulated sensor reading")
    kpi(cols[2], "Predictive risk", f"{risk_score:.0f}/100", badge(tier, tier_tone(tier)))

    ttb = risk.time_to_breach_envelope_mins
    kpi(cols[3], "Time to 4°C threshold", f"{ttb:.0f} min" if ttb is not None else "Not estimated", "Illustrative project threshold")
    kpi(cols[4], "Workflow", result["workflow_stage"].replace("_", " "), "Human decision controls action")
    st.markdown("---")

    st.markdown("### Processing status")
    status_cols = st.columns(3)

    with status_cols[0]:
        st.success("Disruption sensing completed")

    with status_cols[1]:
        st.success("Risk assessment completed")

    with status_cols[2]:
        st.success("Recovery planning completed")

    st.markdown("---")
    st.markdown("### Operational health")
    gauge_cols = st.columns([1, 1, 1.5])
    risk_color = "#D94B45" if risk_score >= 70 else ("#D69A35" if risk_score >= 40 else "#159B83")
    health_score = max(0, min(100, 100 - risk_score))

    with gauge_cols[0]:
        st.markdown(
            f'<div class="visual-card"><div class="visual-title">Shipment health</div><div class="gauge-wrap"><div class="gauge" style="--gauge-value:{health_score:.1f}%;--gauge-color:#159B83"><div class="gauge-inner"><div class="gauge-value">{health_score:.0f}%</div><div class="gauge-label">Health score</div></div></div></div><div class="visual-sub" style="text-align:center">Higher is better</div></div>',
            unsafe_allow_html=True
        )
    with gauge_cols[1]:
        st.markdown(
            f'<div class="visual-card"><div class="visual-title">Risk level</div><div class="gauge-wrap"><div class="gauge" style="--gauge-value:{max(0,min(100,risk_score)):.1f}%;--gauge-color:{risk_color}"><div class="gauge-inner"><div class="gauge-value">{risk_score:.0f}</div><div class="gauge-label">Out of 100</div></div></div></div><div class="visual-sub" style="text-align:center">{str(tier)}</div></div>',
            unsafe_allow_html=True
        )
    with gauge_cols[2]:
        st.markdown('<div class="visual-card"><div class="visual-title">Shipment temperature trend</div><div class="visual-sub">Recent simulated reefer readings</div>', unsafe_allow_html=True)
        temp_df = pd.DataFrame([
            {"Time": x.timestamp.strftime("%H:%M"), "Temperature (°C)": float(x.temperature_c)}
            for x in telemetry
        ])
        if not temp_df.empty:
            st.line_chart(
    temp_df.set_index("Time"),
    height=230,
    color="#16A6A1",
    width="stretch"
)
        else:
            st.caption("Temperature history is not available for this scenario.")
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown("### Estimated business impact")
    impact_cols = st.columns(4)
    kpi(impact_cols[0], "Financial exposure", f"${impact.total_financial_exposure_usd:,.0f}", "Scenario estimate · not actual loss")
    kpi(impact_cols[1], "Cargo quantity at risk", f"{impact.quantity_affected_kg:,.0f} kg", "Modelled quantity")
    kpi(impact_cols[2], "Expected delay", f"{impact.expected_delay_minutes} min", "Scenario projection")
    kpi(impact_cols[3], "Recovery options", str(len(alts)), f"{sum(1 for x in alts if x.is_feasible)} feasible")

    chart_left, chart_right = st.columns([1.2, 1])
    with chart_left:
        st.markdown("### Exposure breakdown")
        impact_breakdown = pd.DataFrame({
            "Cost category": ["Spoilage", "Delay penalty", "Emergency logistics"],
            "Estimated USD": [
                float(impact.estimated_spoilage_cost_usd),
                float(impact.estimated_sla_penalty_usd),
                float(impact.estimated_additional_logistics_usd)
            ]
        }).set_index("Cost category")
        st.bar_chart(impact_breakdown, height=220)
    with chart_right:
        st.markdown("### Recovery readiness")
        feasible_count = sum(1 for x in alts if x.is_feasible)
        total_count = len(alts)
        readiness = (feasible_count / total_count * 100) if total_count else 0
        st.markdown(
            f'<div class="visual-card"><div class="visual-title">Feasible recovery options</div><div class="gauge-wrap"><div class="gauge" style="--gauge-value:{readiness:.1f}%;--gauge-color:#278FAD"><div class="gauge-inner"><div class="gauge-value">{feasible_count}/{total_count}</div><div class="gauge-label">Options ready</div></div></div></div><div class="status-line"><span>Recommended action</span><b>{recommended.name if recommended else "Needs review"}</b></div><div class="status-line"><span>Decision status</span><b>Human review required</b></div></div>',
            unsafe_allow_html=True
        )

    st.markdown("### Shipment route & truck position")
    left, right = st.columns([1.25, 1])
    with left:
        m = folium.Map(location=[13.45, 74.72], zoom_start=7, tiles="OpenStreetMap")
        folium.PolyLine(route, color="#087E83", weight=5, opacity=0.85, tooltip="Illustrative shipment route").add_to(m)
        folium.Marker(route[0], tooltip="Origin · Coastal dispatch", icon=folium.Icon(color="green", icon="play")).add_to(m)
        folium.Marker(route[-1], tooltip="Destination · Distribution hub", icon=folium.Icon(color="blue", icon="flag")).add_to(m)
        folium.Marker(truck_pos, tooltip="Simulated truck location", popup=f"Demo GPS point {step + 1}/{len(route)}", icon=folium.Icon(color="orange", icon="truck", prefix="fa")).add_to(m)
        if stage == "CRITICAL_DISRUPTION":
            folium.Marker(route[3], tooltip="Simulated disruption", icon=folium.Icon(color="red", icon="warning-sign")).add_to(m)
        st_folium(m, use_container_width=True, height=370, key="command_map")
        loc1, loc2, loc3 = st.columns(3)
        loc1.metric("Current location", truck_place)
        loc2.metric("Latitude", f"{truck_pos[0]:.5f}°")
        loc3.metric("Longitude", f"{truck_pos[1]:.5f}°")
        b1, b2 = st.columns(2)
        if b1.button("← Previous GPS point"):
            st.session_state.last_map_step = max(0, step - 1)
            st.rerun()
        if b2.button("Move truck →"):
            st.session_state.last_map_step = min(len(route) - 1, step + 1)
            st.rerun()
        st.caption("Truck movement and coordinates are simulated, not live vehicle GPS.")

    with right:
        st.markdown("### Latest alerts")

        st.markdown("### Latest alerts")

        if events:
            for event in events[:4]:
                severity = str(event.severity).upper()
                alert_text = f"{severity} · {event.headline}"

                if severity in ("CRITICAL", "HIGH"):
                    st.error(alert_text)
                elif severity in ("MEDIUM", "MODERATE"):
                    st.warning(alert_text)
                else:
                    st.info(alert_text)
        else:
            st.success("No disruption event detected in this scenario.")


    st.caption("Prototype mode: shipment, vehicle, telemetry and business values shown here are simulated. Estimates support demonstration and should not be treated as actual operational measurements.")


# ---------------------------------------------------------
# LIVE SHIPMENT MAP
# ---------------------------------------------------------

elif page == "Live Shipment Map":

    st.info(
        "This is a moving GPS simulation for demonstration. "
        "It does not connect to a real truck tracker."
    )

    gps1, gps2, gps3 = st.columns(3)

    gps1.metric("Current route location", truck_place)

    gps2.metric("Latitude", f"{truck_pos[0]:.5f}°")

    gps3.metric("Longitude", f"{truck_pos[1]:.5f}°")

    st.caption(
        f"Checkpoint {step + 1} of {len(route)} · Coastal Karnataka demonstration corridor"
    )

    m = folium.Map(
        location=[13.45, 74.72],
        zoom_start=7,
        tiles="OpenStreetMap"
    )

    folium.PolyLine(
        route,
        color="#087E83",
        weight=5,
        tooltip="Primary coastal route"
    ).add_to(m)

    for i, point in enumerate(route):

        folium.CircleMarker(
            point,
            radius=5,
            color="#087E83",
            fill=True,
            tooltip=f"Route checkpoint {i + 1}"
        ).add_to(m)

    folium.Marker(
        route[0],
        tooltip="Origin",
        icon=folium.Icon(
            color="green",
            icon="anchor",
            prefix="fa"
        )
    ).add_to(m)

    folium.Marker(
        route[-1],
        tooltip="Destination",
        icon=folium.Icon(
            color="blue",
            icon="flag"
        )
    ).add_to(m)

    folium.Marker(
        truck_pos,
        tooltip="Truck now (simulated)",
        icon=folium.Icon(
            color="orange",
            icon="truck",
            prefix="fa"
        )
    ).add_to(m)

    if stage == "CRITICAL_DISRUPTION":

        folium.Marker(
            route[3],
            tooltip="Flood warning (simulated)",
            icon=folium.Icon(
                color="red",
                icon="warning-sign"
            )
        ).add_to(m)

    st_folium(
        m,
        use_container_width=True,
        height=550,
        key="full_route_map"
    )

    a, b = st.columns(2)

    if a.button(
        "Move truck one checkpoint",
        width="stretch"
    ):

        st.session_state.last_map_step = (
            step + 1
        ) % len(route)

        st.rerun()

    if b.button(
        "Reset truck to origin",
        width="stretch"
    ):

        st.session_state.last_map_step = 0

        st.rerun()

    st.caption(
        "GPS provenance: SIMULATED. In deployment, connect authorised fleet telematics or vehicle GPS APIs."
    )


# ---------------------------------------------------------
# PREDICTIVE RISK
# ---------------------------------------------------------

elif page == "Predictive Risk":

    a, b, c = st.columns(3)

    a.metric(
        "Risk index",
        f"{risk_score:.1f}/100",
        tier,
        delta_color="off"
    )

    b.metric(
        "Temperature",
        f"{latest.temperature_c:.2f}°C",
        latest.compressor_status,
        delta_color="off"
    )

    bval = risk.time_to_breach_envelope_mins

    c.metric(
        "Estimated time to 4°C",
        f"{bval:.0f} min" if bval is not None else "Not available"
    )

    st.progress(
        min(1, max(0, risk_score / 100)),
        text=f"Explainable heuristic risk index · {tier}"
    )

    st.markdown("### Temperature history")

    df = pd.DataFrame([
        {
            "Time": x.timestamp.strftime("%H:%M"),
            "Temperature °C": x.temperature_c
        }
        for x in telemetry
    ])

    try:
        st.line_chart(
            df.set_index("Time"),
            color="#087E83"
        )
    except TypeError:
        # Older Streamlit versions do not support the colour option.
        st.line_chart(
            df.set_index("Time")
        )

    st.markdown("### Contributing signals")

    signals = []

    for factor in risk.contributing_factors:

        signals.append({
            "Factor": factor.factor_name,
            "Signal": factor.current_value_repr,
            "Direction": factor.direction,
            "Weight %": factor.weight_pct,
            "Contribution": factor.score_contribution,
            "Explanation": factor.explanation
        })

    if signals:

        st.dataframe(
            pd.DataFrame(signals),
            width="stretch",
            hide_index=True
        )

    st.markdown("### Preventive recommendation")

    st.info(
        risk.recommended_preventive_action
        or "Continue monitoring and verify data."
    )

    if risk.missing_or_unreliable_signals:

        st.warning(
            "Missing / unreliable: " +
            ", ".join(risk.missing_or_unreliable_signals)
        )

    st.caption(
        "This is the project's weighted heuristic, not a trained or statistically calibrated ML model."
    )


# ---------------------------------------------------------
# IMPACT SCORING
# ---------------------------------------------------------

elif page == "Impact Scoring":

    a, b, c, d = st.columns(4)

    a.metric(
        "Cargo quantity",
        f"{impact.quantity_affected_kg:,.0f} kg"
    )

    b.metric(
        "Estimated spoilage exposure",
        f"${impact.estimated_spoilage_cost_usd:,.0f}"
    )

    c.metric(
        "Delay penalty",
        f"${impact.estimated_sla_penalty_usd:,.0f}"
    )

    d.metric(
        "Emergency logistics",
        f"${impact.estimated_additional_logistics_usd:,.0f}"
    )

    st.metric(
        "Total estimated exposure",
        f"${impact.total_financial_exposure_usd:,.0f}"
    )

    st.markdown("### Impact details")

    st.write({
        "Expected delay minutes": impact.expected_delay_minutes,
        "Deadline breached": impact.deadline_breached,
        "Perishability urgency": impact.perishability_urgency,
        "Unmet demand kg": impact.unmet_demand_kg
    })

    st.warning(
        impact.assumptions_statement +
        " These are simulated estimates, not measured savings or guaranteed losses."
    )


# ---------------------------------------------------------
# RECOVERY SCENARIOS
# ---------------------------------------------------------

elif page == "Recovery Scenarios":

    st.write(
        "Available plans are checked against capacity, route and timing constraints. Infeasible plans are excluded."
    )

    for alt in alts:

        with st.container(border=True):

            head, score = st.columns([4, 1])

            head.markdown(
                f"**{alt.name}**"
            )

            score.metric(
                "Rank score",
                f"{alt.composite_rank_score:.1f}"
            )

            st.write(alt.description)

            a, b, c = st.columns(3)

            a.write(
                f"Vehicle: `{alt.assigned_vehicle_id}` · "
                f"{alt.vehicle_capacity_kg:.0f} kg"
            )

            b.write(
                f"Delay: **{alt.estimated_delay_minutes} min**"
            )

            c.write(
                f"Cost: **${alt.additional_cost_usd:,.0f}**"
            )

            if alt.is_feasible:

                st.success(
                    "FEASIBLE · " +
                    ("RECOMMENDED" if alt.is_recommended else "ALTERNATIVE")
                )

            else:

                st.error(
                    "REJECTED — " +
                    ("; ".join(alt.rejection_reasons)
                     or "Constraint check failed")
                )

            if alt.recommendation_rationale:

                st.caption(
                    alt.recommendation_rationale
                )

    if not alts:

        st.info(
            "No recovery options are available for the selected scenario."
        )


# ---------------------------------------------------------
# HUMAN APPROVAL
# ---------------------------------------------------------

elif page == "Human Approval":

    st.markdown("### Recommended action")

    if recommended:

        st.success(
            f"Recommended: {recommended.name}"
        )

        st.write(recommended.description)

        st.write(
            f"Vehicle capacity: {recommended.vehicle_capacity_kg:.0f} kg · "
            f"Cargo: 800 kg · "
            f"Delay: {recommended.estimated_delay_minutes} min · "
            f"Cost: ${recommended.additional_cost_usd:.0f}"
        )

    else:

        st.warning(
            "No feasible recommended action is available. "
            "Escalate to an authorised human operator."
        )

    st.markdown("### Record decision")

    with st.form("human_decision"):

        operator = st.text_input(
            "Operator name",
            value="Demo Dispatcher"
        )

        role = st.text_input(
            "Role",
            value="Cold-chain fleet controller"
        )

        choice = st.selectbox(
            "Decision",
            ["APPROVED", "REJECTED", "MODIFIED"]
        )

        chosen = st.selectbox(
            "Recovery option",
            options=[a.alt_id for a in alts] or ["NONE"],
            format_func=lambda x: next(
                (a.name for a in alts if a.alt_id == x),
                x
            )
        )

        reason = st.text_area(
            "Reason / notes",
            value="Reviewed simulated risk and recovery constraints."
        )

        submitted = st.form_submit_button(
            "Record human decision",
            type="primary"
        )

    if submitted:

        if not alts:

            st.error(
                "There is no recovery option to submit. Run a disruption scenario first."
            )

        else:

            ok, msg, record = (
                st.session_state.orchestrator.process_human_decision(
                    shipment_id=(
    active_shipment["shipment_id"]
    if active_shipment
    else ShipmentBaseline.SHIPMENT_ID
),
                    decision_type=choice,
                    operator_name=operator,
                    operator_role=role,
                    rationale_notes=reason,
                    selected_alt_id=chosen
                )
            )

            if ok:
                st.success(msg)
            else:
                st.error(msg)

            st.caption(
                "Check the Audit Trail page for the recorded decision."
            )
# ---------------------------------------------------------
# AGENT OPERATIONS
# ---------------------------------------------------------

elif page == "Agent Operations":

    st.markdown("### ORVIX Agent Execution Centre")

    st.write(
        "Monitor the actual execution history of the ORVIX processing agents."
    )


    render_agent_monitor(compact=False)

    st.divider()

    # -----------------------------------------------------
    # PHI-3 AI AGENT EXPLANATIONS
    # -----------------------------------------------------

    st.markdown("### ORVIX AI Intelligence")

    st.caption(
        "Natural-language explanations generated by the five "
        "independent local Phi-3 AI agents."
    )

    ai_analysis = result.get("ai_analysis", {})

    if isinstance(ai_analysis, dict) and ai_analysis:

        ai_agents = ai_analysis.get("agents", [])

        st.caption(
            f"Provider: {ai_analysis.get('provider', 'Local AI')} · "
            f"Model: {ai_analysis.get('model', 'Phi-3')} · "
            f"Completed: {ai_analysis.get('completed_count', 0)}/"
            f"{ai_analysis.get('total_count', 5)}"
        )

        if ai_agents:

            for agent in ai_agents:

                agent_name = agent.get("agent", "Unknown Agent")
                agent_status = str(
                    agent.get("status", "UNKNOWN")
                ).upper()

                explanation = agent.get(
                    "explanation",
                    "No explanation was returned."
                )

                with st.expander(
                    f"{agent_name} · {agent_status}",
                    expanded=True
                ):

                    if agent_status == "LLM_COMPLETED":
                        st.success("Phi-3 explanation generated")
                        st.write(explanation)

                    elif agent_status == "LLM_UNAVAILABLE_FALLBACK":
                        st.warning(
                            "Phi-3 explanation unavailable. "
                            "The deterministic Python results remain unchanged."
                        )
                        st.write(explanation)

                    else:
                        st.info(f"Agent status: {agent_status}")
                        st.write(explanation)

        else:
            st.warning("No individual AI agent explanations were returned.")

    else:
        st.info(
            "AI explanations are not available for this pipeline execution. "
            "Check the Phi-3 execution logs."
        )

    st.divider()

    st.markdown("### Agent responsibilities")


    agent_cols = st.columns(4)

    agent_information = [
        (
            "Agent A · Disruption Sensing",
            "Detects temperature, weather, vehicle and storage disruptions."
        ),
        (
            "Agent B · Predictive Risk",
            "Calculates shipment risk and estimates time to temperature threshold."
        ),
        (
            "Agent C · Business Impact",
            "Estimates financial exposure, cargo impact and delay penalties."
        ),
        (
            "Agent D · Scenario Planning",
            "Creates and ranks shipment recovery alternatives."
        ),
    ]

    for col, (name, description) in zip(agent_cols, agent_information):

        with col:
            with st.container(border=True):
                st.markdown(f"**{name}**")
                st.caption(description)

    st.divider()

    st.markdown("### Agent E · Orchestrator")

    st.info(
        "Agent E coordinates Agents A, B, C and D, "
        "manages the workflow and supports human approval."
    )



# ---------------------------------------------------------
# AUDIT TRAIL
# ---------------------------------------------------------

elif page == "Audit Trail":

    records = (
        st.session_state.orchestrator.audit_db.get_all_records(
            limit=100
        )
    )

    if records:

        rows = []

        for record in records:

            rows.append({
                "Time": record.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "Shipment": record.shipment_id,
                "Decision": record.human_decision,
                "Risk": record.risk_score,
                "Tier": record.risk_tier,
                "Action": record.recommended_action,
                "Operator": record.operator_id,
                "Reason": record.rationale_notes
            })

        st.dataframe(
            pd.DataFrame(rows),
            width="stretch",
            hide_index=True
        )

        with st.expander("View raw latest audit payload"):

            st.code(
                records[0].raw_payload_json or "No payload",
                language="json"
            )

    else:

        st.info(
            "No human decisions recorded yet. Visit Human Approval to create an audit entry."
        )

    st.caption("Decision records are retained for review and operational accountability.")


# ---------------------------------------------------------
# 11. FOOTER
# ---------------------------------------------------------

st.divider()

st.caption(
    f"ORVIX · Resilient Seafood Supply Chains · "
    f"Prototype with simulated operational data · "
    f"{datetime.now().strftime('%d %b %Y %H:%M')}"
)
