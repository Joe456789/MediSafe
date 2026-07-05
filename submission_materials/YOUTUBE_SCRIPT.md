# YouTube Demo Video Script: MediSafe (Max 5 Mins)

**Video Title**: MediSafe - Plain-English Medicine Safety Guardian (Kaggle Capstone Pitch)
**Suggested Duration**: 4-5 Minutes
**Visual Style**: Screen recording of the Web UI, terminal commands running tests, and code views, mixed with your slides or camera.

---

## Part 1: Introduction (0:00 - 0:45)
**Visual**: Slides showing the project title "MediSafe" and the problem statement.
*   **Audio (What to say)**:
    > "Hi everyone! I am Joe. Today, I'm presenting my Kaggle Capstone Project: **MediSafe - The Plain-English Medicine Safety Guardian**, built for the Kaggle 5-Day AI Agents Intensive Course.
    > 
    > When patients bring home medicine, they are often overwhelmed by complex chemical names and warnings. Our goal was to build a helper that turns this confusing data into clear, easy-to-understand reports.
    > 
    > What makes MediSafe unique is that it implements all the core concepts from our 5 days of intensive agent training—including custom Skills, the Model Context Protocol (MCP), Human-in-the-Loop triage, and advanced security and testing policies."

---

## Part 2: Architecture & Skills (0:45 - 1:45)
**Visual**: Show the Architecture Diagram (Mermaid chart) and transition to VS Code displaying `backend/skills/api_tools.py` and `backend/agents/agent_system.py`.
*   **Audio (What to say)**:
    > "Under the hood, MediSafe runs on a FastAPI Python backend and a glassmorphism HTML frontend.
    > 
    > When a query starts, our Coordinator Agent triggers custom **Agent Skills** (Day 3) to fetch real-time clinical data:
    > - The **OpenFDA** skill checks for active recalls.
    > - The **PubMed** skill retrieves the latest scientific abstracts.
    > - The **ClinicalTrials** skill finds ongoing research studies.
    > 
    > Once gathered, the Coordinator uses a Gemini 2.5 Flash model acting as an Empathetic Translator to synthesize the findings into a clear, layman-friendly document."

---

## Part 3: Live Demo - Premium Consumer Experience (1:45 - 2:45)
**Visual**: Share screen of the Web UI. Click "Acetaminophen". Show the generated report. Click "🔊 Speak" to hear it, drag the slider in "Pediatric Dosage Calculator", click "Get Dose Reminder" and show the downloaded `.ics` file. 
*   **Audio (What to say)**:
    > "Let's see it in action! Here is our safety report for Acetaminophen. 
    > 
    > We've upgraded the dashboard with several high-fidelity consumer features:
    > - A prominent **Safety Traffic Light** badge shows the drug's safety level instantly.
    > - A **CSS 3D Pill Visualizer** renders a floating representation of a White Tablet.
    > - A **Food Warnings Grid** lists dietary checks like avoiding alcohol.
    > - The **Pediatric Calculator** lets parents drag a slider to find correct child dosages on-the-fly.
    > - You can click **🔊 Speak** to hear the report read aloud, click **Get Dose Reminder** to export a calendar alarm, or click **Save as PDF** to print.
    > - Finally, you can toggle between **English** and **Traditional Chinese** in the header to re-translate the entire report!"

---

## Part 4: Live Demo - MCP & Human-in-the-Loop (2:45 - 3:30)
**Visual**: Click "Aspirin" quick example button. The screen locks, showing the red **Critical Allergy Alert** modal. Click "Approve & Override", and show the report generating.
*   **Audio (What to say)**:
    > "Next is safety and guardrails. We've implemented a standard-compliant **Model Context Protocol (MCP) Server** that runs in a completely isolated subprocess and communicates with our backend over stdio using JSON-RPC 2.0. This ensures full interoperability.
    > 
    > Our patient, John Doe, is allergic to Aspirin. When I search for *Aspirin*, the backend queries the MCP server, detects a conflict, and triggers a **Human-in-the-Loop Triage Warning** (Day 4).
    > 
    > To proceed, a pharmacist must review the allergy warning and click *Approve & Override*. 
    > 
    > Once overridden, the safety report is fetched and loaded from our production-grade TTL cache, preventing rate-limiting during demo presentation. At the bottom, you can ask follow-up questions to our **AI Pharmacist Chat**."

---

## Part 5: Security Gates, Evaluations & Pytest (3:30 - 4:30)
**Visual**: Show terminal running `python -m pytest tests/test_security_pytest.py` showing all 4 tests passed, and show the file `.agents/CONTEXT.md` in VS Code.
*   **Audio (What to say)**:
    > "Finally, we enforce strict compliance and security gates. Our **PreToolUse hook** goes beyond simple regex. It performs full command-line tokenization and path-traversal validation, ensuring strict **sandbox containment** by blocking any command that references a path outside our project workspace.
    > 
    > We also implement a production-grade in-memory cache with size limits and TTL expiration, preventing memory growth and stale data.
    > 
    > We verify all safety boundaries by running our automated **Pytest Security Suite** and local evaluation scripts, showing 100% pass rates.
    > 
    > With standard-compliant stdio MCP, robust sandbox hooks, and a production-grade cache, MediSafe represents a secure, enterprise-ready agent.
    > 
    > Thank you Google AI Studio and Kaggle for this amazing course!"
