"""Test cases for the scraper module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.scraper import InternshipScraper, TARGET_URL


class TestInternshipScraper:
    """Test suite for InternshipScraper class."""

    @pytest.fixture
    def scraper(self):
        return InternshipScraper(headless=True, timeout=30000)

    def test_initialization(self, scraper):
        assert scraper.url == TARGET_URL
        assert scraper.headless is True
        assert scraper.timeout == 30000
        assert scraper.page is None

    def test_default_url(self):
        s = InternshipScraper()
        assert s.url == TARGET_URL

    @pytest.mark.parametrize("raw, expected", [
        ("  hello   world  ", "hello world"),
        ("<span>Python</span>", "Python"),
        ("   ", ""),
        ("", ""),
    ])
    def test_clean_text(self, raw, expected):
        result = InternshipScraper._clean_text(raw)
        assert result == expected

    def test_extract_intern_item_blocks_empty(self):
        blocks = InternshipScraper._extract_intern_item_blocks("")
        assert blocks == []

    def test_parse_job_list_empty(self):
        jobs = InternshipScraper.parse_job_list("")
        assert jobs == []

    @pytest.mark.asyncio
    async def test_scrape_jobs_browser_lifecycle(self, scraper):
        """Integration-style test: verify start/stop are called."""
        with patch.object(scraper, 'start_browser', new_callable=AsyncMock) as mock_start, \
             patch.object(scraper, 'stop_browser', new_callable=AsyncMock) as mock_stop, \
             patch.object(scraper, 'navigate_to', new_callable=AsyncMock) as mock_nav, \
             patch.object(scraper, 'smooth_scroll', new_callable=AsyncMock) as mock_scroll, \
             patch.object(scraper, 'extract_jobs_via_playwright', new_callable=AsyncMock) as mock_extract:

            mock_extract.return_value = [
                {'title': 'Python Intern', 'company': 'ACME', 'salary': '3k', 'detail_url': '/job/1'}
            ]

            jobs = await scraper.scrape_jobs()

            mock_start.assert_called_once()
            mock_stop.assert_called_once()
            mock_nav.assert_called_once_with(TARGET_URL)
            assert len(jobs) >= 1
