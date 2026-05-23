"""Test cases for the parser module."""

import pytest
from src.parser import DataParser


class TestDataParser:
    """Test suite for DataParser class."""

    @pytest.fixture
    def parser(self):
        """Create a DataParser instance for testing."""
        return DataParser()

    def test_initialization(self, parser):
        """Test DataParser initialization."""
        assert parser is not None
        assert parser.encoding == 'utf-8'

    def test_parse_html(self, parser):
        """Test HTML parsing."""
        html = "<html><head><title>Test</title></head><body>Content</body></html>"
        soup = parser.parse_html(html)
        assert soup.title.string == "Test"

    def test_clean_text(self, parser):
        """Test text cleaning."""
        dirty_text = "  Multiple   spaces   here  "
        clean = parser.clean_text(dirty_text)
        assert clean == "Multiple spaces here"

    def test_parse(self, parser):
        """Test generic parse method."""
        html = "<html><head><title>Test Page</title></head><body>Test content</body></html>"
        result = parser.parse(html)
        assert result['title'] == 'Test Page'
        assert 'content' in result
