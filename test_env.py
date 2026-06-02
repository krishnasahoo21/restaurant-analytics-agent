from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv("ANTHROPIC_API_KEY")

if api_key:
    print(f"✅ API key loaded successfully!")
    print(f"Key starts with: {api_key[:10]}...")
else:
    print("❌ API key not found. Check your .env file.")