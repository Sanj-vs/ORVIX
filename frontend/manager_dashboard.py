
import streamlit as st
import pandas as pd

from backend.shipment_db import ShipmentDB
from backend.audit_db import AuditDB


def render_manager_dashboard():
    """Render the ORVIX Manager Dashboard."""

    st.markdown(
        '<div class="section">Manager Dashboard</div>',
        unsafe_allow_html=True,
    )

    st.caption(
        "Supply Chain Monitoring | Risk Intelligence | Decision Management"
    )

    # Load persistent database records
    try:
        shipments = ShipmentDB().get_all_shipments()
        audit_records = AuditDB().get_all_records(limit=500)
    except Exception as exc:
        st.error("Unable to load manager dashboard data.")
        st.code(f"{type(exc).__name__}: {exc}")
        return

    # Read the latest pipeline result from the existing application
    pipeline = st.session_state.get("pipeline")


    # --------------------------------------------------
    # MANAGER DASHBOARD HEADER
    # --------------------------------------------------

    st.markdown("## Management Overview")
    st.caption("Supply chain performance and operational intelligence")

    # --------------------------------------------------
    # SHIPMENT OVERVIEW
    # --------------------------------------------------

    total_shipments = len(shipments)

    total_quantity = sum(
        float(item.get("quantity_kg", 0) or 0)
        for item in shipments
    )

    statuses = [
        str(item.get("status", "")).upper()
        for item in shipments
    ]

    registered = statuses.count("REGISTERED")
    in_transit = statuses.count("IN_TRANSIT")
    delivered = statuses.count("DELIVERED")
    delayed = statuses.count("DELAYED")
    disrupted = statuses.count("DISRUPTED")

    active_shipments = registered + in_transit
    at_risk_shipments = delayed + disrupted

    st.markdown("### Shipment Performance")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Shipments", total_shipments)
    c2.metric("Active Shipments", active_shipments)
    c3.metric("Delivered", delivered)
    c4.metric("At Risk", at_risk_shipments)

    st.markdown("### Shipment Distribution")

    chart_col, quantity_col = st.columns([2, 1])

    with chart_col:
        status_data = pd.DataFrame({
            "Status": ["Registered", "In Transit", "Delivered", "Delayed", "Disrupted"],
            "Shipments": [
                registered,
                in_transit,
                delivered,
                delayed,
                disrupted,
            ],
        })

        status_data = status_data[status_data["Shipments"] > 0]

        if not status_data.empty:
            st.bar_chart(
                status_data.set_index("Status"),
                height=260,
            )
        else:
            st.info("No shipment activity available.")

    with quantity_col:
        st.metric("Total Cargo", f"{total_quantity:,.1f} kg")
        st.metric("Registered", registered)
        st.metric("Delayed", delayed)
        st.metric("Disrupted", disrupted)



    # Create shipment dataframe
        # --------------------------------------------------
    # 2. SHIPMENT RECORDS
    # --------------------------------------------------

    st.markdown("### Shipment Records")

    # Always initialise the dataframe, even when there are no shipments.
    shipment_columns = [
        "Shipment ID",
        "Supplier",
        "Fish Type",
        "Quantity (kg)",
        "Pickup",
        "Destination",
        "Status",
    ]

    shipment_rows = []

    for item in shipments:
        shipment_rows.append({
            "Shipment ID": item.get("shipment_id", ""),
            "Supplier": item.get("supplier_name", ""),
            "Fish Type": item.get("fish_type", ""),
            "Quantity (kg)": item.get("quantity_kg", 0),
            "Pickup": item.get("pickup_location", ""),
            "Destination": item.get("destination", ""),
            "Status": item.get("status", ""),
        })

    shipment_df = pd.DataFrame(
        shipment_rows,
        columns=shipment_columns,
    )

    if not shipment_df.empty:

        search_col, status_col, fish_col = st.columns(3)

        with search_col:
            search_text = st.text_input(
                "Search shipment or supplier",
                placeholder="Enter ID or supplier name",
                key="manager_shipment_search",
            )

        with status_col:
            status_options = ["All"] + sorted(
                shipment_df["Status"].dropna().astype(str).unique().tolist()
            )

            selected_status = st.selectbox(
                "Filter by status",
                status_options,
                key="manager_status_filter",
            )

        with fish_col:
            fish_options = ["All"] + sorted(
                shipment_df["Fish Type"].dropna().astype(str).unique().tolist()
            )

            selected_fish = st.selectbox(
                "Filter by fish type",
                fish_options,
                key="manager_fish_filter",
            )

        filtered_df = shipment_df.copy()

        if search_text:
            search_mask = (
                filtered_df["Shipment ID"].astype(str).str.contains(
                    search_text, case=False, na=False
                )
                |
                filtered_df["Supplier"].astype(str).str.contains(
                    search_text, case=False, na=False
                )
            )

            filtered_df = filtered_df[search_mask]

        if selected_status != "All":
            filtered_df = filtered_df[
                filtered_df["Status"].astype(str) == selected_status
            ]

        if selected_fish != "All":
            filtered_df = filtered_df[
                filtered_df["Fish Type"].astype(str) == selected_fish
            ]

        st.caption(
            f"Showing {len(filtered_df)} of {len(shipment_df)} shipments"
        )

        st.dataframe(
            filtered_df,
            width="stretch",
            hide_index=True,
        )

    else:
        st.info("No shipments have been registered yet.")

    st.divider()


    # --------------------------------------------------
    # CURRENT DISRUPTION MONITORING
    # --------------------------------------------------

    st.markdown("### Operational Alerts")

    if pipeline:
        events = pipeline.get("detected_events", [])

        if events:
            critical = sum(
                1 for event in events
                if str(event.severity).upper() == "CRITICAL"
            )

            medium = sum(
                1 for event in events
                if str(event.severity).upper() == "MEDIUM"
            )

            low = sum(
                1 for event in events
                if str(event.severity).upper() == "LOW"
            )

            a, b, c, d = st.columns(4)
            a.metric("Total Alerts", len(events))
            b.metric("Critical", critical)
            c.metric("Medium", medium)
            d.metric("Low", low)

            for event in events:
                severity = str(event.severity).upper()

                with st.container(border=True):
                    left, right = st.columns([4, 1])

                    left.markdown(f"**{event.headline}**")
                    left.caption(
                        f"{event.event_type} · Source: {event.source}"
                    )

                    if severity == "CRITICAL":
                        right.error(severity)
                    elif severity == "MEDIUM":
                        right.warning(severity)
                    else:
                        right.info(severity)

        else:
            st.success("No active disruptions detected.")
    else:
        st.info("No operational alerts available.")



    # --------------------------------------------------
    # PREDICTIVE RISK OVERVIEW
    # --------------------------------------------------

    st.markdown("### Risk Intelligence")

    if pipeline and pipeline.get("risk_assessment"):

        risk = pipeline["risk_assessment"]
        score = max(0, min(100, float(risk.overall_risk_score)))
        risk_tier = str(risk.risk_tier).upper()

        risk_col, details_col = st.columns([1, 2])

        with risk_col:
            st.markdown("#### Overall Risk")

            st.metric("Risk Score", f"{score:.1f} / 100")

            st.progress(score / 100)

            st.caption(risk_tier)

        with details_col:
            st.markdown("#### Risk Assessment")

            r1, r2 = st.columns(2)

            r1.metric("Risk Level", risk_tier)
            r2.metric(
                "Risk Direction",
                str(risk.direction_of_change or "Not available")
            )

            st.markdown("**Recommended Preventive Action**")

            st.info(
                risk.recommended_preventive_action
                or "No preventive action specified."
            )

        if risk.contributing_factors:
            with st.expander("View contributing risk factors"):
                for factor in risk.contributing_factors:
                    st.markdown(f"**{factor.factor_name}**")
                    st.caption(factor.explanation)

    else:
        st.info("No current risk assessment available.")

    # Historical risk distribution
    risk_counts = {}

    for record in audit_records:
        tier = str(record.risk_tier).upper()
        risk_counts[tier] = risk_counts.get(tier, 0) + 1

    st.markdown("#### Historical Risk Distribution")

    historical_data = pd.DataFrame({
        "Risk Level": ["LOW", "MODERATE", "ELEVATED", "CRITICAL"],
        "Recorded Events": [
            risk_counts.get("LOW", 0),
            risk_counts.get("MODERATE", 0),
            risk_counts.get("ELEVATED", 0),
            risk_counts.get("CRITICAL", 0),
        ],
    })

    st.bar_chart(
        historical_data.set_index("Risk Level"),
        height=220,
    )


    # --------------------------------------------------
    # BUSINESS IMPACT
    # --------------------------------------------------

    st.markdown("### Financial Impact")

    if pipeline and pipeline.get("business_impact"):

        impact = pipeline["business_impact"]

        st.markdown("#### Estimated Business Exposure")

        c1, c2, c3 = st.columns(3)

        c1.metric(
            "Financial Exposure",
            f"${impact.total_financial_exposure_usd:,.2f}"
        )

        c2.metric(
            "Cargo at Risk",
            f"{impact.quantity_affected_kg:,.1f} kg"
        )

        c3.metric(
            "Expected Delay",
            f"{impact.expected_delay_minutes} min"
        )

        st.markdown("#### Cost Breakdown")

        cost_data = pd.DataFrame({
            "Cost Category": [
                "Spoilage",
                "Emergency Logistics",
                "SLA Penalty",
            ],
            "Estimated Cost (USD)": [
                impact.estimated_spoilage_cost_usd,
                impact.estimated_additional_logistics_usd,
                impact.estimated_sla_penalty_usd,
            ],
        })

        st.bar_chart(
            cost_data.set_index("Cost Category"),
            height=240,
        )

        st.caption(impact.assumptions_statement)

    else:
        st.info("No financial impact assessment available.")




    # --------------------------------------------------
    # RECOVERY SCENARIOS
    # --------------------------------------------------

    st.markdown("### Recovery Performance")

    if pipeline:

        alternatives = pipeline.get("recovery_alternatives", [])

        if alternatives:

            feasible = [a for a in alternatives if a.is_feasible]
            infeasible = [a for a in alternatives if not a.is_feasible]

            c1, c2, c3 = st.columns(3)

            c1.metric("Recovery Options", len(alternatives))
            c2.metric("Feasible", len(feasible))
            c3.metric("Not Feasible", len(infeasible))

            st.progress(len(feasible) / len(alternatives))

            recommended = pipeline.get("recommended_alternative")

            if recommended:
                st.markdown("#### Recommended Recovery Plan")

                with st.container(border=True):

                    st.markdown(f"**{recommended.name}**")

                    st.success("Recommended option")

                    st.write(recommended.recommendation_rationale)

                    r1, r2, r3 = st.columns(3)

                    r1.metric(
                        "Estimated Delay",
                        f"{recommended.estimated_delay_minutes} min"
                    )

                    r2.metric(
                        "Additional Cost",
                        f"${recommended.additional_cost_usd:,.2f}"
                    )

                    r3.metric(
                        "Quantity Delivered",
                        f"{recommended.quantity_delivered_kg:,.1f} kg"
                    )

            st.markdown("#### Alternative Recovery Plans")

            for alternative in alternatives:

                with st.expander(
                    f"{alternative.name} — "
                    f"{'Feasible' if alternative.is_feasible else 'Not Feasible'}"
                ):

                    st.write(f"Vehicle: {alternative.assigned_vehicle_id}")

                    st.write(
                        f"Estimated delay: {alternative.estimated_delay_minutes} minutes"
                    )

                    st.write(
                        f"Additional cost: ${alternative.additional_cost_usd:,.2f}"
                    )

                    if alternative.rejection_reasons:
                        st.warning(
                            "Reasons: "
                            + ", ".join(alternative.rejection_reasons)
                        )

            if not feasible:
                st.error(
                    "No feasible recovery option. "
                    "Human intervention is required."
                )

        else:
            st.info("No recovery alternatives available.")

    else:
        st.info("No recovery assessment available.")




    # --------------------------------------------------
    # HUMAN DECISION OVERVIEW
    # --------------------------------------------------

    st.markdown("### Management Decisions")

    decisions = [
        str(record.human_decision or "").upper()
        for record in audit_records
    ]

    approved = decisions.count("APPROVED")
    rejected = decisions.count("REJECTED")
    modified = decisions.count("MODIFIED")

    c1, c2, c3 = st.columns(3)

    c1.metric("Approved", approved)
    c2.metric("Rejected", rejected)
    c3.metric("Modified", modified)

    st.caption("Recorded decisions from the audit database.")

    if st.button("Open Human Approval", type="primary"):
        st.session_state["manager_approval_navigation"] = True
        st.rerun()



    # --------------------------------------------------
    # RECENT AUDIT ACTIVITY
    # --------------------------------------------------

    st.markdown("### Recent Activity")

    if audit_records:

        recent_records = audit_records[:10]

        for record in recent_records:

            decision = str(record.human_decision or "PENDING").upper()

            with st.container(border=True):

                col1, col2, col3 = st.columns([2, 2, 1])

                col1.markdown(f"**{record.shipment_id}**")

                col2.caption(
                    record.timestamp.strftime("%d %b %Y · %H:%M")
                )

                col3.markdown(f"**{decision}**")

                st.caption(
                    f"Risk: {record.risk_tier} · Operator: {record.operator_id}"
                )

    else:
        st.info("No recent activity recorded.")
