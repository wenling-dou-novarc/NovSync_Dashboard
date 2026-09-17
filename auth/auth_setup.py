from playwright.sync_api import sync_playwright

def generate_auth_state():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # 1. Login to the frontend SPA
        page.goto("https://test-novsync.novarctech.com/login")
        # ... perform login steps ...
        page.wait_for_url("https://test-novsync.novarctech.com/", timeout=60000)

        # 2. Ping backend API origin to ensure API cookies are saved to state.json
        page.goto("https://api-test.novarctech.com/api/v2/branding")
        page.wait_for_timeout(2000)

        context.storage_state(path="auth/state.json")
        browser.close()

if __name__ == "__main__":
    generate_auth_state()
