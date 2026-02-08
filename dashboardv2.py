import streamlit as st
import pandas as pd
from detecterv5 import predict_future_faults
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import altair as alt

st.set_page_config(page_title="Future Fault Prediction Dashboard", layout="wide")
st.title("Future Fault Prediction Dashboard")

uploaded_file = st.file_uploader(
    "📂 Upload Alarm Log File (CSV / XLSX)",
    type=["csv", "xlsx"]
)

# ================= EMAIL =================
def send_email_report(df, receiver_email):
    sender_email = "your_email@gmail.com"
    sender_password = "APP_PASSWORD"

    body = "Future Fault Prediction Report\n\n"

    for _, row in df.iterrows():
        body += (
            f"Site          : {row['Site']}\n"
            f"Location      : {row['Location']}\n"
            f"Fault         : {row['Fault']}\n"
            f"Probability   : {row['Probability (%)']}%\n"
            f"Risk Level    : {row['Risk Level']}\n"
            f"Cause         : {row['Possible Cause']}\n"
            f"Recommendation: {row['Recommendation']}\n"
            f"Team          : {row['Team']}\n"
            "----------------------------------------\n"
        )

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = receiver_email
    msg["Subject"] = "Future Fault Prediction Report"
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=20) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(msg)

# ================= MAIN =================
if uploaded_file:
    try:
        df = (
            pd.read_csv(uploaded_file, engine="python", sep=None, on_bad_lines="skip")
            if uploaded_file.name.endswith(".csv")
            else pd.read_excel(uploaded_file)
        )

        with st.spinner("Running prediction..."):
            results = predict_future_faults(df)

        if not results:
            st.warning("No significant future fault risk detected.")
            st.stop()

        results_df = pd.DataFrame(results)

        # -------------------------------------
        # FILTERS
        # -------------------------------------
        st.subheader("🔍 Filters")

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
            st.warning("No results match the selected filters.")
            st.stop()

        # -------------------------------------
        # TABLE
        # -------------------------------------
        st.subheader("📊 Predicted Faults with Recommendations")
        st.dataframe(filtered_df, use_container_width=True)

        # ================= CHART =================
        st.divider()
        st.subheader("📊 Fault Probability by Fault Type")
        if not filtered_df.empty:
            fault_prob_chart = (
                alt.Chart(filtered_df)
                .mark_bar()
                .encode(
                    x=alt.X(
                        "Fault:N",
                        sort="-y",
                        title="Fault Type"
                    ),
                    y=alt.Y(
                        "Probability (%):Q",
                        title="Probability (%)"
                    ),
                    color=alt.Color(
                        "Risk Level:N",
                        scale=alt.Scale(
                            domain=["LOW", "MEDIUM", "HIGH"],
                            range=["#2ecc71", "#f1c40f", "#e74c3c"]
                        )
                    ),
                    tooltip=[
                        "Site",
                        "Location",
                        "Fault",
                        "Probability (%)",
                        "Risk Level"
                    ]
                )
                .properties(height=400)
            )

            st.altair_chart(fault_prob_chart, use_container_width=True)

        st.subheader("🧮 Risk Level Distribution")
        if not filtered_df.empty:
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


        st.subheader("📍 Site-wise Risk Count")
        if not filtered_df.empty:
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
                    y=alt.Y("Risk Count:Q"),
                    tooltip=["Site", "Risk Count"]
                )
                .properties(height=350)
            )

            st.altair_chart(site_chart, use_container_width=True)

        # ================= EMAIL =================
        st.subheader("📧 Email Report")
        email = st.text_input("Recipient Email")

        if st.button("Send Email"):
            if not email or "@" not in email:
                st.error("Please enter a valid email address.")
            else:
                send_email_report(filtered_df, email)
                st.success("Email sent successfully")

        # ================= DOWNLOAD =================
        st.subheader("⬇️ Download Report")
        st.download_button(
            "Download CSV",
            filtered_df.to_csv(index=False).encode("utf-8"),
            "future_fault_report.csv",
            "text/csv"
        )

    except Exception as e:
        st.error("Error processing file")
        st.exception(e)
