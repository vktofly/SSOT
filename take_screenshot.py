import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        # Set viewport for a desktop layout
        await page.set_viewport_size({"width": 1280, "height": 800})
        await page.goto('http://localhost:8501')
        # Wait for Streamlit to load
        await page.wait_for_selector('.stApp', timeout=15000)
        # Give some time for data/charts to render fully
        await page.wait_for_timeout(3000)
        await page.screenshot(path='screenshot.png', full_page=True)
        await browser.close()
        print("Screenshot saved to screenshot.png")

if __name__ == '__main__':
    asyncio.run(main())
