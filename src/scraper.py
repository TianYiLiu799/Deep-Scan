"""Cloud-native scraper — requests + DeepSeek LLM, zero browser dependencies."""

import json
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import requests as http_requests
from openai import OpenAI

# ── Import DataCleaner (same fallback chain as before) ────────────────────────
if __name__ == '__main__' or os.path.basename(os.getcwd()) == 'Deep-Scan':
    parent_dir = os.path.dirname(os.path.dirname(__file__))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

try:
    from .cleaner import DataCleaner
except ImportError:
    try:
        from src.cleaner import DataCleaner
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "cleaner", os.path.join(os.path.dirname(__file__), 'cleaner.py'))
        cleaner_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cleaner_module)
        DataCleaner = cleaner_module.DataCleaner

logger = logging.getLogger(__name__)

TARGET_URL = 'https://www.shixiseng.com/interns?k=Python&c=全国'

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/125.0.0.0 Safari/537.36'
    ),
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
}

LISTING_PROMPT = """You are a precise HTML data extractor. Given the HTML source of a Chinese job board page (实习僧 shixiseng.com) showing Python internship listings, extract ALL job postings into a JSON object.

Return ONLY valid JSON in this exact format (no markdown, no code fences):
{
  "jobs": [
    {
      "title": "job title text in Chinese",
      "company": "company name in Chinese",
      "salary": "salary text exactly as shown (e.g. 120-150/天, 200-300/天, or the original format)",
      "detail_url": "full absolute URL to the job detail page"
    }
  ],
  "has_next_page": true,
  "next_page_url": "absolute URL for the next page, or null"
}

Critical rules:
- Extract EVERY job card visible in the HTML. Do not skip any.
- Preserve original Chinese text exactly — do not translate or summarize.
- If detail_url is relative, prepend "https://www.shixiseng.com".
- Look for job data in any form: HTML attributes, <script> JSON blobs, data-* attributes, SSR-rendered cards.
- If absolutely no job data is found, return {"jobs": [], "has_next_page": false, "next_page_url": null}."""

DETAIL_PROMPT = """You are a precise Chinese job description parser. Given the HTML source of a Python internship job detail page from 实习僧 (shixiseng.com), extract structured information.

Return ONLY valid JSON (no markdown, no code fences):
{
  "description": "the full job description text in Chinese, cleaned of HTML tags, concatenated into one paragraph (keep ALL Chinese content — responsibilities, requirements, company intro)",
  "core_tech_stack": ["Python", "Django", "MySQL", ...],
  "experience_level": "初级/中级/高级 or empty string",
  "employment_type": "实习/全职/兼职 or empty string",
  "location": "city and district in Chinese (e.g. 北京市/海淀区), or empty string"
}

Rules for core_tech_stack:
- Extract ALL technologies, frameworks, databases, tools mentioned as required OR preferred skills.
- Use canonical English names: "Python", "Django", "Flask", "FastAPI", "JavaScript", "TypeScript", "React", "Vue.js", "Node.js", "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch", "Docker", "Kubernetes", "Linux", "Git", "AWS", "GCP", "Azure", "NLP", "TensorFlow", "PyTorch", "Scrapy", "Selenium", "HTML", "CSS", "SQL", "Shell", "Java", "Go", "C++", "Rust", "REST", "GraphQL", "Nginx", "Jenkins", "Kafka", "Spark", "Hadoop", "AI", "Machine Learning", "OpenCV", "Keras", "RPA", "OCR".
- Only list technologies explicitly referenced in the job description.
- Return [] if no technologies can be identified.
- Do NOT include generic soft skills (沟通能力, 团队合作, etc.) — only technical keywords."""

SALARY_FIX_PROMPT = """Extract the daily salary range from this Chinese job listing HTML. Look for patterns like "120-150/天", "200-300/天", "150元/天".

Return ONLY valid JSON:
{
  "salary_raw": "120-150/天"
}

If no salary number is found, return {"salary_raw": ""}."""


