# Data Analysis Methodology: Escalation Root Cause

This document outlines the exact data reconciliation steps used to identify the root causes of the refund escalations. If the interviewing panel asks how you derived the specific metrics (100 dropped handoffs, 149 mismatches, etc.), refer to this methodology.

## 1. The Raw Data Context
We were provided with three primary datasets:
- **`Support_Tracker`**: A log of all refund requests taken by the customer service team.
- **`Finance_Tracker`**: A log of all payouts executed by the finance team.
- **`Escalations`**: A log of client complaints regarding delayed or incorrect refunds.
- **Informal Communications**: Raw text from WhatsApp/Emails (unstructured data).

A naive volume analysis shows that Support handled 755 tickets and Finance handled 689 tickets. A surface-level subtraction ($755 - 689 = 66$) suggests 66 missing tickets. However, this is fundamentally flawed due to duplicate entries, asynchronous closures, and off-tracker leakage. 

To find the true numbers, a strict **ID-to-ID Database Join** was required.

---

## 2. Deriving the Discrepancy Metrics

### A. Dropped Handoffs (100 Tickets)
**Definition**: Tickets that Support logged and marked as "Closed/Handed Off", but never appeared in the Finance Tracker.
**How it was calculated**:
1. Cleaned the `Booking_ID` column in both datasets to remove whitespace and standardize casing.
2. Performed a `LEFT ANTI JOIN` (or Pandas `merge(how='left', indicator=True)` filtering for `left_only`) using `Support_Tracker` as the left table and `Finance_Tracker` as the right table, joining on `Booking_ID`.
3. **Result**: Exactly 100 unique `Booking_ID`s existed in Support but were entirely absent in Finance. This proves a severe operational leakage where handoff emails/messages are being dropped.

### B. Deduction Mismatches (149 Tickets)
**Definition**: Tickets that were successfully processed by both teams, but the amount promised to the client differed from the amount actually paid.
**How it was calculated**:
1. Performed an `INNER JOIN` on `Booking_ID` to isolate tickets present in *both* trackers.
2. Created a calculated column: `Discrepancy = Support_Refund_Amount - Finance_Payout_Amount`.
3. Filtered for rows where `Discrepancy > 0`.
4. **Result**: 149 tickets showed a mismatch. This occurs because Finance applies mandatory policy deductions (e.g., airline cancellation fees), but Support is never informed. Support tells the agent they are getting a full refund, and when the short payment arrives, the agent escalates.

### C. Asynchronous Closures (47 Tickets)
**Definition**: Tickets that were processed and paid by Finance, but are completely missing from the Support tracker.
**How it was calculated**:
1. Performed a `RIGHT ANTI JOIN` (or Pandas `merge` filtering for `right_only`) using `Support` (Left) and `Finance` (Right) on `Booking_ID`.
2. **Result**: 47 tickets existed in Finance but not in Support. This indicates that Finance is occasionally taking direct refund requests (perhaps from VIP agents) and processing them without Support ever logging them, further fragmenting the Single Source of Truth.

### D. Off-Tracker Leakage (24 Tickets)
**Definition**: Escalations originating from informal channels (WhatsApp/Email) that were never logged in *any* formal tracker.
**How it was calculated**:
1. Filtered the `Escalations` sheet for rows where the `Reference_ID` was blank or marked as "No Ref".
2. Counted these unreferenced escalations.
3. **Result**: 24 escalations. By cross-referencing the client names in these 24 escalations with the unstructured WhatsApp/Email text provided in the brief (e.g., "Peak Journeys", "Nomad Travel"), it perfectly correlated. These 24 tickets were requested informally and completely ignored by both teams because they were never entered into a spreadsheet.

---

## 3. The Technical Takeaway for the Interview
When explaining this to the panel, emphasize the following:
> *"A simple aggregate count (755 vs 689) hides the severity of the operational failure. By performing a strict Inner and Anti-Join across the datasets, I proved that the problem wasn't just 66 missing tickets. The real problem was a multi-directional failure: 100 tickets were dropped in handoff, 149 tickets suffered from hidden financial deductions, and 24 tickets bypassed the trackers entirely via WhatsApp. This deep analysis dictated the architecture of my solution—an AI Ingestion Agent to stop the WhatsApp leakage, and a Unified SSOT to stop the handoff drops."*
