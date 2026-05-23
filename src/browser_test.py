"""Browser testing module for Deep-Scan project using Playwright."""

import asyncio
import logging
from typing import Optional, List, Dict, Any
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright
from playwright_stealth import Stealth

logger = logging.getLogger(__name__)


class BrowserTest:
    """Browser automation and testing class using Playwright."""

    def __init__(self, headless: bool = True, timeout: int = 60000):
        """
        Initialize BrowserTest.

        Args:
            headless: Run browser in headless mode
            timeout: Default timeout in milliseconds
        """
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright: Optional[Playwright] = None
        self.stealth = Stealth()

    async def start_browser(self) -> None:
        """Start the browser with stealth enabled."""
        try:
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=self.headless)
            self.context = await self.browser.new_context()

            # Apply stealth to context and popups
            await self.stealth.apply_stealth_async(self.context)
            self.context.on("page", lambda page: asyncio.create_task(self.apply_stealth(page)))

            self.page = await self.context.new_page()
            await self.apply_stealth(self.page)
            logger.info("Browser started successfully")
        except Exception as e:
            logger.error(f"Error starting browser: {e}")
            raise

    async def apply_stealth(self, page: Page) -> None:
        """Apply Playwright stealth patches to a page."""
        try:
            await self.stealth.apply_stealth_async(page)
            logger.info("Stealth applied to page")
        except Exception as e:
            logger.error(f"Error applying stealth: {e}")
            raise

    async def stop_browser(self) -> None:
        """Stop the browser."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            logger.info("Browser stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping browser: {e}")
            raise

    async def navigate_to(self, url: str) -> None:
        """
        Navigate to a URL.

        Args:
            url: URL to navigate to
        """
        if not self.page:
            raise RuntimeError("Browser not started. Call start_browser() first.")
        try:
            await self.page.goto(url, timeout=self.timeout, wait_until="domcontentloaded")
            try:
                await self.page.wait_for_load_state("networkidle", timeout=10000)
            except Exception as e:
                logger.warning(f"Network idle wait timed out for {url}: {e}")
            logger.info(f"Navigated to {url}")
        except Exception as e:
            logger.error(f"Error navigating to {url}: {e}")
            raise

    async def get_page_title(self) -> str:
        """
        Get the page title.

        Returns:
            Page title
        """
        if not self.page:
            raise RuntimeError("Browser not started.")
        try:
            title = await self.page.title()
            logger.info(f"Page title: {title}")
            return title
        except Exception as e:
            logger.error(f"Error getting page title: {e}")
            raise

    async def get_page_content(self) -> str:
        """
        Get the full page HTML content.

        Returns:
            Page HTML content
        """
        if not self.page:
            raise RuntimeError("Browser not started.")
        try:
            content = await self.page.content()
            logger.info("Page content retrieved")
            return content
        except Exception as e:
            logger.error(f"Error getting page content: {e}")
            raise

    async def find_elements(self, selector: str) -> List[str]:
        """
        Find elements by CSS selector.

        Args:
            selector: CSS selector

        Returns:
            List of element contents
        """
        if not self.page:
            raise RuntimeError("Browser not started.")
        try:
            elements = await self.page.query_selector_all(selector)
            contents = []
            for element in elements:
                text = await element.text_content()
                if text:
                    contents.append(text.strip())
            logger.info(f"Found {len(contents)} elements with selector {selector}")
            return contents
        except Exception as e:
            logger.error(f"Error finding elements: {e}")
            raise

    async def click_element(self, selector: str) -> None:
        """
        Click an element.

        Args:
            selector: CSS selector of the element
        """
        if not self.page:
            raise RuntimeError("Browser not started.")
        try:
            await self.page.click(selector)
            logger.info(f"Clicked element: {selector}")
        except Exception as e:
            logger.error(f"Error clicking element: {e}")
            raise

    async def fill_input(self, selector: str, text: str) -> None:
        """
        Fill an input field.

        Args:
            selector: CSS selector of the input field
            text: Text to fill
        """
        if not self.page:
            raise RuntimeError("Browser not started.")
        try:
            await self.page.fill(selector, text)
            logger.info(f"Filled input {selector} with: {text}")
        except Exception as e:
            logger.error(f"Error filling input: {e}")
            raise

    async def wait_for_selector(self, selector: str, timeout: Optional[int] = None) -> None:
        """
        Wait for an element to appear.

        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds
        """
        if not self.page:
            raise RuntimeError("Browser not started.")
        try:
            await self.page.wait_for_selector(selector, timeout=timeout or self.timeout)
            logger.info(f"Element appeared: {selector}")
        except Exception as e:
            logger.error(f"Error waiting for selector: {e}")
            raise

    async def take_screenshot(self, filepath: str) -> None:
        """
        Take a screenshot.

        Args:
            filepath: Path to save the screenshot
        """
        if not self.page:
            raise RuntimeError("Browser not started.")
        try:
            await self.page.screenshot(path=filepath)
            logger.info(f"Screenshot saved to {filepath}")
        except Exception as e:
            logger.error(f"Error taking screenshot: {e}")
            raise

    async def get_metadata(self) -> Dict[str, Any]:
        """
        Get page metadata.

        Returns:
            Dictionary with page metadata
        """
        if not self.page:
            raise RuntimeError("Browser not started.")
        try:
            title = await self.page.title()
            url = self.page.url
            metadata = {
                'title': title,
                'url': url,
                'user_agent': await self.page.evaluate('navigator.userAgent'),
            }
            logger.info("Metadata retrieved")
            return metadata
        except Exception as e:
            logger.error(f"Error getting metadata: {e}")
            raise


async def main():
    """Example usage of BrowserTest."""
    browser_test = BrowserTest(headless=True)
    try:
        await browser_test.start_browser()
        await browser_test.navigate_to("https://news.ycombinator.com")
        
        title = await browser_test.get_page_title()
        print(f"Page Title: {title}")
        
        metadata = await browser_test.get_metadata()
        print(f"Metadata: {metadata}")
        
        await browser_test.take_screenshot("data/hn_homepage.png")
    finally:
        await browser_test.stop_browser()


if __name__ == "__main__":
    asyncio.run(main())
