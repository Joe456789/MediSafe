# YouTube Demo Video Script: MediSafe (Simplified version, < 3.5 Mins)

**Video Title**: MediSafe - Plain-English Medicine Safety Guardian (Kaggle Capstone Pitch)
**Suggested Duration**: 3 Minutes
**Visual Style**: Screen recording of the Web UI, switching briefly to the terminal for tests.

---

## Part 1: Introduction (0:00 - 0:45)
**Visual**: Home page of the Web UI. Scroll slightly to show trending cards.
*   **Audio (What to say)**:
    > "Hi everyone! I am Joe. Today, I am presenting my project: **MediSafe — The Plain-English Medicine Safety Guardian**. 
    > 
    > Many patients find medicine labels and warnings very confusing. MediSafe solves this. It turns complex medical data into clear, simple reports for everyone."

---

## Part 2: Architecture & Skills (0:45 - 1:15)
**Visual**: Show the data-fetching code in VS Code (backend/skills/api_tools.py).
*   **Audio (What to say)**:
    > "MediSafe runs on a FastAPI backend and a clean HTML frontend. 
    > 
    > When we search for a drug, our agent uses three custom skills to fetch real-time data: **OpenFDA** for recalls, **PubMed** for science abstracts, and **ClinicalTrials** for research. 
    > 
    > Then, **Gemini 2.5 Flash** translates all data into a simple safety report."

---

## Part 3: Live Demo — Premium Features (1:15 - 2:15)
**Visual**: Click "Acetaminophen" card. Point to green badge, 3D Pill, and Alcohol warning. Drag the weight slider. Click "Speak" then "Stop". Download calendar reminder. Switch to Traditional Chinese.
*   **Audio (What to say)**:
    > "Let’s see the demo. I will click **Acetaminophen**. 
    > 
    > Here is the report. The dashboard shows a green **Safety Badge**, a floating **3D Pill Visualizer**, and clear **Food Warning Details** like avoiding alcohol. 
    > 
    > Parents can drag this weight slider to calculate pediatric dosage instantly. 
    > 
    > You can also click **Speak** to listen to the report, download a **Dose Reminder** for your calendar, or toggle to **Traditional Chinese**."

---

## Part 4: Allergy Alert & Pharmacist Override (2:15 - 2:55)
**Visual**: Toggle back to English. Search "Aspirin". Click "Approve & Override" on red alert popup. Ask chatbot "Can I take this with milk?".
*   **Audio (What to say)**:
    > "Next is safety. We built a local **MCP Server** that runs in a separate process. 
    > 
    > Our patient, John Doe, is allergic to Aspirin. If I search **Aspirin**, the system blocks the page and shows a red **Allergy Alert**. 
    > 
    > To proceed, a pharmacist must review the warning and click **Approve & Override**. 
    > 
    > Once overridden, the report loads. We can also ask follow-up questions in the **AI Pharmacist Chat** at the bottom."

---

## Part 5: Security & Testing (2:55 - 3:30)
**Visual**: Alt-Tab to terminal. Show pytest output (4 passed) and eval_agent output.
*   **Audio (What to say)**:
    > "For security, we use a **PreToolUse Hook** to check commands and block dangerous code. We also use a **TTL Cache** to save memory. 
    > 
    > We verified our system by running **Pytest** and local evaluations. All tests passed with **100% success**. 
    > 
    > MediSafe is secure, fast, and ready for production. Thank you!"
