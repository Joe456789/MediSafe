# Local Project Context & Secure Coding Standards

This file defines the paved roads and coding guidelines for the **MediSafe** project. All agents editing or running code in this project must adhere to these policies.

## Core Paved Roads

We systematically address common vulnerability classes by guiding all agent workflows to use pre-configured, secure-by-default helper patterns instead of writing raw, unverified implementation logic from scratch.

1. **Tool Input Validation**: Every agent tool or API endpoint must validate incoming parameters against strict Pydantic schemas rather than parsing raw dictionaries or strings.
2. **No Shell Execution**: Never execute raw shell commands or use `run_command` in a way that executes arbitrary user input. All terminal commands must be pre-approved or verified.
3. **Pre-Commit Remediation Loop**: If a git commit fails due to a pre-commit hook error (such as a Semgrep scan finding a hardcoded credential), treat the violation as a refactoring task, apply targeted fixes, run tests to verify no regressions, and attempt to commit again.

---

## TDD Planning Gate

During the **Plan** phase, you must decompose the workspace task into logical, modular stages. Every implementation plan MUST include a dedicated **Security Boundaries & Assertions** section outlining specific edge cases that could exploit the feature.

Specifically, when implementing new tools or endpoints:
- Document how input parameters are validated and sanitized.
- Specify how unauthorized actions are blocked (e.g. check MCP allergies or profile settings).
- Write corresponding tests in `tests/` to verify these boundaries before declaring execution complete.
