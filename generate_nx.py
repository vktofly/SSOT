import matplotlib.pyplot as plt
import networkx as nx

def generate_arch():
    G = nx.DiGraph()
    
    # Add nodes with their labels
    nodes = {
        'Ext': 'Email & WhatsApp',
        'Gate': 'Identity Gateway\n(RBAC)',
        'Inb': 'Webhook Inbox',
        'AI_In': 'AI Ingestion\n(Gemini 3.5)',
        'HITL_In': 'Human Review Grid\n(PII Masked)',
        'DB': 'Unified SSOT DB\n(Global Search)',
        'Recon': 'Reconciliation Engine',
        'AI_Out': 'AI Drafter\n(Gemini 3.5)',
        'HITL_Out': '1-Click Dispatch'
    }
    
    for n, label in nodes.items():
        G.add_node(n, label=label)
        
    edges = [
        ('Ext', 'Gate'),
        ('Gate', 'Inb'),
        ('Inb', 'AI_In'),
        ('AI_In', 'HITL_In'),
        ('HITL_In', 'DB'),
        ('DB', 'Recon'),
        ('Recon', 'AI_Out'),
        ('AI_Out', 'HITL_Out'),
        ('HITL_Out', 'Ext')
    ]
    G.add_edges_from(edges)
    
    pos = {
        'Ext': (0, 1),
        'Gate': (1, 1),
        'Inb': (2, 1),
        'AI_In': (3, 1),
        'HITL_In': (4, 1),
        'DB': (5, 1),
        
        'Recon': (5, 0),
        'AI_Out': (3, 0),
        'HITL_Out': (1, 0)
    }
    
    # Re-route the last edge for visual flow
    G.remove_edge('HITL_Out', 'Ext')
    
    plt.figure(figsize=(16, 8))
    
    labels = nx.get_node_attributes(G, 'label')
    
    # Draw nodes
    nx.draw_networkx_nodes(G, pos, node_size=6000, node_color='#BBDEFB', node_shape='s', edgecolors='#1976D2', linewidths=2)
    
    # Draw edges
    nx.draw_networkx_edges(G, pos, edgelist=G.edges(), width=2, arrowsize=20, edge_color='#757575', connectionstyle='arc3,rad=0.1')
    
    # Custom edge back to Ext
    nx.draw_networkx_edges(G, pos, edgelist=[('HITL_Out', 'Ext')], width=2, arrowsize=20, edge_color='#757575', connectionstyle='arc3,rad=-0.3')
    
    # Draw labels
    nx.draw_networkx_labels(G, pos, labels, font_size=10, font_weight='bold', font_family='sans-serif')
    
    plt.title("Enterprise Multi-Agent Architecture", fontsize=18, fontweight='bold', pad=20)
    plt.axis('off')
    
    plt.tight_layout()
    plt.savefig('deliverables/architecture.png', dpi=300, bbox_inches='tight')
    print("Generated architecture.png")

if __name__ == '__main__':
    generate_arch()
