import time
from dotenv import load_dotenv
import altair as alt
import streamlit as st
import requests
import pandas as pd
import psycopg2

# --- CONFIGURATION ---
st.set_page_config(page_title="Gateway Command Center", page_icon="📡", layout="wide")
GATEWAY_URL = "http://localhost:8000/v1/chat/completions"
load_dotenv()
from app.core import db as db_module
DB_URL = db_module.DATABASE_URL

st.title("📡 AI Gateway Infrastructure")
st.markdown("Monitor high-availability failovers, latency metrics, and edge-security in real-time.")

tab_console, tab_analytics = st.tabs(["💻 Interactive Console", "📊 Telemetry Analytics"])

with tab_console:
    col_main, col_telemetry = st.columns([2, 1])

    with col_main:
        with st.container(border=True):
            st.subheader("Send Request")
            
            selected_model = st.selectbox(
                "Target Model",
                [
                    "llama-3.1-8b-instant", 
                    "llama-3.3-70b-versatile", 
                    "openai/gpt-oss-120b",
                    "openai/gpt-oss-20b"
                ]
            )
            user_prompt = st.text_area("System Prompt:", "Explain quantum computing in one sentence.")
            
            # 🔥 THE FIX: Actually creating the UI toggle so the variable exists!
            simulate_crash = st.toggle("💥 Simulate Primary Provider Crash (Chaos Mode)")
            
            col_btn1, col_btn2 = st.columns(2)
            send_request = col_btn1.button("Send Request", type="primary", use_container_width=True)
            spam_request = col_btn2.button("⚠️ Stress Test (Trigger Rate Limit)", use_container_width=True)

    with col_telemetry:
        with st.container(border=True):
            st.subheader("Live Request Metrics")
            metric_latency = st.empty()
            metric_provider = st.empty()
            metric_status = st.empty()

    # --- Interaction Logic: Normal Request ---
    if send_request:
        # The payload now successfully grabs the state (True/False) from the toggle above
        payload = {
            "model": selected_model, 
            "messages": [{"role": "user", "content": user_prompt}], 
            "temperature": 0.7,
            "simulate_crash": simulate_crash 
        } 
        
        with st.spinner("Routing through Gateway..."):
            try:
                response = requests.post(GATEWAY_URL, json=payload)
                status_code = response.status_code
                
                if status_code == 200:
                    data = response.json()
                    latency = data.get("gateway_telemetry", {}).get("latency_ms", "Unknown")
                    
                    metric_latency.metric("Overhead Latency", f"{latency} ms")
                    metric_status.metric("HTTP Status", f"{status_code} OK")
                    metric_provider.metric("Active Model Engine", "Groq" if float(latency) < 4000 and not simulate_crash else "Google Gemini (Failover)")
                    
                    st.success("Response Received:")
                    st.info(data["choices"][0]["message"]["content"])
                elif status_code == 429:
                    metric_status.metric("HTTP Status", "429 Blocked", delta="-Rate Limit", delta_color="inverse")
                    st.error("🛑 Redis Rate Limiter Triggered! You are blocked.")
                else:
                    st.error(f"Gateway Error: {status_code}")
            except requests.exceptions.ConnectionError:
                st.error("Cannot connect to Gateway. Ensure FastAPI is running on port 8000.")

    # --- Interaction Logic: Stress Test ---
    if spam_request:
        st.warning("Firing 10 rapid requests to trigger Redis...")
        progress_bar = st.progress(0)
        
        blocked = False
        for i in range(10):
            try:
                res = requests.post(GATEWAY_URL, json={
                    "model": selected_model,
                    "messages": [{"role": "user", "content": "ping"}],
                    "max_tokens": 10,
                    "temperature": 0.1
                })
                
                # Update progress bar
                progress_bar.progress((i + 1) / 10)
                
                if res.status_code == 429:
                    metric_status.metric("HTTP Status", "429 Blocked", delta="-Rate Limit", delta_color="inverse")
                    st.error(f"🛑 Blocked at request #{i+1} by Redis Rate Limiter!")
                    blocked = True
                    break
                    
            except requests.exceptions.ConnectionError:
                st.error("Connection failed during stress test.")
                break
                
        if not blocked:
            st.success("All requests passed! (Check your rate limit settings in routes.py)")


# ==========================================
# TAB 2: Professional Analytics Graphs
# ==========================================
with tab_analytics:
    st.subheader("Global Execution Telemetry")
    st.caption("Live data pulled directly from PostgreSQL.")
    
    if st.button("🔄 Refresh Database Data"):
        pass # Streamlit reruns the script on button click automatically

    try:
        # Connect to DB and fetch the last 100 requests
        conn = psycopg2.connect(DB_URL)
        query = "SELECT * FROM telemetry_logs ORDER BY created_at DESC LIMIT 100"
        df = pd.read_sql(query, conn)
        conn.close()

        if not df.empty:
            # 1. Top Row Metrics
            kpi1, kpi2, kpi3 = st.columns(3)
            avg_latency = round(df['latency_ms'].mean(), 2)
            failover_rate = round((len(df[df['routed_provider'] == 'gemini']) / len(df)) * 100, 1)
            
            kpi1.metric("Avg Latency (Last 100)", f"{avg_latency} ms")
            kpi2.metric("Circuit Breaker Tripped", f"{failover_rate}% of requests")
            kpi3.metric("Total Logged Requests", len(df))

            st.divider()

            # 2. Charts
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                st.markdown("**Latency Time-Series (ms)**")
                # Reverse dataframe so time flows left to right
                df_chart = df.iloc[::-1].reset_index(drop=True)
                st.line_chart(df_chart['latency_ms'], use_container_width=True)

            with chart_col2:
                st.markdown("**Model Routing Distribution**")
                provider_counts = df['routed_provider'].value_counts().reset_index()
                provider_counts.columns = ["provider", "count"]
                routing_chart = alt.Chart(provider_counts).mark_bar().encode(
                    x=alt.X("provider:N", axis=alt.Axis(labelAngle=0)),
                    y="count:Q"
                )
                st.altair_chart(routing_chart, use_container_width=True)
                
            # 3. Raw Data Table
            with st.expander("View Raw Database Audit Logs"):
                st.dataframe(df[['created_at', 'primary_provider', 'routed_provider', 'latency_ms', 'status_code']], use_container_width=True)
        else:
            st.info("No telemetry logs found in the database yet. Send some requests from the Command Center!")

    except Exception as e:
        st.error(f"Could not connect to PostgreSQL Database. Ensure Docker is running. Error: {e}")