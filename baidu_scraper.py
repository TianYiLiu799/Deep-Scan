"""
Asynchronous Playwright script for web scraping.

This script demonstrates best practices for async/await usage with Playwright:
- Headless Chromium browser launch
- Async context managers for resource management
- Error handling and logging
- Screenshots to data folder
"""

import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BaiduScraper:
    """Asynchronous web scraper for Baidu using Playwright."""

    def __init__(
        self,
        screenshot_dir: str = "data",
        headless: bool = True,
        timeout: int = 30000
    ):
        """
        Initialize the Baidu scraper.

        Args:
            screenshot_dir: Directory to save screenshots
            headless: Run browser in headless mode
            timeout: Default timeout in milliseconds
        """
        self.screenshot_dir = Path(screenshot_dir)
        self.headless = headless
        self.timeout = timeout
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None

        # Ensure screenshot directory exists
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Screenshot directory set to: {self.screenshot_dir.absolute()}")

    async def launch_browser(self) -> None:
        """Launch the Chromium browser in headless mode."""
        try:
            playwright = await async_playwright().start()
            self.browser = await playwright.chromium.launch(headless=self.headless)
            logger.info("Chromium browser launched successfully (headless mode)")
        except Exception as e:
            logger.error(f"Failed to launch browser: {e}")
            raise

    async def create_context(self) -> None:
        """Create a new browser context."""
        if not self.browser:
            raise RuntimeError("Browser not launched. Call launch_browser() first.")
        try:
            self.context = await self.browser.new_context()
            logger.info("Browser context created")
        except Exception as e:
            logger.error(f"Failed to create context: {e}")
            raise

    async def create_page(self) -> None:
        """Create a new page in the current context."""
        if not self.context:
            raise RuntimeError("Context not created. Call create_context() first.")
        try:
            self.page = await self.context.new_page()
            self.page.set_default_timeout(self.timeout)
            logger.info("New page created")
        except Exception as e:
            logger.error(f"Failed to create page: {e}")
            raise

    async def navigate_to_baidu(self) -> None:
        """Navigate to Baidu homepage."""
        if not self.page:
            raise RuntimeError("Page not created. Call create_page() first.")
        try:
            logger.info("Navigating to https://www.baidu.com...")
            await self.page.goto("https://www.baidu.com", wait_until="networkidle")
            logger.info("Successfully navigated to Baidu")
        except Exception as e:
            logger.error(f"Failed to navigate to Baidu: {e}")
            raise

    async def get_page_title(self) -> str:
        """
        Get the page title.

        Returns:
            Page title string
        """
        if not self.page:
            raise RuntimeError("Page not available.")
        try:
            title = await self.page.title()
            logger.info(f"Page title: {title}")
            return title
        except Exception as e:
            logger.error(f"Failed to get page title: {e}")
            raise

    async def take_screenshot(self) -> Path:
        """
        Take a screenshot and save it to the data folder.

        Returns:
            Path to the saved screenshot
        """
        if not self.page:
            raise RuntimeError("Page not available.")
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"baidu_screenshot_{timestamp}.png"
            filepath = self.screenshot_dir / filename

            await self.page.screenshot(path=str(filepath))
            logger.info(f"Screenshot saved to: {filepath.absolute()}")
            return filepath
        except Exception as e:
            logger.error(f"Failed to take screenshot: {e}")
            raise

    async def close_browser(self) -> None:
        """Close the browser and clean up resources."""
        try:
            if self.page:
                await self.page.close()
                logger.info("Page closed")
            if self.context:
                await self.context.close()
                logger.info("Context closed")
            if self.browser:
                await self.browser.close()
                logger.info("Browser closed")
        except Exception as e:
            logger.error(f"Error during browser cleanup: {e}")
            raise

    async def run(self) -> None:
        """
        Execute the complete scraping workflow.

        This method demonstrates proper async/await usage with
        resource cleanup via context managers.
        """
        try:
            # Launch browser
            await self.launch_browser()

            # Create context and page
            await self.create_context()
            await self.create_page()

            # Navigate to Baidu
            await self.navigate_to_baidu()

            # Get and print page title
            title = await self.get_page_title()
            print(f"\n{'='*50}")
            print(f"Page Title: {title}")
            print(f"{'='*50}\n")

            # Take screenshot
            screenshot_path = await self.take_screenshot()
            print(f"Screenshot saved to: {screenshot_path.absolute()}\n")

            logger.info("Scraping completed successfully")

        finally:
            # Ensure browser is closed even if errors occur
            await self.close_browser()


async def main() -> None:
    """Main entry point with proper async context management."""
    scraper = BaiduScraper(screenshot_dir="data", headless=True)
    await scraper.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Script interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
