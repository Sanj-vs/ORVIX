"""Shipment Management page for the ORVIX Streamlit application.

This page reads and updates records through the existing ShipmentDB API.
It does not connect to live vehicle tracking or the audit database.
"""

from typing import Any, Dict, List

import pandas as pd
import streamlit as st

from backend.shipment_db import ShipmentDB


ACTIVE_STATUSES = {
    "REGISTERED",
    "ACTIVE",
    "AT_RISK",
    "DELAYED",
    "DISRUPTED",
    "PENDING_APPROVAL",
}
RISK_STATUSES = {"AT_RISK", "DELAYED", "DISRUPTED"}


def _format_datetime(value: Any) -> str:
    """Return a readable date/time without failing on empty legacy values."""
    if not value:
        return "—"
    return str(value).replace("T", " ")[:16]


def _filter_shipments(
    shipments: List[Dict[str, Any]],
    search_text: str,
    selected_status: str,
    selected_fish_type: str,
) -> List[Dict[str, Any]]:
    """Apply the search and filter controls to shipment records."""
    query = search_text.strip().casefold()
    filtered: List[Dict[str, Any]] = []

    for shipment in shipments:
        status = str(shipment.get("status", "")).upper()
        fish_type = str(shipment.get("fish_type", ""))

        if selected_status != "All statuses" and status != selected_status:
            continue
        if selected_fish_type != "All fish types" and fish_type != selected_fish_type:
            continue

        if query:
            searchable_values = (
                shipment.get("shipment_id", ""),
                shipment.get("supplier_name", ""),
                shipment.get("fish_type", ""),
                shipment.get("vehicle_number", ""),
                shipment.get("pickup_location", ""),
                shipment.get("destination", ""),
            )
            if not any(query in str(value).casefold() for value in searchable_values):
                continue

        filtered.append(shipment)

    return filtered


