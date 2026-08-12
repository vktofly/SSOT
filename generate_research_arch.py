import matplotlib.pyplot as plt
import matplotlib.patches as patches

def generate_research_arch():
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.axis('off')

    # Styling for research-grade (Grayscale / Minimal)
    bg_color = '#F8F9FA'
    box_color = '#FFFFFF'
    edge_color = '#212529'
    text_color = '#212529'
    font_family = 'sans-serif'
    
    def draw_layer_box(x, y, w, h, title):
        # Background for the layer
        ax.add_patch(patches.Rectangle((x, y), w, h, fill=True, facecolor=bg_color, edgecolor=edge_color, lw=1, linestyle='--'))
        ax.text(x + 2, y + h - 3, title, ha='left', va='center', fontsize=12, fontweight='bold', color=edge_color, family=font_family)

    def draw_box(x, y, w, h, text, is_agent=False):
        lw = 2 if is_agent else 1.5
        ax.add_patch(patches.Rectangle((x, y), w, h, fill=True, facecolor=box_color, edgecolor=edge_color, lw=lw))
        ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=10, color=text_color, family=font_family)

    def draw_arrow(x1, y1, x2, y2, label=None):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle='->', lw=1.5, color=edge_color))
        if label:
            # Midpoint for label
            mx = (x1 + x2) / 2
            my = (y1 + y2) / 2
            ax.text(mx, my + 1.5, label, ha='center', va='center', fontsize=8, family=font_family, bbox=dict(facecolor='white', edgecolor='none', alpha=0.8, pad=0.5))

    # --- DRAW LAYERS ---
    # Layer 1: Interfaces (Top)
    draw_layer_box(5, 75, 90, 20, "Layer 1: Interfaces & Access Control")
    
    # Layer 2: Processing (Middle)
    draw_layer_box(5, 40, 90, 30, "Layer 2: Multi-Agent Processing Core")
    
    # Layer 3: Persistence (Bottom)
    draw_layer_box(5, 5, 90, 30, "Layer 3: Data Persistence & Governance")


    # --- DRAW COMPONENTS ---
    # Layer 1
    draw_box(10, 80, 20, 10, "External Channels\n(WhatsApp / Email)")
    draw_box(40, 80, 20, 10, "Identity Gateway\n(RBAC Auth)")
    draw_box(70, 80, 20, 10, "Internal Operations\n(Web Dashboard)")

    # Layer 2
    draw_box(10, 55, 20, 10, "Webhook Inbox\n(Event Queue)")
    draw_box(40, 55, 20, 10, "Ingestion Agent\n(Gemini LLM)", is_agent=True)
    draw_box(70, 55, 20, 10, "Reconciliation Agent\n(Anomaly Detection)", is_agent=True)
    draw_box(40, 42, 20, 10, "Data Guardrails\n(PII Masking)")

    # Layer 3
    draw_box(25, 10, 20, 20, "Human-In-The-Loop\n(HITL Review Grid)")
    draw_box(55, 10, 20, 20, "SSOT Database\n(Unified Records)")


    # --- DRAW ARROWS ---
    # Layer 1 to 2
    draw_arrow(20, 80, 20, 65, "Raw Text")
    draw_arrow(50, 80, 50, 65, "Auth Validated")
    
    # Layer 2 Internal
    draw_arrow(30, 60, 40, 60, "Batch")
    draw_arrow(50, 55, 50, 52, "Extracted Entities")
    draw_arrow(60, 60, 70, 60, "Validation Trigger")

    # Layer 2 to 3
    draw_arrow(50, 42, 35, 30, "Safe Data")
    draw_arrow(35, 20, 55, 20, "Operator Approval")
    draw_arrow(65, 30, 80, 55, "Query Results")

    plt.title("Fig 1: Proposed System Architecture for Multi-Agent Data Reconciliation", fontsize=14, fontweight='bold', family=font_family, pad=10)
    plt.tight_layout()
    plt.savefig('deliverables/architecture.png', dpi=300, bbox_inches='tight')
    print("Research-grade architecture diagram generated.")

if __name__ == '__main__':
    generate_research_arch()
