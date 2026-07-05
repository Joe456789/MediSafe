import os
import base64
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

def test_pro():
    base64_gif = "R0lGODlhAQABAIAAAP///wAAACH5BAEAAAAALAAAAAABAAEAAAICRAEAOw=="
    image_bytes = base64.b64decode(base64_gif)
    prompt = "Extract any text from this image."
    
    print("Testing OCR with gemini-2.5-pro...")
    try:
        response = client.models.generate_content(
            model='gemini-2.5-pro',
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/gif"),
                prompt
            ]
        )
        print("Success! Response:", response.text)
    except Exception as e:
        print("Failed with error:", str(e))

if __name__ == "__main__":
    test_pro()
