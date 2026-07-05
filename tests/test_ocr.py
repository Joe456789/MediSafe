import sys
import os
import base64

# Add the project root to the python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from backend.agents.agent_system import extract_ingredient_from_image

def test_ocr():
    # 1x1 white GIF in base64
    base64_gif = "R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="
    
    print("Testing OCR with a 1x1 GIF image using current configuration...")
    try:
        result = extract_ingredient_from_image(base64_gif, "image/gif")
        print("Success! Extracted text:", result)
    except Exception as e:
        print("OCR Test Failed!")
        print("Error Type:", type(e).__name__)
        print("Error Details:", str(e))

if __name__ == "__main__":
    test_ocr()
