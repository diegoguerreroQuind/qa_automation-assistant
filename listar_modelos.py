import os
import ssl
import google.generativeai as genai
from dotenv import load_dotenv

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

load_dotenv()
genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

print("Buscando modelos autorizados para tu llave...")
for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"👉 {m.name}")