import streamlit as st
import pandas as pd
import altair as alt
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

from detecterv5 import predict_future_faults


# ------------------------------------------------------------
# PAGE CONFIG
# ------------------------------------------------------------
st.set_page_config(page_title="Future Fault Prediction Dashboard", layout="wide")
st.title("📡 Future Fault Prediction Dashboard")


# ------------------------------------------------------------
# SECRET HANDLER (Local + Cloud Compatible)
# ------------------------------------------------------------
def get_secret(key):
    if key in st.secrets:
        return st.secrets[key]
    return os.getenv(key)


# ------------------------------------------------------------
# EMAIL FUNCTION (AUTO GROUP EMAIL)
# ------------------------------------------------------------
def send_email_report(df, subject="Future Fault Prediction Report"):

    sender_email = get_secret("EMAIL_USER")
    sender_password = get_secret("EMAIL_PASS")
    receivers_raw = get_secret("EMAIL_GROUP")

    if not sender_email or not sender_password or not receivers_raw:
        st.warning("Email secrets not configured. Skipping email.")
        return False

    receivers = receivers_raw.split(",")

    html_table = df.to_html(index=False)

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = ", ".join(receivers)
    msg["Subject"] = subject
    msg.attach(MIMEText(html_table, "html"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receivers, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print("Email error:", e)
        return False


# ------------------------------------------------------------
# MULTIPLE FILE UPLOAD
# ------------------------------------------------------------
uploaded_files = st.file_uploader(
    "📂 Upload Alarm Log Files (CSV / XLSX)",
    type=["csv", "xlsx"],
    accept_multiple_files=True
)


# ------------------------------------------------------------
# MAIN LOGIC
# ------------------------------------------------------------
if uploaded_files:

    all_dfs = []

    for uploaded_file in uploaded_files:
        try:
            if uploaded_file.name.endswith(".csv"):
                temp_df = pd.read_csv(
                    uploaded_file,
                    engine="python",
                    sep=None,
                    on_bad_lines="skip"
                )
            else:
                temp_df = pd.read_excel(uploaded_file)

            temp_df["Source File"] = uploaded_file.name
            all_dfs.append(temp_df)

        except Exception as e:
            st.error(f"Error reading {uploaded_file.name}")
            st.exception(e)

    if not all_dfs:
        st.warning("No valid files uploaded.")
        st.stop()

    df = pd.concat(all_dfs, ignore_index=True)
    # Remove duplicate columns if exist
    df = df.loc[:, ~df.columns.duplicated()]

    st.success(f"{len(uploaded_files)} file(s) loaded successfully.")
    st.subheader("📄 Combined Alarm Log Preview")
    # st.dataframe(df.head())
    st.dataframe(df)



    # --------------------------------------------------------
    # RUN PREDICTION
    # --------------------------------------------------------
    with st.spinner("🔍 Running prediction..."):
        results = predict_future_faults(df)

    if not results:
        st.warning("No significant future fault risk detected.")
        st.stop()

    results_df = pd.DataFrame(results)


    # --------------------------------------------------------
    # FILTERS
    # --------------------------------------------------------
    st.subheader("🔎 Filters")

    site_filter = st.multiselect(
        "Filter by Site",
        options=sorted(results_df["Site"].unique())
    )

    risk_filter = st.multiselect(
        "Filter by Risk Level",
        options=["HIGH", "MEDIUM", "LOW"],
        default=["HIGH", "MEDIUM", "LOW"]
    )

    filtered_df = results_df.copy()

    if site_filter:
        filtered_df = filtered_df[
            filtered_df["Site"].isin(site_filter)
        ]

    if risk_filter:
        filtered_df = filtered_df[
            filtered_df["Risk Level"].isin(risk_filter)
        ]

    if filtered_df.empty:
        st.warning("No results match selected filters.")
        st.stop()


    # --------------------------------------------------------
    # TABLE OUTPUT
    # --------------------------------------------------------
    st.subheader("📊 Predicted Faults with Recommendations")
    st.dataframe(filtered_df, use_container_width=True)


    # --------------------------------------------------------
    # CHARTS
    # --------------------------------------------------------
    st.divider()

    # Fault Probability Chart
    st.subheader("📊 Fault Probability by Fault Type")

    fault_prob_chart = (
        alt.Chart(filtered_df)
        .mark_bar()
        .encode(
            x=alt.X("Fault:N", sort="-y"),
            y="Probability (%):Q",
            color=alt.Color(
                "Risk Level:N",
                scale=alt.Scale(
                    domain=["LOW", "MEDIUM", "HIGH"],
                    range=["#2ecc71", "#f1c40f", "#e74c3c"]
                )
            ),
            tooltip=["Site", "Location", "Fault", "Probability (%)", "Risk Level"]
        )
        .properties(height=400)
    )

    st.altair_chart(fault_prob_chart, use_container_width=True)


    # Risk Distribution Pie
    st.subheader("🧮 Risk Level Distribution")

    risk_count = (
        filtered_df["Risk Level"]
        .value_counts()
        .reset_index()
    )
    risk_count.columns = ["Risk Level", "Count"]

    risk_pie = (
        alt.Chart(risk_count)
        .mark_arc()
        .encode(
            theta="Count:Q",
            color=alt.Color(
                "Risk Level:N",
                scale=alt.Scale(
                    domain=["LOW", "MEDIUM", "HIGH"],
                    range=["#2ecc71", "#f1c40f", "#e74c3c"]
                )
            ),
            tooltip=["Risk Level", "Count"]
        )
    )

    st.altair_chart(risk_pie, use_container_width=True)


    # Site-wise Risk Count
    st.subheader("📍 Site-wise Risk Count")

    site_risk = (
        filtered_df
        .groupby("Site")
        .size()
        .reset_index(name="Risk Count")
    )

    site_chart = (
        alt.Chart(site_risk)
        .mark_bar()
        .encode(
            x=alt.X("Site:N", sort="-y"),
            y="Risk Count:Q",
            tooltip=["Site", "Risk Count"]
        )
        .properties(height=350)
    )

    st.altair_chart(site_chart, use_container_width=True)


    # --------------------------------------------------------
    # AUTO EMAIL (ONCE PER SESSION)
    # --------------------------------------------------------
    if "email_sent" not in st.session_state:
        st.session_state.email_sent = False

    if not st.session_state.email_sent:
        success = send_email_report(filtered_df)

        if success:
            st.success("📧 Report emailed automatically to group.")
            st.session_state.email_sent = True
        else:
            st.warning("Email not sent (check secrets configuration).")


    # --------------------------------------------------------
    # DOWNLOAD REPORT
    # --------------------------------------------------------
    st.subheader("⬇️ Download Report")

    st.download_button(
        "Download CSV",
        filtered_df.to_csv(index=False).encode("utf-8"),
        "future_fault_report.csv",
        "text/csv"
    )