def render_shipment_management(db: ShipmentDB) -> None:
    """Render shipment KPIs, searchable records, details, and status updates."""
    st.markdown(
        '<div class="section">Shipment management</div>',
        unsafe_allow_html=True,
    )
    st.write(
        "Review shipment registrations stored in the ORVIX shipment database. "
        "Search records, inspect shipment details, and update their operational status."
    )
    st.info(
        "This page displays locally registered records. Status updates are saved "
        "to the shipment database; they do not represent live GPS tracking, and "
        "they are not yet written to the separate audit trail."
    )

    try:
        shipments = db.get_all_shipments()
    except Exception as exc:
        st.error("Could not read the shipment database.")
        st.code(f"{type(exc).__name__}: {exc}")
        return

    if not shipments:
        st.warning("No shipments have been registered yet. Use 'Register Shipment' to add the first record.")
        return

    # Dashboard metrics are calculated from the complete stored shipment list.
    status_counts = [str(item.get("status", "")).upper() for item in shipments]
    metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
    metric_col1.metric("Total shipments", len(shipments))
    metric_col2.metric(
        "Active shipments",
        sum(status in ACTIVE_STATUSES for status in status_counts),
    )
    metric_col3.metric(
        "At-risk shipments",
        sum(status in RISK_STATUSES for status in status_counts),
    )
    metric_col4.metric(
        "Completed shipments",
        sum(status == "DELIVERED" for status in status_counts),
    )

    st.divider()
    search_col, status_col, fish_col = st.columns([2, 1, 1])
    with search_col:
        search_text = st.text_input(
            "Search shipments",
            placeholder="Shipment, supplier, route, or vehicle",
            key="orvix_management_search",
        )
    with status_col:
        status_options = ["All statuses"] + sorted(set(status_counts))
        selected_status = st.selectbox(
            "Status",
            options=status_options,
            key="orvix_management_status_filter",
        )
    with fish_col:
        fish_types = sorted(
            {str(item.get("fish_type", "")) for item in shipments if item.get("fish_type")}
        )
        selected_fish_type = st.selectbox(
            "Fish type",
            options=["All fish types"] + fish_types,
            key="orvix_management_fish_filter",
        )

    filtered_shipments = _filter_shipments(
        shipments,
        search_text,
        selected_status,
        selected_fish_type,
    )

    if filtered_shipments:
        st.markdown("### Shipments")
        table_rows = []
        for item in filtered_shipments:
            table_rows.append(
                {
                    "Shipment ID": item.get("shipment_id", ""),
                    "Supplier": item.get("supplier_name", ""),
                    "Fish type": item.get("fish_type", ""),
                    "Quantity (KG)": float(item.get("quantity_kg", 0) or 0),
                    "Pickup": item.get("pickup_location", ""),
                    "Destination": item.get("destination", ""),
                    "Vehicle": item.get("vehicle_number", ""),
                    "Status": item.get("status", ""),
                    "Expected delivery": _format_datetime(item.get("expected_delivery_at")),
                }
            )

        st.dataframe(
            pd.DataFrame(table_rows),
            width="stretch",
            hide_index=True,
        )

        st.divider()
        st.markdown("### Shipment details")
        shipment_ids = [str(item.get("shipment_id", "")) for item in filtered_shipments]
        selected_shipment_id = st.selectbox(
            "Select a shipment",
            options=shipment_ids,
            key="orvix_management_selected_shipment",
        )
        selected_shipment = next(
            item for item in filtered_shipments
            if str(item.get("shipment_id", "")) == selected_shipment_id
        )

        detail_col1, detail_col2, detail_col3 = st.columns(3)
        detail_col1.metric("Shipment ID", selected_shipment.get("shipment_id", "—"))
        detail_col2.metric("Current status", selected_shipment.get("status", "—"))
        detail_col3.metric(
            "Quantity",
            f"{float(selected_shipment.get('quantity_kg', 0) or 0):,.1f} kg",
        )

        left, right = st.columns(2)
        with left:
            st.markdown("**Supplier and cargo**")
            st.write(f"Supplier: {selected_shipment.get('supplier_name', '—')}")
            st.write(f"Contact: {selected_shipment.get('contact_number', '—')}")
            st.write(f"Fish type: {selected_shipment.get('fish_type', '—')}")
            st.write(
                "Initial temperature: "
                f"{selected_shipment.get('initial_temperature_c', '—')} °C"
            )
            st.write(f"Notes: {selected_shipment.get('additional_notes') or '—'}")

        with right:
            st.markdown("**Route and schedule**")
            st.write(f"Pickup: {selected_shipment.get('pickup_location', '—')}")
            st.write(f"Destination: {selected_shipment.get('destination', '—')}")
            st.write(f"Vehicle: {selected_shipment.get('vehicle_number', '—')}")
            st.write(f"Storage: {selected_shipment.get('vehicle_storage_info', '—')}")
            st.write(
                "Expected pickup: "
                f"{_format_datetime(selected_shipment.get('expected_pickup_at'))}"
            )
            st.write(
                "Expected delivery: "
                f"{_format_datetime(selected_shipment.get('expected_delivery_at'))}"
            )

        st.caption(
            "Created: "
            f"{_format_datetime(selected_shipment.get('created_at'))}"
            " · Last updated: "
            f"{_format_datetime(selected_shipment.get('updated_at'))}"
        )

        st.divider()
        st.markdown("### Update operational status")
        st.caption(
            "Choose a status only when the corresponding operational update is known. "
            "This action saves the new status to SQLite."
        )
        current_status = str(selected_shipment.get("status", "REGISTERED")).upper()
        status_options = sorted(ShipmentDB.ALLOWED_STATUSES)
        current_index = status_options.index(current_status) if current_status in status_options else 0

        with st.form("orvix_update_shipment_status_form"):
            new_status = st.selectbox(
                "New status",
                options=status_options,
                index=current_index,
                key="orvix_management_new_status",
            )
            confirm_update = st.checkbox(
                "I confirm this status reflects a known shipment update.",
                key="orvix_management_confirm_status",
            )
            update_clicked = st.form_submit_button(
                "Save status update",
                type="primary",
                width="stretch",
            )

        if update_clicked:
            if not confirm_update:
                st.warning("Please confirm the status update before saving.")
            elif new_status == current_status:
                st.info("The selected status is already the shipment's current status.")
            else:
                try:
                    updated = db.update_status(selected_shipment_id, new_status)
                    if updated:
                        st.success(
                            f"Shipment {selected_shipment_id} status updated to {new_status}."
                        )
                        st.rerun()
                    else:
                        st.error("The shipment was not found. Refresh the page and try again.")
                except Exception as exc:
                    st.error("The shipment status could not be updated.")
                    st.code(f"{type(exc).__name__}: {exc}")
    else:
        st.warning("No shipments match the current search and filters. Clear a filter and try again.")