class CloudScraper:
    """Lightweight cloud-native scraper: requests for HTTP, DeepSeek LLM for extraction."""

    def __init__(self):
        api_key = os.getenv('OPENAI_API_KEY', '')
        base_url = os.getenv('OPENAI_BASE_URL', 'https://api.openai.com/v1')
        self.model = os.getenv('OPENAI_MODEL', 'deepseek-chat')
        self.use_ai = bool(api_key)
        if self.use_ai:
            self.client = OpenAI(api_key=api_key, base_url=base_url, timeout=90)
        else:
            self.client = None
        self.cleaner = DataCleaner()

    # ── HTTP ──────────────────────────────────────────────────────────────

    @staticmethod
    def _fetch(url: str, max_retries: int = 3) -> Optional[str]:
        """Fetch URL with retry + backoff. Returns decoded HTML or None."""
        for attempt in range(max_retries):
            try:
                resp = http_requests.get(url, headers=HEADERS, timeout=30)
                resp.raise_for_status()
                resp.encoding = resp.apparent_encoding or 'utf-8'
                return resp.text
            except Exception as exc:
                logger.warning('Fetch %d/%d failed [%s]: %s',
                               attempt + 1, max_retries, url[:80], exc)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
        return None

    # ── LLM ───────────────────────────────────────────────────────────────

    def _call_llm(self, system_prompt: str, user_content: str) -> Dict[str, Any]:
        """Send content to LLM, return parsed JSON dict."""
        if not self.client:
            raise RuntimeError('No API key — set OPENAI_API_KEY')

        # Trim HTML to stay within token budget while keeping head + tail
        limit = 24000
        if len(user_content) > limit:
            user_content = (
                user_content[:limit * 3 // 4] +
                '\n…[truncated]…\n' +
                user_content[-limit // 4:]
            )

        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_content},
            ],
            temperature=0.1,
            response_format={'type': 'json_object'},
        )
        raw = response.choices[0].message.content
        if not raw:
            raise ValueError('LLM returned empty response')
        return json.loads(raw)

    # ── Extraction ────────────────────────────────────────────────────────

    def scrape_listings(self, html: str) -> Tuple[List[Dict], bool]:
        """Return (jobs, has_next_page) from a listing page HTML."""
        result = self._call_llm(LISTING_PROMPT, html)
        jobs = result.get('jobs', [])
        has_next = result.get('has_next_page', False)
        logger.info('LLM extracted %d jobs (has_next=%s)', len(jobs), has_next)
        return jobs, has_next

    def scrape_detail(self, html: str) -> Dict[str, Any]:
        """Extract structured fields from a detail page HTML."""
        result = self._call_llm(DETAIL_PROMPT, html)
        return {
            'description': result.get('description', ''),
            'core_tech_stack': result.get('core_tech_stack', []),
            'experience_level': result.get('experience_level', ''),
            'employment_type': result.get('employment_type', ''),
            'location': result.get('location', ''),
        }

    def fix_salary(self, html: str) -> str:
        """Second-pass LLM call to extract exact salary string from detail HTML."""
        try:
            result = self._call_llm(SALARY_FIX_PROMPT, html)
            return result.get('salary_raw', '')
        except Exception:
            return ''

    # ── Orchestrator ──────────────────────────────────────────────────────

    def run(self, max_pages: int = 3, detail_limit: int = 20) -> None:
        """Full pipeline: list → detail → clean → save."""
        if not self.use_ai:
            print('[FATAL] OPENAI_API_KEY not set — cloud scraper requires LLM.')
            sys.exit(1)

        os.makedirs('data', exist_ok=True)
        print('\n🐍 Deep-Scan Cloud Scraper  (requests + LLM)\n')

        # ═══ Phase 1: Scrape listing pages ═══════════════════════════════
        all_jobs: List[Dict[str, Any]] = []

        for page in range(1, max_pages + 1):
            url = f'{TARGET_URL}&p={page}' if page > 1 else TARGET_URL
            print(f'{"=" * 50}')
            print(f'  📄 第 {page} 页')
            print(f'{"=" * 50}')

            html = self._fetch(url)
            if not html:
                logger.warning('页面 %d 获取失败，停止翻页', page)
                break

            try:
                page_jobs, has_next = self.scrape_listings(html)
            except Exception as exc:
                logger.error('LLM 提取第 %d 页失败: %s', page, exc)
                break

            all_jobs.extend(page_jobs)
            for j in page_jobs:
                print(f'  📌 {j.get("title", "?")[:45]}')
                print(f'     🏢 {j.get("company", "?")}  |  💰 {j.get("salary", "?")}')

            logger.info('第 %d 页: %d 条', page, len(page_jobs))
            if not has_next:
                break
            time.sleep(1)

        print(f'\n  ✅ 列表抓取完成: {len(all_jobs)} 条职位\n')
        save_jobs_to_json(all_jobs, 'data/jobs.json')

        if not all_jobs:
            print('[DONE] 无职位数据，流水线结束。')
            return

        # ═══ Phase 2: Detail pages + checkpoint resuming ═════════════════
        print(f'{"=" * 50}')
        print(f'  🔍 抓取详情页 (最多 {detail_limit} 条)')
        print(f'{"=" * 50}\n')

        detailed_path = 'data/jobs_detailed.json'
        enriched: List[Dict[str, Any]] = []
        scraped_urls: set = set()
        if os.path.exists(detailed_path):
            with open(detailed_path, 'r', encoding='utf-8') as f:
                enriched = json.load(f)
            scraped_urls = {
                j.get('detail_url', '') for j in enriched if j.get('detail_url')
            }
            logger.info('断点续传: 已加载 %d 条已处理 URL', len(scraped_urls))

        for idx, job in enumerate(all_jobs[:detail_limit]):
            detail_url = job.get('detail_url', '')
            if not detail_url:
                logger.warning('[%d/%d] 缺少 URL，跳过', idx + 1, detail_limit)
                continue
            if detail_url in scraped_urls:
                print(f'  ⏭️ 跳过 (已处理): {detail_url[:70]}...')
                continue

            try:
                logger.info('[%d/%d] %s', idx + 1, detail_limit, detail_url[:70])
                time.sleep(1.2)  # polite rate-limit

                html = self._fetch(detail_url)
                if not html:
                    logger.warning('  ⚠️ 详情页获取失败，继续下一条')
                    job['description'] = ''
                    job['core_tech_stack'] = []
                    enriched.append(job)
                    scraped_urls.add(detail_url)
                    continue

                # LLM extraction
                detail = self.scrape_detail(html)
                job['description'] = detail['description']
                job['core_tech_stack'] = detail['core_tech_stack']
                job['experience_level'] = detail['experience_level']
                job['employment_type'] = detail['employment_type']
                job['location'] = detail['location']

                # If salary field is empty or non-numeric, ask LLM to find it
                raw_sal = job.get('salary', '')
                if not raw_sal or not any(c.isdigit() for c in raw_sal):
                    fixed = self.fix_salary(html)
                    if fixed:
                        job['salary'] = fixed

                logger.info('  ✓ 技能: %s', job.get('core_tech_stack', []))
                enriched.append(job)
                scraped_urls.add(detail_url)

                # Checkpoint save after every detail
                with open(detailed_path, 'w', encoding='utf-8') as f:
                    json.dump(enriched, f, ensure_ascii=False, indent=2)

            except Exception as exc:
                logger.error('  ✗ 详情页失败 [%s]: %s', detail_url[:70], exc)
                job['description'] = ''
                job['core_tech_stack'] = []
                enriched.append(job)
                scraped_urls.add(detail_url)

        save_jobs_to_json(enriched, 'data/jobs_detailed.json')
        print(f'\n  ✅ 详情抓取完成: {len(enriched)} 条\n')

        # ═══ Phase 3: Clean ══════════════════════════════════════════════
        cleaned = self.cleaner.clean(enriched)
        save_jobs_to_json(cleaned, 'data/jobs_cleaned.json')
        print(f'🧹 清洗完成: {len(enriched)} → {len(cleaned)} 条有效记录')


# ── Save helpers ──────────────────────────────────────────────────────────────

def save_jobs_to_json(jobs: List[Dict], filepath: str = 'data/jobs.json') -> None:
    dir_path = os.path.dirname(filepath)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    print(f'🎉 已保存: {filepath} ({len(jobs)} 条)')


# ── CLI entry ────────────────────────────────────────────────────────────────

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
    )
    try:
        CloudScraper().run(max_pages=3, detail_limit=20)
    except KeyboardInterrupt:
        logger.warning('用户中断 (Ctrl+C)')


if __name__ == '__main__':
    main()
