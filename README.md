# MediSafe: The Plain-English Medicine Safety Guardian 🛡️

**Track**: Concierge Agents (or Agents for Good)
**Project Version**: Day 4 (Premium Consumer Experience Upgrade)

## 1. Problem Statement
The general public often struggles to understand the complex chemical ingredients listed on medicine packaging. Furthermore, it is extremely difficult for a layperson to track whether a specific ingredient has recent FDA safety warnings, recalls, or emerging side effects documented in recent medical literature. This creates a dangerous information gap in personal healthcare.

## 2. Solution & Value
MediSafe is an AI Concierge Agent designed to bridge this gap. By simply inputting a medicine name or ingredient (or uploading a photo of the package), MediSafe's multi-agent system autonomously queries three major databases (OpenFDA, PubMed, and ClinicalTrials.gov). It then synthesizes this highly technical data into a reassuring, plain-English safety report, empowering individuals to make informed discussions with their doctors.

---

## 3. Key Premium Features (Day 4 Upgrade)

To elevate MediSafe into a high-fidelity consumer health concierge, the following features have been added:

1. **🟢 Visual Safety Traffic Lights**:
   - In the frontend report panel, a prominent traffic light badge displays the safety status:
     - 🟢 **SAFE**: If the drug is generally safe and has no active FDA enforcement actions.
     - 🟡 **WARNING**: If minor safety recalls or side effect reports are found.
     - 🔴 **DANGER / RECALL**: If serious recalls, safety warnings, or patient allergy conflicts are detected.
2. **💊 CSS Pill Visualizer (3D-like Animation)**:
   - A floating, spinning 3D-like CSS representation of the pill (Tablet, Capsule, or Liquid) matches the drug's properties. Capsules feature a detailed split-color gradient matching the drug's typical appearance (e.g. red/white, orange/white).
3. **🍷 Food & Beverage Contraindication Grid**:
   - A visual icon grid showcasing safety status (Safe 🟢 vs Avoid 🔴) when combining the medicine with common items like **Alcohol**, **Dairy**, **Grapefruit**, and **Caffeine**.
4. **🇬🇧/🇹🇼 Bilingual Localization Toggle**:
   - A toggle button in the header allows users to instantly switch the entire app interface and the AI report summary between **English** and **Traditional Chinese (繁體中文)**. Changing the language dynamically re-translates and updates the report.
5. **🔊 Speech Synthesis (TTS Audio)**:
   - Users can listen to the generated safety report read aloud. Using browser-native Speech Synthesis, it automatically reads the text in the correct language (English or Mandarin).
6. **👶 Pediatric Dosage Calculator**:
   - An interactive, weight-based (kg) slider widget allowing parents to estimate safe pediatric dosage ranges (mg) on-the-fly, configured dynamically per active medication.
7. **⏰ Smart Dose Reminders (iCal export)**:
   - Instantly generate and download a standard `.ics` calendar file to schedule dose reminders on Apple Calendar, Google Calendar, or Outlook.
8. **📄 Print / Export as PDF**:
   - A dedicated export button that opens the print dialog with customized `@media print` CSS stylesheets, formatting the safety report perfectly on a white background while hiding search boxes and actions.
9. **💬 Follow-up AI Pharmacist Chat**:
   - An interactive chat box at the bottom of the safety report where users can ask warm, safe follow-up questions (e.g., "Can I take this with milk?") that are answered using the safety report context.

---

## 4. Architecture & Agent Design (ADK)
MediSafe uses a Multi-Agent architecture built in Python:
- **Coordinator Agent**: Receives the user request from the Frontend UI.
- **Vision Agent (Multimodal OCR)**: Uses Gemini 2.5 Flash's vision capabilities to analyze uploaded photos of medicine packages, automatically extracting the active ingredient so users don't have to type it manually.
- **MCP User Profile Server**: A Model Context Protocol (MCP) server (`mcp://user/profile`) that securely stores local patient allergies (Aspirin, Penicillin) and active medications.
- **Data Fetcher Agents (Skills)**: Custom tools calling the REST APIs of:
  - `OpenFDA`: To check for enforcement reports and recalls.
  - `PubMed`: To fetch the latest abstracts on side effects.
  - `ClinicalTrials.gov`: To monitor active safety studies.
- **Medical Translator Agent**: Uses Gemini 2.5 Flash to synthesize raw database outputs into plain-English markdown reports with strict safety guardrails.
- **Human-in-the-Loop (HITL) Triage Gate**: Dynamically blocks reports and requires pharmacist override if the drug conflicts with MCP allergies.

---

## 5. Setup Instructions (How to run locally)

### Prerequisites
- Python 3.10+
- A Google Gemini API Key

### Installation
1. Clone or download this repository.
2. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your API Key in the `.env` file:
   - Create a file named `.env` in the root folder of the project.
   - Add your key inside: `GEMINI_API_KEY=your_actual_api_key_here`

### Running the System
1. Start the backend FastAPI server:
   ```bash
   python backend/main.py
   ```
2. Open the Frontend UI:
   - Simply double-click the `frontend/index.html` file in your web browser.
3. Upload a picture of a medicine (e.g. Acetaminophen) or type it in to analyze its safety.

### Running Local Evaluations
Run our automated local evaluation test suite to verify the agent's logic, safety blocks, and overrides offline (using mocked clients to conserve API credits):
```bash
python tests/eval_agent.py
```

---

## 6. Future Roadmap
As we continue to iterate on MediSafe, our next major milestone is **Cloud Run Deployment** (Day 5 Cloud Integration) and adding real-time **Barcode/NDC Scanning** to automatically look up drugs via phone camera.
