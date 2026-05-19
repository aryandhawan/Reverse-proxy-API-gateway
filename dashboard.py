import streamlit as st
import requests
import time
import json

# --- CONFIGURATION ---
st.set_page_config(page_title="Gateway Command Center", layout="wide")
GATEWAY_URL = "http://localhost:8000/v1/chat/completions"

# --- UI HEADER ---
st.title("🚀 AI Gateway Command Center")
st.markdown("Monitor high-availability failovers, latency telemetry, and Redis rate-limiting in real-time.")
st.divider()

# --- LAYOUT ---
col_main, col_telemetry = st.columns([2, 1])

with col_main:
    st.subheader("Terminal")
    
    # Input Controls
    selected_model = st.selectbox("Target Model", ["google/gemma-2-2b-it", "meta-llama/Llama-3-8b-chat-hf"])
    user_prompt = st.text_area("Enter your prompt:", "Explain quantum computing in one sentence.")
    
    col_btn1, col_btn2 = st.columns(2)
    send_request = col_btn1.button("Send Request", type="primary")
    spam_request = col_btn2.button("⚠️ Stress Test (Trigger Rate Limit)")

with col_telemetry:
    st.subheader("Live Telemetry")
    # Placeholders for dynamic metrics
    metric_latency = st.empty()
    metric_provider = st.empty()
    metric_status = st.empty()

# --- INTERACTION LOGIC ---
if send_request:
    payload = {
        "model": selected_model,
        "messages": [{"role": "user", "content": user_prompt}],
        "max_tokens": 200,
        "temperature": 0.7
    }
    
    with st.spinner("Routing through Gateway..."):
        try:
            # Fire HTTP request to your FastAPI Gateway
            response = requests.post(GATEWAY_URL, json=payload)
            
            # Extract Telemetry from the HTTP Headers and JSON Body
            status_code = response.status_code
            
            if status_code == 200:
                data = response.json()
                response_text = data["choices"][0]["message"]["content"]
                
                # Fetch our custom injected telemetry
                latency = data.get("gateway_telemetry", {}).get("latency_ms", "Unknown")
                
                # Update UI Metrics
                metric_latency.metric(label="Overhead Latency", value=f"{latency} ms")
                metric_status.metric(label="HTTP Status", value=f"{status_code} OK")
                
                # Determine provider based on latency (Cheat code for Phase 1 UI)
                # In a real app, you'd pass the provider in the gateway_telemetry JSON
                provider_display = "Google Gemini (Failover)" if float(latency) > 5000 else "Hugging Face (Primary)"
                metric_provider.metric(label="Active Model Engine", value=provider_display)
                
                st.success("Response Received:")
                st.write(response_text)
                
            elif status_code == 429:
                metric_status.metric(label="HTTP Status", value="429 Blocked", delta="-Rate Limit", delta_color="inverse")
                st.error("Redis Rate Limiter Triggered! You are blocked.")
                st.json(response.json())
                
            else:
                st.error(f"Gateway Error: {status_code}")
                st.write(response.text)
                
        except requests.exceptions.ConnectionError:
            st.error("Cannot connect to Gateway. Is FastAPI running on port 8000?")

if spam_request:
    st.warning("Firing 60 rapid requests to trigger Redis...")
    progress_bar = st.progress(0)
    
    blocked = False
    for i in range(60):
        # We send lightweight requests just to bump the Redis counter
        res = requests.post(GATEWAY_URL, json={
            "model": "google/gemma-2-2b-it",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 10,
            "temperature": 0.1
        })
        
        progress_bar.progress((i + 1) / 60)
        
        if res.status_code == 429:
            st.error(f"🛑 Blocked at request #{i+1} by Redis!")
            blocked = True
            break
            
    if not blocked:
        st.success("All 60 requests passed! (Check your rate limit settings)")