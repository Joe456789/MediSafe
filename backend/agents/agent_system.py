import os
import base64
import time
import re
import json
import subprocess
import sys
from google import genai
from google.genai import types
from backend.skills.api_tools import fetch_openfda_data, fetch_pubmed_abstracts, fetch_clinical_trials

# Global TTL cache to prevent 429 rate limit blocks
MEDISAFE_CACHE = {}
CACHE_TTL = 3600  # 1 hour
MAX_CACHE_SIZE = 100

def get_from_cache(cache_key):
    """Retrieve entry from cache if it exists and is not expired."""
    if cache_key in MEDISAFE_CACHE:
        val, ts = MEDISAFE_CACHE[cache_key]
        if time.time() - ts < CACHE_TTL:
            return val
        else:
            del MEDISAFE_CACHE[cache_key]
    return None

def set_in_cache(cache_key, value):
    """Save entry in cache, evicting expired or oldest items if full."""
    now = time.time()
    # Evict expired
    expired_keys = [k for k, (_, ts) in MEDISAFE_CACHE.items() if now - ts >= CACHE_TTL]
    for k in expired_keys:
        del MEDISAFE_CACHE[k]
    # Evict FIFO if size limit exceeded
    if len(MEDISAFE_CACHE) >= MAX_CACHE_SIZE:
        oldest = next(iter(MEDISAFE_CACHE))
        del MEDISAFE_CACHE[oldest]
    MEDISAFE_CACHE[cache_key] = (value, now)


