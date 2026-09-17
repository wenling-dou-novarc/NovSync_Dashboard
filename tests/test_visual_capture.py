import os
import json
import time
import pytest
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError
from PIL import Image
from google import genai
from google.genai import errors
from PIL import Image, ImageChops

BASE_URL = "https://test-novsync.novarctech.com"
AUTH_FILE = "auth/state.json"
TARGET_UNITS = ["SWR-1224"]

GLOBAL_PAGES = [
    {"name": "fleet_view", "path": "/"},
    {"name": "admin_tool", "path": "/admin"},
    {"name": "performance_details", "path": "/performance"},
]

UNIT_PAGES = [
    {"name": "unit_info", "suffix": ""},
    {"name": "videos_logs", "suffix": "/search"},
    {"name": "analytics", "suffix": "/analytics"},
    {"name": "performance", "suffix": "/performance"},
    {"name": "qc_report", "suffix": "/qc_report"},
    {"name": "events", "suffix": "/alarm_list"},
    {"name": "file_list", "suffix": "/files"},
    {"name": "support", "suffix": "/support"},
]


def dismiss_tour_popups(page: Page):
    """Detects and dismisses 'What's New in NovSync' modals and onboarding pop-ups."""
    page.wait_for_timeout(600)

    dismiss_selectors = [
        "button:has-text('Skip')",
        "button:has-text('Finish')",
        "button:has-text('Close')",
        "button:has-text('Done')",
        "[aria-label='Close']",
        "button[aria-label='Close']",
    ]

    for selector in dismiss_selectors:
        button = page.locator(selector)
        if button.count() > 0 and button.first.is_visible():
            button.first.click()
            page.wait_for_timeout(500)
            break

    # Inject CSS guard to eliminate modal backdrops
    page.add_style_tag(
        content="""
        .modal, .modal-backdrop, [class*='backdrop'], [class*='overlay'], 
        [class*='modal-root'], .shepherd-element, .driver-popover {
            display: none !important;
            visibility: hidden !important;
            opacity: 0 !important;
        }
    """
    )


def wait_until_page_is_fully_loaded(page: Page, wait_seconds: int = 20):
    """Waits for DOM content, splash overlays, network requests, and skeleton placeholders to resolve."""
    page.wait_for_load_state("domcontentloaded")

    # 1. Wait for splash screen overlay to unmount
    try:
        page.wait_for_selector(
            ".loading-container", 
            state="hidden", 
            timeout=wait_seconds * 1000
        )
    except PlaywrightTimeoutError:
        print("\n[DIAGNOSTIC WARNING] Loader '.loading-container' failed to hide within timeout.")

    # 2. Wait for RTK Query background network requests to complete
    try:
        page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeoutError:
        print("\n[DIAGNOSTIC WARNING] Network traffic did not go idle within 15s.")

    # 3. Wait for Ant Design chart skeleton placeholders to unmount
    skeleton_selectors = [
        ".ant-skeleton",
        "[class*='skeleton']",
        ".ant-spin-spinning"
    ]
    for selector in skeleton_selectors:
        try:
            page.wait_for_selector(selector, state="detached", timeout=10000)
        except PlaywrightTimeoutError:
            pass

    # 4. Render buffer allowing canvas charts and SVG elements to paint
    page.wait_for_timeout(1500)

    # 5. Dismiss onboarding pop-ups
    dismiss_tour_popups(page)


def images_are_identical(img1_path: str, img2_path: str, threshold: float = 0.005) -> bool:
    """Returns True if local pixel differences fall below threshold."""
    img1 = Image.open(img1_path).convert('RGB')
    img2 = Image.open(img2_path).convert('RGB')
    diff = ImageChops.difference(img1, img2)
    
    # Calculate percentage of changed pixels
    non_zero = sum(1 for pixel in diff.getdata() if any(c > 15 for c in pixel))
    total_pixels = img1.width * img1.height
    return (non_zero / total_pixels) < threshold

def images_are_identical(img1_path: str, img2_path: str, threshold: float = 0.005) -> bool:
    """Returns True if local pixel differences fall below threshold."""
    if not os.path.exists(img1_path) or not os.path.exists(img2_path):
        return False

    with Image.open(img1_path).convert("RGB") as img1, Image.open(img2_path).convert("RGB") as img2:
        if img1.size != img2.size:
            return False

        diff = ImageChops.difference(img1, img2)
        non_zero = sum(1 for pixel in diff.getdata() if any(c > 15 for c in pixel))
        total_pixels = img1.width * img1.height
        return (non_zero / total_pixels) < threshold


