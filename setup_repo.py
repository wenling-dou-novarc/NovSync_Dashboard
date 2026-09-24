import os
from pathlib import Path

# Define file contents
gitignore_content = """# Python & Virtual Environments
venv/
.venv/
__pycache__/
*.py[cod]
.pytest_cache/

# Authentication & Environment Variables
.env
auth/state.json
*.json
!package.json

# Screenshots & Output
screenshots/current/
!screenshots/baseline/.gitkeep
*.log
htmlcov/
.coverage

# System Files
.DS_Store
Thumbs.db
"""

requirements_content = """playwright>=1.40.0
pytest>=8.0.0
pytest-playwright>=0.4.0
Pillow>=10.0.0
google-genai>=0.1.0
python-dotenv>=1.0.0
"""

pytest_ini_content = """[pytest]
testpaths = tests
python_files = test_*.py
python_functions = test_*
addopts = -s --tb=short
markers =
    visual: Visual regression tests
    interactive: Interactive UI flow tests
"""

settings_content = """import os

BASE_URL = os.getenv("NOVSYNC_BASE_URL", "https://api-test.novarctech.com")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

TARGET_UNITS = [
    "A30001",
    "A30002"
]
"""

pixel_diff_content = """import os
from PIL import Image, ImageChops

def images_are_identical(img1_path: str, img2_path: str, threshold: float = 0.005) -> bool:
    \"\"\"Returns True if local pixel differences fall below threshold.\"\"\"
    if not os.path.exists(img1_path) or not os.path.exists(img2_path):
        return False

    with Image.open(img1_path).convert("RGB") as img1, Image.open(img2_path).convert("RGB") as img2:
        if img1.size != img2.size:
            return False

        diff = ImageChops.difference(img1, img2)
        non_zero = sum(1 for pixel in diff.getdata() if any(c > 15 for c in pixel))
        total_pixels = img1.width * img1.height
        return (non_zero / total_pixels) < threshold
"""

gemini_eval_content = """import os
import time
import pytest
from PIL import Image
from google import genai
from google.genai import errors
from utils.pixel_diff import images_are_identical

def evaluate_visual_changes(baseline_path: str, current_path: str) -> tuple[str, str]:
    if not os.path.exists(baseline_path):
        return ("SKIP", f"Baseline missing at {baseline_path}.")

    if images_are_identical(baseline_path, current_path):
        return "PASS", "Local Pixel Check: Images are visually identical."

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        pytest.fail("GEMINI_API_KEY environment variable is not set.")

    client = genai.Client(api_key=api_key)
    baseline_img = Image.open(baseline_path)
    current_img = Image.open(current_path)

    prompt = (
        "You are an automated visual regression testing engine for a web dashboard. "
        "The first image is the baseline (expected UI). The second image is the actual current build. "
        "Analyze both images for visual defects, unwanted layout shifts, missing elements, or formatting bugs. "
        "CRITICAL INSTRUCTION: Ignore minor rotation, scaling, or perspective differences in dynamic 3D canvas models. "
        "Provide a concise bulleted list of differences, then finish strictly with 'VERDICT: PASS' or 'VERDICT: FAIL'."
    )

    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[prompt, baseline_img, current_img]
        )
        analysis = response.text
        verdict = "PASS" if "VERDICT: PASS" in analysis.upper() else "FAIL"
        return verdict, analysis
    except Exception as e:
        return "FAIL", f"Gemini API error: {e}"
"""

readme_content = """# NovSync Automated Visual Regression Suite

Playwright + Pytest framework for visual and functional regression testing of NovSync dashboard views.

## Quick Start
1. `source venv/bin/activate`
2. `pip install -r requirements.txt`
3. `export GEMINI_API_KEY="your_api_key"`
4. `pytest -s`
"""

# Structure Mapping
files_to_create = {
    ".gitignore": gitignore_content,
    "requirements.txt": requirements_content,
    "pytest.ini": pytest_ini_content,
    "README.md": readme_content,
    "config/__init__.py": "",
    "config/settings.py": settings_content,
    "utils/__init__.py": "",
    "utils/pixel_diff.py": pixel_diff_content,
    "utils/gemini_eval.py": gemini_eval_content,
    "auth/auth_setup.py": "# Add login setup script here\n",
    "tests/__init__.py": "",
    "tests/conftest.py": "# Add Pytest fixtures here\n",
    "tests/test_visual_capture.py": "# Add visual test suites here\n",
    "screenshots/baseline/.gitkeep": "",
    "screenshots/current/.gitkeep": "",
}

def build_repo():
    print("Building NovSync repository structure...")
    for file_path, content in files_to_create.items():
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists() or content:
            path.write_text(content, encoding="utf-8")
            print(f"  Created: {file_path}")
    print("\nRepository scaffold successfully created!")

if __name__ == "__main__":
    build_repo()