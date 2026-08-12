import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import graphviz
import os

# --- 1. METRICS GRAPH ---
def generate_metrics_graph():
    # Set the style to be very modern and enterprise
    sns.set_theme(style="whitegrid")
    plt.rcParams['font.family'] = 'sans-serif'
    
    data = {
        'Failure Type': ['Dropped Handoffs', 'Deduction Mismatches', 'Asynchronous Closures', 'Off-Tracker Leakage'],
        'Ticket Volume': [100, 149, 47, 24],
        'Risk Category': ['High (Complete Loss)', 'High (Customer Escalation)', 'Medium (Delay)', 'Critical (Unlogged)']
    }
    df = pd.DataFrame(data)
    
    # Sort for visual hierarchy
    df = df.sort_values('Ticket Volume', ascending=False)
    
    plt.figure(figsize=(10, 6))
    
    # Create a clean horizontal barplot
    ax = sns.barplot(
        x='Ticket Volume', 
        y='Failure Type', 
        hue='Risk Category', 
        data=df,
        palette=['#D32F2F', '#1976D2', '#F57C00', '#388E3C'], # Enterprise colors
        dodge=False
    )
    
    # Add values to bars
    for container in ax.containers:
        ax.bar_label(container, padding=5, fmt='%d', fontsize=12, fontweight='bold')
        
    plt.title('Operational Failure Modes Driving Escalations', fontsize=16, fontweight='bold', pad=20)
    plt.xlabel('Number of Tickets Impacted', fontsize=12)
    plt.ylabel('')
    
    # Clean up legend
    plt.legend(title='Risk Category', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    
    # Save it
    plt.savefig('deliverables/metrics.png', dpi=300, bbox_inches='tight')
    print("Metrics graph generated at deliverables/metrics.png")

# --- 2. ARCHITECTURE DIAGRAM ---
def generate_architecture_diagram():
    # Use graphviz to map out the new robust architecture
    dot = graphviz.Digraph(comment='Enterprise SSOT Architecture', format='png')
    dot.attr(rankdir='LR', splines='ortho', bgcolor='transparent')
    
    # Style definitions
    dot.attr('node', shape='box', style='filled', fontname='Helvetica', fontsize='10', margin='0.2')
    
    # External Sources
    dot.node('External', 'Informal Channels\n(WhatsApp, Email)', fillcolor='#E3F2FD', color='#1565C0', penwidth='2')
    
    # Identity Gateway (RBAC)
    with dot.subgraph(name='cluster_security') as c:
        c.attr(label='Security Perimeter', style='dashed', color='#757575', fontname='Helvetica', fontsize='12')
        c.node('Gateway', 'Identity Gateway & RBAC\n(Manager / Operator)', fillcolor='#FFF3E0', color='#E65100', penwidth='2')
    
    # Ingestion Flow
    with dot.subgraph(name='cluster_ingestion') as c:
        c.attr(label='Event-Driven Ingestion', style='rounded', color='#1976D2', fontname='Helvetica')
        c.node('Webhook', 'Webhook Inbox Queue', fillcolor='#BBDEFB')
        c.node('AI_Ingest', 'Gemini-3.5-Flash Agent\n(Data Structuring)', fillcolor='#C8E6C9', color='#2E7D32', penwidth='2')
        c.node('Guardrails', 'PII Redaction &\nConfidence Scoring', fillcolor='#FFCDD2', color='#C62828')
        c.node('HITL_Ingest', 'Human Review Grid\n(Approve/Override)', fillcolor='#E1BEE7', color='#6A1B9A')
        
    # Core DB
    dot.node('SSOT', 'Unified SSOT Database\n(Support & Finance)', shape='cylinder', fillcolor='#FFF9C4', color='#FBC02D', penwidth='3')
    
    # Reconciliation Flow
    with dot.subgraph(name='cluster_recon') as c:
        c.attr(label='Automated Reconciliation', style='rounded', color='#1976D2', fontname='Helvetica')
        c.node('Recon_Logic', 'Mismatch Detection\n(Anti-Joins)', fillcolor='#BBDEFB')
        c.node('AI_Recon', 'Gemini-3.5-Flash Agent\n(Email Drafting)', fillcolor='#C8E6C9', color='#2E7D32', penwidth='2')
        c.node('HITL_Recon', 'Human Approval\n(1-Click Dispatch)', fillcolor='#E1BEE7', color='#6A1B9A')
        
    # Audit Logs
    dot.node('Audit', 'Immutable Audit Logs\n(CSV Export)', shape='note', fillcolor='#F5F5F5', color='#9E9E9E')
    
    # Edges
    dot.edge('External', 'Gateway', ' Raw text')
    dot.edge('Gateway', 'Webhook', ' Authenticated')
    dot.edge('Webhook', 'AI_Ingest', ' Batch / Single')
    dot.edge('AI_Ingest', 'Guardrails')
    dot.edge('Guardrails', 'HITL_Ingest', ' Safe Data')
    dot.edge('HITL_Ingest', 'SSOT', ' Commit')
    
    dot.edge('SSOT', 'Recon_Logic', ' Scheduled / Live')
    dot.edge('Recon_Logic', 'AI_Recon', ' Anomalies')
    dot.edge('AI_Recon', 'HITL_Recon', ' Drafts')
    dot.edge('HITL_Recon', 'External', ' Resolution emails')
    
    dot.edge('HITL_Ingest', 'Audit', ' Logs')
    dot.edge('HITL_Recon', 'Audit', ' Logs')
    
    dot.render('deliverables/architecture', cleanup=True)
    print("Architecture diagram generated at deliverables/architecture.png")

if __name__ == '__main__':
    generate_metrics_graph()
    generate_architecture_diagram()