def call_gemini_with_retry(client, model, contents, config=None, max_retries=5, initial_delay=3):
    """Wraps Gemini API calls to handle 429 Rate Limit / 503 High Demand / Server errors with dynamic backoff."""
    for attempt in range(max_retries):
        try:
            if config:
                return client.models.generate_content(model=model, contents=contents, config=config)
            else:
                return client.models.generate_content(model=model, contents=contents)
        except Exception as e:
            err_msg = str(e)
            
            # Check if this is a temporary rate limit or server overload error
            is_temp_error = any(
                term in err_msg or term in err_msg.lower() 
                for term in ["429", "500", "503", "504", "resource_exhausted", "unavailable", "rate limit", "overloaded"]
            )
            
            if is_temp_error:
                if attempt == max_retries - 1:
                    raise e
                
                # Dynamically parse how many seconds Gemini wants us to wait
                delay = initial_delay
                match = re.search(r"Please retry in (\d+\.?\d*)s", err_msg)
                if match:
                    delay = float(match.group(1)) + 1.5  # Add a 1.5s safety buffer
                else:
                    match = re.search(r"retryDelay: '(\d+)s'", err_msg)
                    if match:
                        delay = float(match.group(1)) + 1.5
                    elif "503" in err_msg or "unavailable" in err_msg.lower():
                        delay = 6.0 # Sleep 6 seconds for high demand/overload
                
                print(f"[API Warning] Temporary error occurred. Waiting {delay:.2f}s before retrying (Attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
            else:
                raise e

def extract_ingredient_from_image(base64_data: str, mime_type: str) -> str:
    """Uses Gemini Vision to extract the medicine name from an image."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise Exception("GEMINI_API_KEY environment variable not set.")
        
    client = genai.Client(api_key=api_key)
    image_bytes = base64.b64decode(base64_data)
    
    prompt = "Look at this image of a medicine bag, pill bottle, or prescription. Extract the primary active ingredient name or the main medicine name. Return ONLY the exact name of the medicine/ingredient in English (e.g. Acetaminophen, Ibuprofen) and absolutely nothing else."
    
    print("Running Vision OCR on uploaded image...")
    response = call_gemini_with_retry(
        client=client,
        model='gemini-2.5-flash',
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
            prompt
        ]
    )
    extracted_name = response.text.strip()
    print(f"Extracted ingredient: {extracted_name}")
    return extracted_name

def analyze_ingredient(ingredient: str, bypass_triage: bool = False, lang: str = "en", user_allergies: list | None = None, patient_name: str = "John Doe") -> dict:
    # 0a. Per-user allergy check (e.g. LINE users with their own registered profile).
    # Done before the shared cache lookup and skips the MCP subprocess entirely,
    # since a triage result here is specific to this user's allergy list and must
    # never be served from the shared ingredient-level cache to a different user.
    if not bypass_triage and user_allergies is not None:
        allergies_lower = [a.lower() for a in user_allergies]
        if ingredient.lower() in allergies_lower:
            print(f"[Profile Alert] User allergy detected for: {ingredient}")
            return {
                "status": "requires_triage",
                "ingredient": ingredient,
                "patient_name": patient_name,
                "allergies": user_allergies,
            }

    # 0b. Check in-memory cache with TTL
    key_name = ingredient.lower().strip()
    cache_key = (key_name, lang, bypass_triage)
    cached_val = get_from_cache(cache_key)
    if cached_val is not None:
        print(f"[Cache Hit] Returning cached report for: {ingredient} (lang={lang}, bypass={bypass_triage})")
        return cached_val

    # 1. MCP Allergy Check (Day 2 MCP Integration via Standard stdio JSON-RPC 2.0 Subprocess)
    # Only used as a fallback when the caller didn't supply user_allergies directly.
    if not bypass_triage and user_allergies is None:
        try:
            # Spawn user profile MCP server as a subprocess communicating over stdio
            process = subprocess.Popen(
                [sys.executable, "-m", "backend.mcp.user_profile_mcp"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            # Construct standard JSON-RPC 2.0 request to read the profile resource
            req_payload = {
                "jsonrpc": "2.0",
                "method": "resources/read",
                "params": {"uri": "mcp://user/profile"},
                "id": 1
            }
            stdout, stderr = process.communicate(input=json.dumps(req_payload) + "\n", timeout=5)
            
            res = json.loads(stdout.strip())
            if "error" in res:
                raise Exception(res["error"]["message"])
                
            resource_data = res["result"]
            profile = json.loads(resource_data["contents"][0]["text"])
            
            # Check if the ingredient matches any allergies (case-insensitive)
            allergies = [a.lower() for a in profile.get("allergies", [])]
            if ingredient.lower() in allergies:
                print(f"[MCP Alert] User allergy detected for: {ingredient}")
                triage_res = {
                    "status": "requires_triage",
                    "ingredient": ingredient,
                    "patient_name": profile.get("name", "John Doe"),
                    "allergies": profile.get("allergies", [])
                }
                set_in_cache(cache_key, triage_res)
                return triage_res
        except Exception as e:
            print(f"[MCP Warning] Failed to query user profile MCP server over stdio: {str(e)}")


    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return {
            "error": "GEMINI_API_KEY environment variable not set. Please set it to run the agent."
        }
        
    client = genai.Client(api_key=api_key)
    
    # 1. Fetch data using our skills (Data Fetcher Agent logic)
    print(f"Fetching data for {ingredient}...")
    fda_data = fetch_openfda_data(ingredient)
    pubmed_data = fetch_pubmed_abstracts(ingredient)
    trials_data = fetch_clinical_trials(ingredient)
    
    # 2. Coordinator & Translator Agent System Prompt (Structured JSON Output)
    system_instruction = """You are MediSafe, a friendly and empathetic medical concierge agent. 
Your goal is to explain medicine safety to someone with zero medical background (like a 10-year-old or an elderly person).
You will receive data from the FDA, PubMed, and Clinical Trials. 
You MUST output a valid JSON object with the following keys:
1. "safety_level": "safe" (if no active recalls and generally safe), "warning" (if minor recalls or safety warnings in studies), or "danger" (if serious warnings).
2. "pill_type": "tablet", "capsule", or "liquid" (typical form of this medicine).
3. "pill_color": "white", "red", "orange", "blue", "yellow", or "brown" (typical color).
4. "food_warnings": { "alcohol": "avoid" or "safe", "dairy": "avoid" or "safe", "grapefruit": "avoid" or "safe", "caffeine": "avoid" or "safe" } (typical food conflicts).
5. "ingredient_zh": 藥品成分最常見的繁體中文名稱（例如 Acetaminophen 寫「乙醯胺酚（普拿疼）」）；若 lang 為 en 或沒有通用中文譯名，請填入原英文名稱。
6. "report": "A warm, extremely simple safety summary for the general public in markdown. Use bullet points. The report MUST contain exactly three clear sections in markdown:
   - 💊 用藥小叮嚀 (How to Take / Important Guidelines): Practical details such as whether to take with food, what to do if a dose is missed.
   - ⚠️ 密切注意的副作用 (Side Effects to Watch): Simple list of common side effects (e.g. stomach upset) and severe allergy alerts (e.g. rashes).
   - 🔍 歷史品質與安全紀錄 (Quality & Safety Record): Reassuring summary of quality history. Avoid long lists of scary historic recall details; keep it simple and focus on current safety."

If the 'lang' parameter is 'zh', you MUST translate the "report" text (including the headers) into Traditional Chinese (繁體中文), but keep all other JSON keys and values in English.
If 'lang' is 'en', write the "report" in English.
DO NOT include markdown code block formatting (such as ```json) in your output, return ONLY the raw JSON string."""

    prompt = f"""
    Please analyze the following medicine/ingredient: {ingredient}
    Target Language: {lang}
    
    Data from FDA:
    {fda_data}
    
    Data from PubMed:
    {pubmed_data}
    
    Data from Clinical Trials:
    {trials_data}
    
    Write a warm, extremely simple safety summary for the general public. Return a valid JSON.
    """
    
    print("Generating plain-English report...")
    response = call_gemini_with_retry(
        client=client,
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.2,
            response_mime_type="application/json"
        )
    )
    
    # Parse the structured JSON output
    try:
        report_data = json.loads(response.text.strip())
    except Exception as e:
        print(f"Failed to parse JSON response: {str(e)}")
        # Fallback dictionary if JSON parsing fails
        report_data = {
            "safety_level": "warning",
            "pill_type": "tablet",
            "pill_color": "white",
            "food_warnings": {"alcohol": "avoid", "dairy": "safe", "grapefruit": "safe", "caffeine": "safe"},
            "report": response.text
        }
    
    # Override for Pseudoephedrine specific pill representation
    if "pseudoephedrine" in ingredient.lower():
        report_data["pill_type"] = "capsule"
        report_data["pill_color"] = "red-yellow"
    
    # 3. Security Guardrails (Adding mandatory disclaimer)
    disclaimer = "DISCLAIMER: This report is generated by AI for informational purposes only. It is not medical advice. Always consult a healthcare professional before making medical decisions or changing medications."
    
    # Construct final result
    final_result = {
        "status": "normal",
        "ingredient": ingredient,
        "ingredient_zh": report_data.get("ingredient_zh") or ingredient,
        "safety_level": report_data.get("safety_level", "warning"),
        "pill_type": report_data.get("pill_type", "tablet"),
        "pill_color": report_data.get("pill_color", "white"),
        "food_warnings": report_data.get("food_warnings", {}),
        "report": report_data.get("report", "Error generating report."),
        "disclaimer": disclaimer,
        "raw_data": {
            "fda": fda_data,
            "pubmed": pubmed_data,
            "clinical_trials": trials_data
        }
    }
    
    # Store in cache with TTL
    set_in_cache(cache_key, final_result)
    
    return final_result

def answer_followup_question(ingredient: str, report: str, question: str, lang: str = "en") -> str:
    """Answers follow-up questions from the user using report context."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        return "GEMINI_API_KEY environment variable not set."
        
    client = genai.Client(api_key=api_key)
    
    system_instruction = """You are MediSafe AI Pharmacist, a friendly, empathetic assistant. 
You will be asked a follow-up question about a medicine safety report.
Answer the question warmly and clearly. Use simple language.
Keep the answer under 3-4 sentences.
Always remind the user to consult a doctor or pharmacist for serious health concerns.

If the 'lang' parameter is 'zh', write your response in Traditional Chinese (繁體中文).
If 'lang' is 'en', write your response in English."""

    prompt = f"""
    Medicine: {ingredient}
    Language: {lang}
    Safety Report context:
    {report}
    
    User Question: {question}
    """
    
    print("Answering follow-up question...")
    response = call_gemini_with_retry(
        client=client,
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=0.3
        )
    )
    return response.text.strip()
