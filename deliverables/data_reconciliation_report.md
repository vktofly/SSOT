# Data Reconciliation Report

## Overview
This document provides a technical breakdown of the data reconciliation process used to identify the true root causes of the refund escalations at BharatTrip. 

By running programmatic database joins (using Pandas/SQL logic) across the provided datasets (`Support_Tracker`, `Finance_Tracker`, and unstructured text), we proved that the discrepancy is significantly larger than the surface-level difference in ticket volume.

## Reconciliation Methodology & Findings

### 1. Dropped Handoffs (100 Tickets)
**Methodology:** 
We performed a **Left Anti-Join** using the `Support_Tracker` as the primary table and the `Finance_Tracker` as the secondary table, joining on a cleaned `Booking_ID`. 
**Finding:** 
Exactly 100 tickets were logged by the Support team as "Handed Off" but were entirely missing from the Finance database. This indicates a critical failure in the manual sheet-to-sheet handoff process.

### 2. Financial Deduction Mismatches (149 Tickets)
**Methodology:** 
We performed an **Inner Join** on `Booking_ID` to isolate the tickets that successfully traversed both teams. We then calculated the delta: `(Support Refund Amount) - (Finance Payout Amount)`.
**Finding:** 
149 tickets resulted in a positive delta (a "Short Payment"). Support agents were promising full refunds, but Finance applied mandatory policy deductions (e.g., airline cancellation fees) prior to payout. Because the trackers are siloed, Support was never informed of these deductions, leading directly to client escalations.

### 3. Asynchronous Closures (47 Tickets)
**Methodology:** 
We performed a **Right Anti-Join** (Finance to Support). 
**Finding:** 
47 payouts were processed by Finance that were never logged by Support. This indicates alternative ingestion pathways where Finance processes refunds directly, fragmenting the data trail.

### 4. Off-Tracker WhatsApp Leakage (24 Tickets)
**Methodology:** 
We filtered the `Escalations` dataset for complaints containing no `Reference_ID`. We then cross-referenced the client names associated with these "ghost tickets" against the provided unstructured text (WhatsApp/Email logs).
**Finding:** 
24 escalations perfectly matched informal refund requests that were never logged in *any* spreadsheet. This proves that unstructured, out-of-band communication is a primary driver of lost tickets.

## Architectural Impact
The findings above necessitated a system redesign. The prototype presented in this repository solves these specific failures by:
1. Using an **AI Ingestion Agent** to structure the WhatsApp leakage.
2. Using a **Unified SSOT Database** to completely eliminate the 100 dropped handoffs.
3. Using a **Reconciliation Agent** to auto-draft explanatory emails for the 149 short-payment mismatches before they escalate.

**Enterprise Hardening & Operational Safety:**
To ensure this solution is deployable in a real-world financial environment, we also implemented:
* **Identity Gateway & RBAC:** Dual-role authorization separating Manager and Operator privileges.
* **PII Data Masking:** Dynamic redaction of sensitive identifiers in the UI and during LLM extraction to ensure compliance.
* **Granular Workflow Control:** Added individual ingestion triggers for operators to cherry-pick high-priority escalations instead of relying solely on batch processing.
