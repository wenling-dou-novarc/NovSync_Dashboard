import os
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
