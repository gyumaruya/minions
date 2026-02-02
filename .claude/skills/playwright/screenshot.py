#!/usr/bin/env python3
"""Playwright screenshot utility."""

import argparse
import asyncio
import sys
from pathlib import Path


async def take_screenshot(
    url: str,
    output: str = "screenshot.png",
    full_page: bool = False,
    width: int = 1280,
    height: int = 800,
    wait: float = 2.0,
) -> str:
    """Take a screenshot of the given URL.

    Args:
        url: URL to screenshot
        output: Output file path
        full_page: Whether to capture full page
        width: Viewport width in pixels
        height: Viewport height in pixels
        wait: Additional wait time in seconds after page load

    Returns:
        Absolute path to the saved screenshot
    """
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Error: playwright not installed. Run: uv add --dev playwright")
        sys.exit(1)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": width, "height": height})

        print(f"Loading: {url}")
        await page.goto(url)
        await page.wait_for_load_state("networkidle")

        if wait > 0:
            print(f"Waiting {wait} seconds for content to render...")
            await asyncio.sleep(wait)

        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print("Taking screenshot...")
        await page.screenshot(path=str(output_path), full_page=full_page)
        print(f"Screenshot saved: {output_path.absolute()}")

        await browser.close()
        return str(output_path.absolute())


def main():
    """Main entry point for screenshot utility."""
    parser = argparse.ArgumentParser(description="Take screenshot of a webpage")
    parser.add_argument("url", help="URL to screenshot")
    parser.add_argument(
        "-o",
        "--output",
        default="screenshot.png",
        help="Output path (default: screenshot.png)",
    )
    parser.add_argument(
        "--full-page",
        action="store_true",
        help="Capture full page instead of viewport only",
    )
    parser.add_argument(
        "--width",
        type=int,
        default=1280,
        help="Viewport width in pixels (default: 1280)",
    )
    parser.add_argument(
        "--height",
        type=int,
        default=800,
        help="Viewport height in pixels (default: 800)",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=2.0,
        help="Wait time in seconds after page load (default: 2.0)",
    )

    args = parser.parse_args()

    try:
        result = asyncio.run(
            take_screenshot(
                url=args.url,
                output=args.output,
                full_page=args.full_page,
                width=args.width,
                height=args.height,
                wait=args.wait,
            )
        )
        print(f"\n✓ Done: {result}")
    except Exception as e:
        print(f"\n✗ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
