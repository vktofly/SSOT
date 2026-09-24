import asyncio
from playwright.async_api import async_playwright
import sys

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.set_viewport_size({"width": 1280, "height": 800})
        
        print("Navigating to http://localhost:8501...")
        await page.goto('http://localhost:8501')
        
        print("Waiting 5 seconds for load...")
        await page.wait_for_timeout(5000)
        
        print("Taking screenshot...")
        await page.screenshot(path='login_screen.png', full_page=True)
        print("Screenshot saved to login_screen.png")
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
