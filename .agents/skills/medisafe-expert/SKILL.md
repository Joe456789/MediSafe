name: medisafe-expert
description: Use when the user asks to manage, analyze, or extend the MediSafe medicine safety system, inspect FastAPI endpoints, or run tests.
---
# MediSafe Expert Skill

This skill provides expert knowledge and guidelines on managing the MediSafe application codebase, API endpoints, agent workflows, and test validation.

## Architecture Overview

MediSafe is structured as a multi-agent safety concierge:
1. **FastAPI Server** ([main.py](file:///c:/Users/joe20/OneDrive/桌面/Capstone%20Project/backend/main.py)):
   - Exposes `/api/analyze` for safety reports and `/api/chat` for follow-up AI pharmacist chat.
2. **Coordinator & Translator Agents** ([agent_system.py](file:///c:/Users/joe20/OneDrive/桌面/Capstone%20Project/backend/agents/agent_system.py)):
   - Orchestrates FDA, PubMed, and ClinicalTrials data fetching.
   - Summarizes results in plain-English (or re-translates to Traditional Chinese).
   - Queries the User Profile MCP server for allergy conflicts.
3. **User Profile MCP Server** ([user_profile_mcp.py](file:///c:/Users/joe20/OneDrive/桌面/Capstone%20Project/backend/mcp/user_profile_mcp.py)):
   - Resolves patient medical profiles and allergy records (`Aspirin`, `Penicillin`).

---

## Guidelines for Modifying Code

When extending or maintaining this project, you MUST follow these standards:
- **Input Validation**: Ensure all requests to `/api/analyze` and `/api/chat` validate inputs (e.g. non-empty text, correct MIME types).
- **Allergy Check Integrity**: The allergy triage must block and return `status="requires_triage"` unless the pharmacist overrides via `bypass_triage=True`.
- **Localization**: Keep report formatting in friendly markdown. Ensure Traditional Chinese toggles re-run queries translating the generated reports.
- **Safety Logs**: Never log patient credentials, SSNs, or hardcode API keys inside files.

---

## Verification Procedures

- **Local Evaluation Suite**:
  Run standard evaluation simulations:
  ```bash
  python tests/eval_agent.py
  ```
- **Automated pytest Suite**:
  Validate security boundaries and assertions:
  ```bash
  pytest tests/test_security_pytest.py
  ```
