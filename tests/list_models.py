import os
from google import genai
from dotenv import load_dotenv

load_dotenv()
api_key = os.environ.get("GEMINI_API_KEY")

client = genai.Client(api_key=api_key)

try:
    print("Listing model names:")
    for m in client.models.list():
        print(m.name)
except Exception as e:
    print("Error:", str(e))
