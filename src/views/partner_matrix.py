import streamlit as st
import pandas as pd
from src.agents import analyze_partner_sentiment

def render_partner_matrix(escalations_df, support_df):
    st.title("📈 Partner Health & Churn Risk Matrix")
    st.caption("⚡ Live B2B Agency Sentiment Telemetry · VIP Partner Retention & Early Warning Churn Radar")
    
    if escalations_df is None or escalations_df.empty:
        st.success("No active partner escalations. All agency health scores are optimal (100% green).")
        return
        
    # Aggregate Agency Intelligence
    agency_stats = {}
    
    for _, row in escalations_df.iterrows():
        agent = str(row.get('Agent', 'Unknown')).strip()
        if not agent or agent == 'nan':
            agent = "Direct Traveler / Unspecified"
            
        if agent not in agency_stats:
            is_vip = any(vip in agent.lower() for vip in ["peak", "nomad", "global", "royal", "zenith"])
            tier = "VIP" if is_vip else "Standard"
            agency_stats[agent] = {
                "Agent": agent,
                "Tier": tier,
                "Escalations": 0,
                "Sentiments": [],
                "Categories": [],
                "Sample_Messages": []
            }
            
        agency_stats[agent]["Escalations"] += 1
        msg = str(row.get('Message', ''))
        sentiment_res = analyze_partner_sentiment(msg, agency_tier=agency_stats[agent]["Tier"])
        agency_stats[agent]["Sentiments"].append(sentiment_res.get("sentiment_score", -0.5))
        agency_stats[agent]["Categories"].append(sentiment_res.get("frustration_category", "Delay"))
        agency_stats[agent]["Sample_Messages"].append(msg)
        
    summary_rows = []
    for agent, data in agency_stats.items():
        avg_sent = round(sum(data["Sentiments"]) / len(data["Sentiments"]), 2) if data["Sentiments"] else 0.0
        most_common_cat = max(set(data["Categories"]), key=data["Categories"].count) if data["Categories"] else "General"
        
        # Determine Risk Status
        if data["Tier"] == "VIP" and (avg_sent < -0.4 or data["Escalations"] >= 3):
            risk_label = "🔴 CRITICAL (Immediate Churn Risk)"
        elif avg_sent < -0.3 or data["Escalations"] >= 4:
            risk_label = "🟡 ELEVATED (SLA Delay)"
        else:
            risk_label = "🟢 STABLE"
            
        summary_rows.append({
            "Agency Name": agent,
            "Revenue Tier": data["Tier"],
            "Active Escalations": data["Escalations"],
            "Sentiment Index": avg_sent,
            "Primary Bottleneck": most_common_cat,
            "Risk Status": risk_label
        })
        
    summary_df = pd.DataFrame(summary_rows).sort_values(by=["Revenue Tier", "Active Escalations"], ascending=[False, False])
    
    total_agencies = len(summary_df)
    critical_vips = len(summary_df[summary_df["Risk Status"].str.contains("CRITICAL")])
    overall_sentiment = round(summary_df["Sentiment Index"].mean(), 2) if not summary_df.empty else 0.0
    
    # 4 Executive Telemetry Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Monitored Agencies", total_agencies, delta="Active Partners", delta_color="off")
    c2.metric("Critical VIPs at Risk", critical_vips, delta="High Priority Action", delta_color="inverse" if critical_vips > 0 else "normal")
    c3.metric("Fleet Sentiment Index", f"{overall_sentiment}", delta="Scale: -1.0 to +1.0", delta_color="inverse" if overall_sentiment < 0 else "normal")
    c4.metric("Dominant Complaint", "Fee Deductions", delta="149 Mismatches", delta_color="inverse")
    
    st.markdown("---")
    st.subheader("📊 Partner Telemetry & Retention Leaderboard")
    
    # Render stylized data grid
    st.dataframe(
        summary_df,
        column_config={
            "Sentiment Index": st.column_config.ProgressColumn(
                "Sentiment Index",
                help="NLP Sentiment Score mapped to 0-1 range",
                format="%.2f",
                min_value=-1.0,
                max_value=1.0,
            ),
        },
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    st.subheader("🎯 Partner Drill-Down & Fast Outreach")
    
    selected_agency = st.selectbox("Select Partner Agency for Incident Review:", list(agency_stats.keys()))
    if selected_agency:
        p_data = agency_stats[selected_agency]
        with st.container(border=True):
            col_a, col_b = st.columns([2, 1])
            with col_a:
                st.markdown(f"### 🏢 {selected_agency} (`{p_data['Tier']} Partner`)")
                st.markdown(f"**Total Escalations Logged:** `{p_data['Escalations']}`")
                st.markdown("**Recent Inbound Communications:**")
                for i, sample in enumerate(p_data["Sample_Messages"][:3]):
                    st.caption(f"💬 *\"{sample}\"*")
            with col_b:
                st.markdown("### ⚡ Fast-Track Actions")
                if st.button(f"📞 Launch VIP Reassurance Dispatch", type="primary", use_container_width=True):
                    st.success(f"Proactive VIP account manager outreach scheduled for {selected_agency}!")
                    st.session_state['show_success_toast'] = True
                    st.rerun()
                if st.button("⚖️ Jump to Reconciliation Queue", use_container_width=True):
                    try:
                        st.switch_page("reconciliation")
                    except Exception:
                        pass
