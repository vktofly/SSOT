# Task Plan: Improve Dashboard UI

## Goal
Implement the 5 identified AI Operations Dashboard UI improvements to make it an actionable command center demonstrating efficiency without adding headcount.

## Next Step
Wait for user approval to begin Phase 1.

## Current Phase
Phase 1

## Dashboard Redesign Tasks

- [x] **Phase 1: Surface AI Root Cause Analysis**
  - [x] Detach `render_rca_section` from the tabs.
  - [x] Insert `render_rca_section` directly above `render_kpi_cards`.

- [x] **Phase 2: Add Automation / Headcount KPI**
  - [x] Modify `render_kpi_cards`.
  - [x] Inject a new Stat Card ("Manual Hours Saved", "78% Automation Rate", etc.) into the column layout.

- [x] **Phase 3: Actionable At-Risk Partners**
  - [x] Move the At-Risk Partners dataframe to the top of `render_analytics`.
  - [x] Add `selection_mode="single-row"` and `on_select="rerun"` to the dataframe.
  - [x] Apply mock filtering logic on charts based on the selection.

- [x] **Phase 4: Refine Color Palette**
  - [x] Update bar charts in `render_analytics`.
  - [x] Replace defaults with B2B palette (`#1E3A8A`, `#F59E0B`, `#EF4444`).

- [x] **Phase 5: Embed Operations Copilot**
  - [x] Use `st.chat_input` and `st.chat_message` at the bottom of `render_dashboard`.
  - [x] Store messages in `st.session_state` to enable interactive Q&A format.mlit session state.

## Key Questions
1. How should the Copilot chat state be managed? (Using Streamlit session state)

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| Use standard Streamlit `selection_mode` | Built-in and easy to hook up for filtering |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
|       |         |            |