def evaluate_visual_changes(baseline_path: str, current_path: str) -> tuple[str, str]:
    """Compares baseline and current screenshots using local pixel diff with Gemini API fallback."""
    if not os.path.exists(baseline_path):
        return (
            "SKIP",
            f"Baseline missing at {baseline_path}. Copy current screenshot to baseline directory to initialize.",
        )

    # 1. Fast Path: Skip API call completely if local pixel diff is negligible (< 0.5% shift)
    if images_are_identical(baseline_path, current_path):
        return "PASS", "Local Pixel Check: Images are visually identical."

    # 2. Standard Gemini API Key Path
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
        "CRITICAL INSTRUCTION: Ignore minor rotation, scaling, or perspective differences in dynamic 3D canvas models as long as surrounding UI components match. "
        "Provide a concise bulleted list of differences, then finish strictly with 'VERDICT: PASS' if visual differences are acceptable/absent, "
        "or 'VERDICT: FAIL' if bugs or layout breakdowns are detected."
    )

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=[prompt, baseline_img, current_img]
            )
            analysis = response.text
            verdict = "PASS" if "VERDICT: PASS" in analysis.upper() else "FAIL"
            return verdict, analysis

        except errors.APIError as e:
            error_msg = str(e).upper()

            # Fail fast on hard daily quotas
            if "PERDAY" in error_msg or "DAILY" in error_msg:
                return "SKIP", f"Daily Gemini API limit reached (20 RPD): {e}"

            # Retry on short-term per-minute rate limits (RPM)
            if "429" in error_msg or "QUOTA" in error_msg or "RESOURCE_EXHAUSTED" in error_msg:
                if attempt < max_retries - 1:
                    print(f"\n[API RATE LIMIT] Per-minute limit hit. Waiting 10s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(10)
                    continue
                return "SKIP", f"Skipped due to Gemini API Rate Limit: {e}"
            return "FAIL", f"Gemini API returned an error: {e}"

        except Exception as e:
            return "FAIL", f"Unexpected error during visual analysis: {e}"


@pytest.fixture(scope="session")
def browser_type_launch_args(browser_type_launch_args):
    return {
        **browser_type_launch_args,
        "headless": True,
        "args": [
            "--disable-blink-features=AutomationControlled",
            "--disable-web-security",
            "--allow-running-insecure-content",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
        ]
    }


@pytest.fixture(scope="session", autouse=True)
def setup_directories():
    """Ensures screenshot directories exist."""
    os.makedirs("screenshots/current", exist_ok=True)
    os.makedirs("screenshots/baseline", exist_ok=True)


@pytest.fixture
def authenticated_page(browser):
    if not os.path.exists(AUTH_FILE):
        pytest.fail(f"Auth file missing at {AUTH_FILE}.")

    with open(AUTH_FILE, "r") as f:
        state_data = json.load(f)

    token = None
    for origin in state_data.get("origins", []):
        for item in origin.get("localStorage", []):
            if any(k in item["name"].lower() for k in ["token", "auth", "jwt", "access"]):
                token = item["value"].strip('"')
                break

    # Set explicit 1080p desktop viewport resolution
    context = browser.new_context(
        storage_state=AUTH_FILE,
        viewport={"width": 1920, "height": 1080},
        device_scale_factor=1
    )
    page = context.new_page()

    def force_auth_headers(route):
        url = route.request.url.lower()

        if "branding" in url:
            route.fulfill(
                status=200,
                headers={"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
                json={}
            )
            return

        headers = dict(route.request.headers)
        if token and "authorization" not in headers:
            headers["authorization"] = f"Bearer {token}" if not token.startswith("Bearer ") else token
        route.continue_(headers=headers)

    page.route("https://api-test.novarctech.com/**", force_auth_headers)

    page.on("console", lambda msg: print(f"\n[CONSOLE {msg.type.upper()}] {msg.text}") if msg.type in ["error", "warning"] else None)
    page.on("response", lambda resp: print(f"\n[HTTP {resp.status}] {resp.url}") if resp.status >= 400 else None)

    page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")

    # 1. Ignore HTTP 500 responses in terminal output
    page.on(
        "response",
        lambda resp: print(f"\n[HTTP {resp.status}] {resp.url}")
        if resp.status >= 400 and resp.status != 500
        else None,
    )

    # 2. Ignore 500-related "Failed to load resource" console errors
    page.on(
        "console",
        lambda msg: print(f"\n[CONSOLE {msg.type.upper()}] {msg.text}")
        if msg.type in ["error", "warning"] and "status of 500" not in msg.text
        else None,
    )

    yield page
    context.close()

@pytest.mark.parametrize(
    "page_info",
    GLOBAL_PAGES,
    ids=[page["name"] for page in GLOBAL_PAGES]
)
def test_global_pages_visuals(authenticated_page: Page, page_info: dict):
    """Validates global dashboard routes."""
    target_url = f"{BASE_URL}{page_info['path']}"
    authenticated_page.goto(target_url)

    wait_until_page_is_fully_loaded(authenticated_page)

    baseline_path = f"screenshots/baseline/global_{page_info['name']}.png"
    current_path = f"screenshots/current/global_{page_info['name']}.png"

    authenticated_page.screenshot(path=current_path, full_page=True)

    verdict, report = evaluate_visual_changes(baseline_path, current_path)
    print(f"\n--- [{page_info['name'].upper()}] GEMINI REPORT ---\n{report}")

    if verdict == "SKIP":
        pytest.skip(report)

    assert verdict == "PASS", f"Visual regression detected on global page '{page_info['name']}':\n{report}"


@pytest.mark.parametrize("unit_id", TARGET_UNITS)
@pytest.mark.parametrize(
    "page_info",
    UNIT_PAGES,
    ids=[page["name"] for page in UNIT_PAGES]
)
def test_unit_pages_visuals(authenticated_page: Page, unit_id: str, page_info: dict):
    """Validates unit-specific dashboard routes."""
    target_url = f"{BASE_URL}/{unit_id}{page_info['suffix']}"
    authenticated_page.goto(target_url)

    wait_until_page_is_fully_loaded(authenticated_page)

    baseline_path = f"screenshots/baseline/{unit_id}_{page_info['name']}.png"
    current_path = f"screenshots/current/{unit_id}_{page_info['name']}.png"

    authenticated_page.screenshot(path=current_path, full_page=True)

    verdict, report = evaluate_visual_changes(baseline_path, current_path)
    print(f"\n--- [{unit_id} - {page_info['name'].upper()}] GEMINI REPORT ---\n{report}")

    if verdict == "SKIP":
        pytest.skip(report)

    assert verdict == "PASS", f"Visual regression detected on {unit_id} page '{page_info['name']}':\n{report}"