import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto('http://localhost:8501')
        await page.wait_for_selector('.stApp', timeout=15000)
        await page.wait_for_timeout(3000)
        
        # Get the outer HTML of the sidebar toggle button wrapper
        html = await page.evaluate('''() => {
            const el = document.querySelector('[data-testid="collapsedControl"]');
            return el ? el.outerHTML : "Not found";
        }''')
        print("Collapsed Control:", html)
        
        # Also check anything containing 'keyboard_double'
        html2 = await page.evaluate('''() => {
            const els = Array.from(document.querySelectorAll('*'));
            const el = els.find(e => e.textContent && e.textContent.includes('keyboard_double') && e.children.length === 0);
            return el ? el.outerHTML : "Not found";
        }''')
        print("Element with text:", html2)
        
        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
