"""Streamlit pages for ORVIX shipment registration and related views."""

from datetime import datetime, timedelta
from uuid import uuid4

import streamlit as st

from backend.shipment_db import ShipmentDB, ShipmentValidationError


def render_register_shipment(db: ShipmentDB) -> None:
    """Render the shipment registration form and save submissions to SQLite."""
    st.markdown('<div class="section">Register a seafood shipment</div>', unsafe_allow_html=True)
    st.write(
        "Register shipment details so ORVIX can make them available to its "
        "shipment-management workflow. Required fields are marked with *.")
    st.info(
        "Registration stores shipment information only. It does not start a real "
        "vehicle journey, trigger a recovery action, or confirm live tracking.")

    # A stable token prevents a repeated submission from creating a second row.
    if "orvix_shipment_submission_token" not in st.session_state:
        st.session_state.orvix_shipment_submission_token = uuid4().hex

    now = datetime.now().astimezone()
    default_delivery = now + timedelta(hours=6)

    with st.form("orvix_register_shipment_form", clear_on_submit=True):
        st.markdown("#### Supplier information")
        supplier_col, contact_col = st.columns(2)
        supplier_name = supplier_col.text_input("Fisherman / Supplier Name *")
        contact_number = contact_col.text_input(
            "Contact Number *", placeholder="Example: +91 9876543210")

        fish_col, quantity_col, temperature_col = st.columns(3)
        fish_type = fish_col.text_input("Fish Type *", placeholder="Example: Seer fish")
        quantity_kg = quantity_col.number_input(
            "Quantity (KG) *", min_value=0.1, value=1.0, step=0.5)
        initial_temperature_c = temperature_col.number_input(
            "Initial Fish Temperature (°C) *", min_value=-10.0,
            max_value=50.0, value=2.0, step=0.1, format="%.1f")

        st.markdown("#### Route and vehicle information")
        pickup_col, destination_col = st.columns(2)
        pickup_location = pickup_col.text_input("Pickup Location *")
        destination = destination_col.text_input("Destination *")

        vehicle_col, storage_col = st.columns(2)
        vehicle_number = vehicle_col.text_input("Refrigerated Vehicle Number *")
        vehicle_storage_info = storage_col.text_input(
            "Vehicle / Storage Information *",
            placeholder="Example:  refrigerated truck, 2–4°C reefer")

        st.markdown("#### Expected schedule")
        pickup_date_col, pickup_time_col = st.columns(2)
        expected_pickup_date = pickup_date_col.date_input(
            "Expected Pickup Date *", value=now.date(), key="orvix_pickup_date")
        expected_pickup_time = pickup_time_col.time_input(
            "Expected Pickup Time *", value=now.time().replace(second=0, microsecond=0),
            key="orvix_pickup_time")

        delivery_date_col, delivery_time_col = st.columns(2)
        expected_delivery_date = delivery_date_col.date_input(
            "Expected Delivery Date *", value=default_delivery.date(),
            key="orvix_delivery_date")
        expected_delivery_time = delivery_time_col.time_input(
            "Expected Delivery Time *",
            value=default_delivery.time().replace(second=0, microsecond=0),
            key="orvix_delivery_time")

        additional_notes = st.text_area(
            "Additional Notes", placeholder="Optional handling or delivery instructions.")

        submitted = st.form_submit_button(
            "Register Shipment", type="primary", width="stretch")

    if submitted:
        shipment_data = {
            "supplier_name": supplier_name,
            "contact_number": contact_number,
            "fish_type": fish_type,
            "quantity_kg": quantity_kg,
            "pickup_location": pickup_location,
            "destination": destination,
            "vehicle_number": vehicle_number,
            "vehicle_storage_info": vehicle_storage_info,
            "initial_temperature_c": initial_temperature_c,
            "expected_pickup_at": datetime.combine(
                expected_pickup_date, expected_pickup_time).isoformat(),
            "expected_delivery_at": datetime.combine(
                expected_delivery_date, expected_delivery_time).isoformat(),
            "additional_notes": additional_notes,
        }

        try:
            record, was_created = db.create_shipment(
    shipment_data,
    submission_token=st.session_state.orvix_shipment_submission_token
)
        except ShipmentValidationError as exc:
            st.error(str(exc))
        else:
            if was_created:
                st.session_state.orvix_shipment_submission_token = uuid4().hex
                st.success("Shipment registered successfully.")
            else:
                st.info("This shipment was already registered.")