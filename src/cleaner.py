"""Data cleaning and standardization module for Deep-Scan project."""

import re
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Known tech names that should keep their canonical casing
_CANONICAL_TECH: Dict[str, str] = {
    'python': 'Python',
    'vue.js': 'Vue.js',
    'vuejs': 'Vue.js',
    'react.js': 'React',
    'reactjs': 'React',
    'node.js': 'Node.js',
    'nodejs': 'Node.js',
    'typescript': 'TypeScript',
    'javascript': 'JavaScript',
    'postgresql': 'PostgreSQL',
    'postgres': 'PostgreSQL',
    'mongodb': 'MongoDB',
    'redis': 'Redis',
    'docker': 'Docker',
    'kubernetes': 'Kubernetes',
    'k8s': 'Kubernetes',
    'aws': 'AWS',
    'gcp': 'GCP',
    'azure': 'Azure',
    'graphql': 'GraphQL',
    'restful': 'REST',
    'rest': 'REST',
    'django': 'Django',
    'flask': 'Flask',
    'fastapi': 'FastAPI',
    'spring': 'Spring',
    'springboot': 'Spring Boot',
    'golang': 'Go',
    'rust': 'Rust',
    'c++': 'C++',
    'c#': 'C#',
    '.net': '.NET',
    'dotnet': '.NET',
    'tensorflow': 'TensorFlow',
    'pytorch': 'PyTorch',
    'mysql': 'MySQL',
    'sqlite': 'SQLite',
    'nginx': 'Nginx',
    'linux': 'Linux',
    'git': 'Git',
    'jenkins': 'Jenkins',
    'terraform': 'Terraform',
    'ansible': 'Ansible',
}

_NOISE_TERMS: set[str] = {
    'etc', 'etc.', 'good communication', 'good communication skills',
    'team player', 'self-motivated', 'self motivated', 'hardworking',
    'hard working', 'fast learner', 'detail oriented', 'detail-oriented',
    'excellent', 'strong', 'proficient', 'experienced', 'familiar',
    'basic', 'plus', 'nice to have', 'bonus', 'preferred',
    'other', 'others', 'various', 'related', 'relevant',
    'and', 'or', 'the',
}


class DataCleaner:
    """Cleans and standardizes crawled job data."""

    def clean_tech_stack(self, tech_stack: List[str]) -> List[str]:
        """
        Standardize a list of technology names.

        Trims whitespace, applies canonical casing, removes duplicates
        and filters out noise/irrelevant terms.
        """
        if not tech_stack:
            return []

        seen: set[str] = set()
        result: List[str] = []

        for item in tech_stack:
            cleaned = item.strip()
            if not cleaned:
                continue

            lower = cleaned.lower()
            if lower in _NOISE_TERMS or len(cleaned) < 2:
                continue

            canonical = _CANONICAL_TECH.get(lower, cleaned)
            if canonical.lower() not in seen:
                seen.add(canonical.lower())
                result.append(canonical)

        return result

    _SALARY_RE = re.compile(
        r'(?:(\d+(?:\.\d+)?)\s*[kK]\s*[-–—to]+\s*(\d+(?:\.\d+)?)\s*[kK])'   # k-range: 15k-25k
        r'|(\d+(?:\.\d+)?)\s*[kK]'                                                # single with k: 20k
        r'|(\d+(?:\.\d+)?)\s*[-–—to]+\s*(\d+(?:\.\d+)?)'                          # raw range: 150-200
        r'|(\d+(?:\.\d+)?)\s*\+\s*'                                                # floor: 250+
        r'|(\d+(?:\.\d+)?)'                                                        # lone number
    )

    @staticmethod
    def _parse_k(value: Optional[str]) -> Optional[int]:
        """Convert a k-suffix number string to int, returning None on failure."""
        if value is None:
            return None
        try:
            return int(float(value) * 1000)
        except (ValueError, TypeError):
            return None

    def parse_salary(self, raw_salary: Optional[str]) -> Dict[str, Optional[int]]:
        """
        Parse a raw salary string into min/max integer fields.

        Handles formats like: '150-200/天', '15k-25k', '20k', '15000-25000/月'.
        Returns {'salary_min': int, 'salary_max': int} with None for unparseable input.
        """
        result: Dict[str, Optional[int]] = {'salary_min': None, 'salary_max': None}
        if not raw_salary or not isinstance(raw_salary, str):
            return result

        match = self._SALARY_RE.search(raw_salary.strip())
        if not match:
            logger.debug(f'Could not parse salary from: {raw_salary!r}')
            return result

        # Groups: (1,2)=k-range, (3)=single-k, (4,5)=raw-range, (6)=floor, (7)=lone
        g1, g2, g3, g4, g5, g6, g7 = match.groups()

        if g1 is not None and g2 is not None:          # "15-25k"
            mn, mx = self._parse_k(g1), self._parse_k(g2)
            result['salary_min'], result['salary_max'] = mn, mx
        elif g3 is not None:                            # "20k"
            val = self._parse_k(g3)
            result['salary_min'] = result['salary_max'] = val
        elif g4 is not None and g5 is not None:         # "150-200"
            try:
                lo, hi = int(float(g4)), int(float(g5))
                result['salary_min'], result['salary_max'] = lo, hi
            except (ValueError, TypeError):
                pass
        elif g6 is not None:                            # "250+" → floor only, max=None
            try:
                result['salary_min'] = int(float(g6))
            except (ValueError, TypeError):
                pass
        elif g7 is not None:                            # "200"
            try:
                val = int(float(g7))
                result['salary_min'] = result['salary_max'] = val
            except (ValueError, TypeError):
                pass

        # Normalize: ensure min <= max
        if result['salary_min'] is not None and result['salary_max'] is not None:
            if result['salary_min'] > result['salary_max']:
                result['salary_min'], result['salary_max'] = (
                    result['salary_max'],
                    result['salary_min'],
                )

        return result

    def verify_record(self, record: Dict[str, Any]) -> bool:
        """Return True if the record passes validation (critical fields non-empty)."""
        title = record.get('title')

        if not title or not str(title).strip():
            return False
        return True

    def clean(self, records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Run all cleaning passes: verify, standardize tech stack, parse salary.

        Returns only records that pass verification.
        """
        cleaned: List[Dict[str, Any]] = []

        for rec in records:
            if not self.verify_record(rec):
                logger.debug('Dropping record with empty title/tech_stack: %r', rec.get('title'))
                continue

            rec = dict(rec)  # shallow copy — don't mutate caller's data

            if 'core_tech_stack' in rec:
                rec['core_tech_stack'] = self.clean_tech_stack(
                    rec['core_tech_stack'] if isinstance(rec['core_tech_stack'], list)
                    else [rec['core_tech_stack']]
                )
            else:
                rec['core_tech_stack'] = []

            if 'salary' in rec:
                parsed = self.parse_salary(rec.get('salary'))
                rec['salary_min'] = parsed['salary_min']
                rec['salary_max'] = parsed['salary_max']

            cleaned.append(rec)

        logger.info(f'Cleaned {len(cleaned)} / {len(records)} records')
        return cleaned
