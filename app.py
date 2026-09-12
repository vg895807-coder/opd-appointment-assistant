import streamlit as st
import pandas as pd
import datetime
import random
import os
from google import genai
from google.genai import types

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="OPD Appointment Assistant | Sunrise Hospital",
    page_icon="📅",
    layout="wide"
)

# --- RETRIEVE API KEY ---
# Check environment variable first, then Streamlit secrets
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        api_key = None

if not api_key:
    st.error("Missing GEMINI_API_KEY. Please set it in Streamlit Secrets (App Settings -> Secrets) or as an environment variable.")
    st.stop()

client = genai.Client(api_key=api_key)

# --- LOAD DATA ---
@st.cache_data
def load_doctor_data():
    return pd.read_csv("doctors_directory.csv")

def get_bookings():
    return pd.read_csv("appointments_ledger.csv")

def save_booking(new_entry):
    df = pd.read_csv("appointments_ledger.csv")
    df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
    df.to_csv("appointments_ledger.csv", index=False)

doctors_df = load_doctor_data()

# --- HEADER & OPERATIONAL DISCLAIMER ---
st.title("🏥 Sunrise Multispeciality Hospital")
st.subheader("Automated Outpatient (OPD) Appointment Booking Portal")
st.caption("Educational Prototype for Healthcare Operations Management | Non-Clinical System")

st.info("⚠️ **Notice:** This application is for administrative appointment scheduling. It does not provide medical treatment. For severe chest pain, breathlessness, or trauma, proceed to the Emergency Room or call **+91-98765-00108**.")

# --- TABS FOR WORKFLOW DIVISION ---
tab1, tab2, tab3 = st.tabs(["🩺 1. AI Specialty Finder & Booking", "📋 2. Live OPD Schedule Directory", "📊 3. Hospital Admin Dashboard"])

# --- TAB 1: BOOKING WORKFLOW ---
with tab1:
    st.markdown("### Step 1: Describe Symptoms (Optional AI Routing)")
    symptom_input = st.text_area(
        "Describe patient symptoms to get an automatic department recommendation:",
        placeholder="e.g., Joint pain in both knees while climbing stairs for the past 2 weeks..."
    )
    
    suggested_specialty = None
    if st.button("Find Recommended Specialty"):
        if symptom_input.strip():
            with st.spinner("Analyzing complaint via Gemini Triage Engine..."):
                triage_prompt = f"""
                You are an administrative triage routing assistant for Sunrise Multispeciality Hospital.
                Available Specialties:
                - Cardiology
                - Paediatrics
                - Orthopaedics
                - Obstetrics & Gynaecology
                - Neurology
                
                If the complaint looks like an emergency, return 'EMERGENCY'.
                Otherwise, return strictly the exact department name from the list.
                Patient Complaint: "{symptom_input}"
                """
                resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=triage_prompt,
                    config=types.GenerateContentConfig(temperature=0.0, max_output_tokens=30)
                )
                pred = resp.text.strip()
                if "EMERGENCY" in pred.upper():
                    st.error("🚨 CRITICAL ALERT: The symptoms entered may require IMMEDIATE EMERGENCY ATTENTION. Please rush to our 24/7 Casualty/Emergency Block.")
                else:
                    st.success(f"Recommended Clinical Specialty: **{pred}**")
                    suggested_specialty = pred

    st.markdown("---")
    st.markdown("### Step 2: Patient & Appointment Details")
    
    col_a, col_b = st.columns(2)
    with col_a:
        patient_name = st.text_input("Patient Full Name")
        patient_age = st.number_input("Patient Age", min_value=1, max_value=115, value=30)
        contact_phone = st.text_input("Phone Number", placeholder="+91-98765-XXXXX")

    with col_b:
        specialty_list = list(doctors_df["Specialty"].unique())
        default_index = specialty_list.index(suggested_specialty) if (suggested_specialty and suggested_specialty in specialty_list) else 0
        
        selected_specialty = st.selectbox("Select Medical Specialty", specialty_list, index=default_index)
        
        # Filter doctors based on specialty
        filtered_docs = doctors_df[doctors_df["Specialty"] == selected_specialty]
        doctor_names = filtered_docs["Doctor_Name"].tolist()
        selected_doctor = st.selectbox("Select Consultant Doctor", doctor_names)
        
        doc_details = filtered_docs[filtered_docs["Doctor_Name"] == selected_doctor].iloc[0]
        st.write(f"**Available Days:** {doc_details['Consultation_Days']} | **Consultation Fee:** INR {doc_details['Consultation_Fee']}")
        
        # Slots
        slot_options = [s.strip() for s in doc_details["Available_Slots"].split(",")]
        selected_slot = st.selectbox("Select Preferred Time Slot", slot_options)
        selected_date = st.date_input("Appointment Date", min_value=datetime.date.today(), value=datetime.date.today() + datetime.timedelta(days=1))

    if st.button("Confirm & Book Appointment", type="primary"):
        if not patient_name or not contact_phone:
            st.warning("Please fill in both Patient Name and Phone Number.")
        else:
            new_id = f"SH-2026-{random.randint(1000, 9999)}"
            new_booking = {
                "Booking_ID": new_id,
                "Patient_Name": patient_name,
                "Patient_Age": patient_age,
                "Contact_Phone": contact_phone,
                "Doctor_Name": selected_doctor,
                "Specialty": selected_specialty,
                "Appointment_Date": str(selected_date),
                "Appointment_Slot": selected_slot,
                "Status": "Confirmed"
            }
            save_booking(new_booking)
            st.success(f"🎉 Appointment confirmed successfully! Booking Reference: **{new_id}**")
            
            with st.spinner("Generating official hospital confirmation letter..."):
                booking_summary_prompt = f"""
                Write an official, polite, and concise hospital appointment confirmation slip for:
                - Patient: {patient_name} (Age: {patient_age})
                - Booking ID: {new_id}
                - Doctor: {selected_doctor} ({selected_specialty})
                - Time: {selected_date} at {selected_slot}
                - Room: {doc_details['Room_No']}
                - Fee: INR {doc_details['Consultation_Fee']}
                
                Instruct them to reach 15 min prior to Counter 2 for vital check. Keep it under 100 words.
                """
                summary_resp = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=booking_summary_prompt,
                    config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=300)
                )
                st.markdown("#### Official Appointment Confirmation Slip")
                st.code(summary_resp.text.strip(), language="markdown")

# --- TAB 2: OPD SCHEDULE DIRECTORY ---
with tab2:
    st.markdown("### 👨‍⚕️ Comprehensive Consultant Schedule & Room Directory")
    st.dataframe(doctors_df, use_container_width=True)

# --- TAB 3: ADMIN & ANALYTICS DASHBOARD ---
with tab3:
    st.markdown("### 📈 Hospital Front Desk Operations Overview")
    current_bookings = get_bookings()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Total Bookings Registered", len(current_bookings))
    m2.metric("Active Specialties", doctors_df["Specialty"].nunique())
    m3.metric("On-Duty Specialists", len(doctors_df))
    
    st.markdown("#### Patient Appointment Log")
    st.dataframe(current_bookings, use_container_width=True)
    
    st.markdown("#### Appointment Distribution by Specialty")
    dept_counts = current_bookings["Specialty"].value_counts()
    st.bar_chart(dept_counts)
