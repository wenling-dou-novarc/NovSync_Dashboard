import os
import re

import pytest
from dotenv import load_dotenv
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError

from tests.test_visual_capture import evaluate_visual_changes

# This loads GEMINI_API_KEY from your .env file
load_dotenv()

BASE_URL = "https://test-novsync.novarctech.com"
UNIT_ID = "SWR-1224"


def go_to_unit_page(page: Page):
    page.goto(f"{BASE_URL}/{UNIT_ID}")
    page.wait_for_load_state("networkidle")


def body_text(page: Page) -> str:
    return page.locator("body").inner_text()


def get_selected_unit_values(page: Page):
    selected = page.locator(
        ".ant-select-selection-item, .ant-select-selection-overflow-item"
    )
    values = []
    for i in range(selected.count()):
        text = selected.nth(i).inner_text().strip()
        if text and re.search(r"SWR-\d+|Unit\s+\d+", text, re.I):
            values.append(text)
    return values


def get_chart_group_counts(page: Page):
    return {
        "NovEye Mode": page.get_by_text("NovEye Mode", exact=True).count(),
        "Fillet Mode": page.get_by_text("Fillet Mode", exact=True).count(),
        "Pipe Statistics": page.get_by_text("Pipe Statistics", exact=True).count(),
    }


def select_unit_count(page: Page, target_count: int):
    selector = page.locator(".ant-select").first
    selector.click()

    options = page.locator(".ant-select-dropdown .ant-select-item-option")
    maximum_attempts = 10

    for _ in range(maximum_attempts):
        selected = get_selected_unit_values(page)
        if len(selected) >= target_count:
            break

        if options.count() == 0:
            selector.click()
            options = page.locator(".ant-select-dropdown .ant-select-item-option")

        for i in range(options.count()):
            item = options.nth(i)
            text = item.inner_text().strip()
            if text and text not in selected:
                item.click()
                break
        selected = get_selected_unit_values(page)
        if len(selected) >= target_count:
            break

    final_selected = get_selected_unit_values(page)
    assert len(final_selected) == target_count, (
        f"Expected {target_count} selected units, but got {final_selected}."
    )


def test_unit_info_fields_are_displayed(page: Page):
    go_to_unit_page(page)

    expected_labels = [
        "Customer",
        "Location",
        "Software Bundle",
        "PLC Code",
        "Installation Date",
        "Tier",
        "Disk Usage",
        "Bandwidth Usage",
    ]

    text = body_text(page)
    missing = [
        label for label in expected_labels
        if not re.search(re.escape(label), text, re.I)
    ]
    assert not missing, f"Missing fields: {', '.join(missing)}"
    assert UNIT_ID in text, f"Expected selected unit {UNIT_ID} to be displayed."


def test_events_link_opens_events_page(page: Page):
    go_to_unit_page(page)

    events_link = page.locator(
        "a[normalize-space()='Events'], a:has-text('Events')"
    ).first
    assert events_link.count() > 0, "Events hyperlink was not found."
    assert events_link.is_visible(), "Events hyperlink is not visible."

    href = (events_link.get_attribute("href") or "").lower()
    if href:
        assert "event" in href or "alarm" in href, (
            f"Unexpected Events link destination: {href!r}"
        )

    events_link.click()
    try:
        page.wait_for_url(re.compile(r".*(event|alarm).*", re.I), timeout=7000)
    except PlaywrightTimeoutError:
        current_url = page.url.lower()
        assert "event" in current_url or "alarm" in current_url, (
            f"Click did not navigate to Events/Alarms: {page.url}"
        )


def test_events_page_visual_comparison(page: Page):
    go_to_unit_page(page)

    page.get_by_role("link", name="Events", exact=True).click()
    page.wait_for_load_state("networkidle")

    baseline_path = "screenshots/baseline/SWR-1224_events.png"
    current_path = "screenshots/current/SWR-1224_events.png"
    os.makedirs(os.path.dirname(current_path), exist_ok=True)

    page.screenshot(path=current_path, full_page=True)
    verdict, report = evaluate_visual_changes(baseline_path, current_path)

    if verdict == "PASS":
        print("\nClicking the Events hyperlink in Unit Info page directs to Events page as expected.")
    else:
        print("\nSomething needs to be checked when clicking the Events hyperlink in Unit Info page.")
        pytest.fail(f"Visual regression detected:\n{report}")


@pytest.mark.parametrize("selected_count", [1, 3, 5])
def test_selected_unit_count_matches_chart_sections(page: Page, selected_count: int):
    go_to_unit_page(page)
    select_unit_count(page, selected_count)

    selected_units = get_selected_unit_values(page)
    assert len(selected_units) == selected_count, (
        f"Expected {selected_count} selected units, got {selected_units}."
    )

    chart_counts = get_chart_group_counts(page)
    for chart_name, chart_count in chart_counts.items():
        assert chart_count == selected_count, (
            f"Expected {selected_count} '{chart_name}' groups, but found {chart_count}."
        )

    print(f"[QA] Selected units: {selected_units}", flush=True)
    print(f"[QA] Chart groups: {chart_counts}", flush=True)


def test_weld_statistics_date_range_picker_opens(page: Page):
    go_to_unit_page(page)

    date_picker = page.locator(".ant-picker-range").first
    assert date_picker.count() > 0, "Date-range picker was not found."
    assert date_picker.is_visible(), "Date-range picker is not visible."
    date_picker.click()

    calendar = page.locator(".ant-picker-dropdown:visible").first
    calendar.wait_for(state="visible", timeout=5000)
    assert calendar.is_visible(), "Date-range calendar did not open."


def test_print_control_is_available(page: Page):
    go_to_unit_page(page)

    print_control = page.locator(
        "button[aria-label*='print' i], "
        "button[title*='print' i], "
        "button:has(.anticon-printer)"
    ).first

    assert print_control.count() > 0, "Print control was not found."
    assert print_control.is_visible(), "Print control is not visible."
    assert print_control.is_enabled(), "Print control is disabled."
