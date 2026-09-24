import os

BASE_URL = os.getenv("NOVSYNC_BASE_URL", "https://api-test.novarctech.com")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TARGET_UNITS = [
    "A30001",
    "A30002"
]
