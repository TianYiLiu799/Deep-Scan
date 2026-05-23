"""Data parser module for Deep-Scan project."""

import logging
import re

import os
from typing import List, Dict, Any
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class DataParser:
    """Data parser for extracting and cleaning web content."""

    def __init__(self, encoding: str = 'utf-8'):
        """
        Initialize the DataParser.

        Args:
            encoding: Text encoding to use
        """
        self.encoding = encoding

    def parse_html(self, html_content: str) -> BeautifulSoup:
        """
        Parse HTML content.

        Args:
            html_content: HTML content as string

        Returns:
            BeautifulSoup object
        """
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            logger.info("HTML content parsed successfully")
            return soup
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            raise

    def extract_data(
        self,
        html_content: str,
        selectors: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """
        Extract data from HTML using CSS selectors.

        Args:
            html_content: HTML content as string
            selectors: Dictionary mapping field names to CSS selectors

        Returns:
            List of dictionaries with extracted data
        """
        soup = self.parse_html(html_content)
        data = []

        try:
            elements = soup.select(list(selectors.values())[0])
            for element in elements:
                item = {}
                for field_name, selector in selectors.items():
                    extracted = element.select_one(selector)
                    item[field_name] = extracted.get_text(strip=True) if extracted else None
                data.append(item)
            logger.info(f"Extracted {len(data)} items")
        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            raise

        return data

    def parse(self, html_content: str) -> Dict[str, Any]:
        """
        Parse HTML content (stub method for subclassing).

        Args:
            html_content: HTML content as string

        Returns:
            Parsed data dictionary
        """
        soup = self.parse_html(html_content)
        return {
            'title': soup.title.string if soup.title else None,
            'content': soup.get_text()[:500],  # First 500 characters
        }

    def clean_text(self, text: str) -> str:
        """
        Clean and normalize text.

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text
        """
        return ' '.join(text.split())


class AIJobParser:
    """AI-powered job description parser."""

    def __init__(self):
        """Initialize the AI job parser."""
        self.api_key = os.getenv('OPENAI_API_KEY', '')
        self.use_ai = bool(self.api_key)
        self._client = None
        if self.use_ai:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
            logger.info('AI Job Parser initialized with API key')
        else:
            logger.warning('AI Job Parser will use regex fallback (no OPENAI_API_KEY found)')

    async def parse_jd(self, job_description: str) -> Dict[str, Any]:
        """
        Parse job description using AI or regex fallback.

        Args:
            job_description: Raw job description text

        Returns:
            Dictionary with parsed job fields
        """
        if not job_description:
            return {}

        try:
            if self.use_ai:
                return await self._parse_with_ai(job_description)
            else:
                return self._parse_with_regex(job_description)
        except Exception as exc:
            logger.warning(f'AI parsing failed: {exc}, using regex fallback')
            return self._parse_with_regex(job_description)

    async def _parse_with_ai(self, job_description: str) -> Dict[str, Any]:
        """Parse using OpenAI Async client."""
        response = await self._client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[
                {
                    'role': 'system',
                    'content': 'You are a job description parser. Extract structured data from job descriptions in JSON format.'
                },
                {
                    'role': 'user',
                    'content': f'Parse this job description and extract: skills (list), experience_level, employment_type, location. Return as JSON:\n\n{job_description[:2000]}'
                }
            ],
            temperature=0.3,
            timeout=10,
        )

        import json
        raw = response.choices[0].message.content
        if not raw:
            raise ValueError('OpenAI returned empty response content')
        result = json.loads(raw)
        return {
            'core_tech_stack': result.get('skills', []),
            'experience_level': result.get('experience_level', ''),
            'employment_type': result.get('employment_type', ''),
            'location': result.get('location', ''),
        }

    @staticmethod
    def _parse_with_regex(job_description: str) -> Dict[str, Any]:
        """Regex-based fallback parsing."""
        result = {}

        # Extract required skills (common keywords)
        skill_patterns = [
            r'(?:技能|Skills?|Required|Experience with)[:\s]+([^。，,;]+)',
            r'(?:精通|熟悉|掌握)[:\s]*([^。，,;]+)',
        ]
        skills = []
        for pattern in skill_patterns:
            matches = re.findall(pattern, job_description, re.IGNORECASE)
            skills.extend(matches)
        result['core_tech_stack'] = [s.strip() for s in skills[:5]] if skills else []

        # Extract work location
        location_pattern = r'(?:地点|Location|工作地点)[:\s]*([^。，,;]+)'
        location_match = re.search(location_pattern, job_description, re.IGNORECASE)
        result['location'] = location_match.group(1).strip() if location_match else ''

        # Extract employment type
        employment_patterns = ['全职', '兼职', '实习', 'Full-time', 'Part-time', 'Internship']
        for emp in employment_patterns:
            if emp in job_description:
                result['employment_type'] = emp
                break
        if 'employment_type' not in result:
            result['employment_type'] = ''

        # Extract experience level
        exp_levels = ['junior', 'senior', '初级', '中级', '高级', 'entry', 'mid-level']
        result['experience_level'] = ''
        for level in exp_levels:
            if level.lower() in job_description.lower():
                result['experience_level'] = level
                break

        return result
