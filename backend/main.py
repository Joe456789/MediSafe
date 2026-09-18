from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sys
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the path so we can import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.agents.agent_system import analyze_ingredient, extract_ingredient_from_image, answer_followup_question
from backend.line_webhook import router as line_router

app = FastAPI(title="MediSafe API", description="AI Agent for Medicine Safety Translation")

app.include_router(line_router)

# Allow CORS for local frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class AnalyzeRequest(BaseModel):
    ingredient: str | None = None
    image_base64: str | None = None
    mime_type: str | None = None
    bypass_triage: bool = False
    lang: str = "en"

class ChatRequest(BaseModel):
    ingredient: str
    report: str
    message: str
    lang: str = "en"

@app.post("/api/analyze")
async def analyze(request: AnalyzeRequest):
    ingredient_to_analyze = request.ingredient

    if request.image_base64 and request.mime_type:
        try:
            extracted = extract_ingredient_from_image(request.image_base64, request.mime_type)
            ingredient_to_analyze = extracted
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Image OCR failed: {str(e)}")

    if not ingredient_to_analyze or len(ingredient_to_analyze.strip()) == 0:
        raise HTTPException(status_code=400, detail="Ingredient or valid image must be provided.")
    
    try:
        result = analyze_ingredient(ingredient_to_analyze, bypass_triage=request.bypass_triage, lang=request.lang)
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        result["extracted_ingredient"] = ingredient_to_analyze 
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat(request: ChatRequest):
    if not request.message or len(request.message.strip()) == 0:
        raise HTTPException(status_code=400, detail="Message cannot be empty")
    
    try:
        reply = answer_followup_question(
            ingredient=request.ingredient,
            report=request.report,
            question=request.message,
            lang=request.lang
        )
        return {"response": reply}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Mount static files for the frontend dashboard
app.mount("/", StaticFiles(directory="frontend", html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=True)
