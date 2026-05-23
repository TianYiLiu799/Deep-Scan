"""Browser-powered scraper for Interns listings on shixiseng.com."""

import asyncio
import html
import json
import logging
import os
import re
import sys
from typing import Any, Dict, List, Optional

# 支持两种运行方式：直接运行或作为模块导入
if __name__ == '__main__' or os.path.basename(os.getcwd()) == 'Deep-Scan':
    # 直接运行时，添加顶层项目目录到 sys.path
    parent_dir = os.path.dirname(os.path.dirname(__file__))
    if parent_dir not in sys.path:
        sys.path.insert(0, parent_dir)

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

# 尝试相对导入，失败时尝试绝对导入
try:
    from .cleaner import DataCleaner
except ImportError:
    try:
        from src.cleaner import DataCleaner
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location("cleaner", os.path.join(os.path.dirname(__file__), 'cleaner.py'))
        cleaner_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cleaner_module)
        DataCleaner = cleaner_module.DataCleaner

try:
    from .parser import AIJobParser
except ImportError:
    try:
        from src.parser import AIJobParser
    except ImportError:
        import importlib.util
        spec = importlib.util.spec_from_file_location("parser", os.path.join(os.path.dirname(__file__), 'parser.py'))
        parser_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(parser_module)
        AIJobParser = parser_module.AIJobParser

try:
    from playwright_stealth import Stealth
except ImportError:
    Stealth = None  # type: ignore

logger = logging.getLogger(__name__)

TARGET_URL = 'https://www.shixiseng.com/interns?k=Python&c=全国'

# Multiple candidate selectors so we don't rely on a single guess
NEXT_PAGE_CANDIDATES = [
    '.el-pagination .btn-next',
    '.pagination .next',
    '.pagination li.next',
    'button:has-text("下一页")',
    'a:has-text("下一页")',
    '.el-icon-arrow-right',
    '[class*="pagination"] [class*="next"]',
    'li.next:not(.disabled)',
]


class InternshipScraper:
    """Browser scraper for shixiseng internship listings."""

    def __init__(self, url: str = TARGET_URL, headless: bool = False, timeout: int = 60000):
        self.url = url
        self.headless = headless
        self.timeout = timeout
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.stealth = Stealth() if Stealth is not None else None
        self.parser = AIJobParser()

    # ── browser lifecycle ────────────────────────────────────────────

    async def start_browser(self) -> None:
        self.playwright = await async_playwright().start()
        try:
            self.browser = await self.playwright.chromium.launch(headless=self.headless)
            self.context = await self.browser.new_context()
            if self.stealth is not None:
                await self.stealth.apply_stealth_async(self.context)
            self.page = await self.context.new_page()
            if self.stealth is not None:
                await self.stealth.apply_stealth_async(self.page)
        except Exception:
            await self.stop_browser()
            raise
        logger.info('浏览器已启动  headless=%s', self.headless)

    async def stop_browser(self) -> None:
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        logger.info('浏览器已关闭')

    # ── navigation ───────────────────────────────────────────────────

    async def navigate_to(self, url: str) -> None:
        if not self.page:
            raise RuntimeError('Browser not started')
        logger.info('正在打开 %s ...', url)
        await self.page.goto(url, timeout=self.timeout, wait_until='domcontentloaded')
        try:
            await self.page.wait_for_load_state('networkidle', timeout=20000)
        except Exception as exc:
            logger.warning('网络未完全空闲: %s', exc)
        logger.info('页面加载完成')

    # ── scroll ───────────────────────────────────────────────────────

    async def smooth_scroll(self, steps: int = 6, delay_ms: int = 250) -> None:
        """Gradually scroll down the page to trigger lazy-loading and look cool."""
        if not self.page:
            return
        for i in range(1, steps + 1):
            await self.page.evaluate(
                f'window.scrollTo({{top: document.body.scrollHeight * {i / steps}, behavior: "smooth"}})'
            )
            await self.page.wait_for_timeout(delay_ms)
        # final nudge to absolute bottom
        await self.page.evaluate('window.scrollTo({top: document.body.scrollHeight, behavior: "smooth"})')
        await self.page.wait_for_timeout(600)
        logger.info('页面滚动完成')

    # ── pagination helpers ───────────────────────────────────────────

    async def _find_next_button(self):
        """Try every candidate selector; return the first visible match."""
        if not self.page:
            return None
        for sel in NEXT_PAGE_CANDIDATES:
            try:
                el = await self.page.query_selector(sel)
                if el and await el.is_visible():
                    return el
            except Exception:
                continue
        return None

    async def _wait_for_item_refresh(self, prev_count: int, timeout_ms: int = 10000) -> bool:
        """Spin until the DOM item count differs from prev_count (real page flip)."""
        if not self.page:
            return False
        deadline = asyncio.get_running_loop().time() + timeout_ms / 1000
        while asyncio.get_running_loop().time() < deadline:
            items = await self.page.query_selector_all('.intern-item, .intern-wrap, [class*="intern-item"]')
            if len(items) != prev_count and len(items) > 0:
                return True
            await self.page.wait_for_timeout(400)
        return False

    # ── extraction ───────────────────────────────────────────────────

    def get_page_content(self) -> str:
        """Synchronous wrapper — call only inside an async context after awaiting."""
        raise RuntimeError('Use extract_jobs_via_playwright() instead; '
                           'call get_page_content_str() if you need raw HTML.')

    async def get_page_content_str(self) -> str:
        if not self.page:
            raise RuntimeError('Browser not started')
        return await self.page.content()

    @staticmethod
    def _clean_text(raw: str) -> str:
        text = html.unescape(raw or '')
        text = re.sub(r'<[^>]+>', '', text)
        return re.sub(r'\s+', ' ', text).strip()

    # ── DOM-based extraction (primary – much more reliable) ──────────

    async def extract_jobs_via_playwright(self) -> List[Dict[str, Any]]:
        """Scrape job cards via Playwright query selectors, parsing live DOM."""
        if not self.page:
            return []

        items = await self.page.query_selector_all(
            '.intern-item, .intern-wrap, [class*="intern-item"]'
        )
        logger.info('  当前页找到 %d 个职位卡片', len(items))

        jobs: List[Dict[str, Any]] = []
        for item in items:
            try:
                data = await item.evaluate('''el => {
                    const getText = (sel) => {
                        const n = el.querySelector(sel);
                        return n ? n.textContent.trim() : '';
                    };
                    const getHref = (sel) => {
                        const n = el.querySelector(sel);
                        return n ? (n.href || n.getAttribute('href') || '') : '';
                    };

                    // try common class patterns on shixiseng
                    const title = getText('.title a, .intern-detail__job .title, a.title, [class*="job"] a.title');
                    const company = getText('.intern-detail__company .title, [class*="company"] a.title');
                    const salary = getText('.tip, .salary, [class*="salary"], .intern-detail__job .tip, .wage');
                    const detailUrl = getHref('.title a, a.title, [class*="job"] a.title');

                    return {title, company, salary, detail_url: detailUrl};
                }''')

                job = {
                    'title': self._clean_text(data.get('title', '')),
                    'company': self._clean_text(data.get('company', '')),
                    'salary': self._clean_text(data.get('salary', '')),
                    'detail_url': data.get('detail_url', ''),
                }
                if job['title']:
                    jobs.append(job)
            except Exception as exc:
                logger.debug('  跳过一条解析失败的卡片: %s', exc)
                continue

        return jobs

    # ── regex-based extraction (fallback) ────────────────────────────

    @staticmethod
    def _extract_intern_item_blocks(page_content: str) -> List[str]:
        blocks: List[str] = []
        position = 0
        while True:
            found = page_content.find('class="intern-wrap interns-point intern-item"', position)
            if found == -1:
                found = page_content.find("class='intern-wrap interns-point intern-item'", position)
            if found == -1:
                break

            div_start = page_content.rfind('<div', 0, found)
            if div_start == -1:
                position = found + 40
                continue

            depth = 0
            index = div_start
            while index < len(page_content):
                if page_content.startswith('<div', index):
                    depth += 1
                    index += 4
                elif page_content.startswith('</div>', index):
                    depth -= 1
                    index += 6
                    if depth == 0:
                        blocks.append(page_content[div_start:index])
                        position = index
                        break
                else:
                    index += 1
            else:
                break
        return blocks

    @classmethod
    def parse_job_list(cls, page_content: str) -> List[Dict[str, Any]]:
        """Regex-based fallback when Playwright selectors don't match."""
        item_blocks = cls._extract_intern_item_blocks(page_content)
        jobs: List[Dict[str, Any]] = []

        for item_html in item_blocks:
            # fixed: use [\'"] instead of buggy ["\"] character class
            detail_url_match = re.search(
                r'''<a[^>]*?(?:class=['"]\s*[^'"]*\btitle\b[^'"]*['"][^>]*href=['"]([^'"]+)['"]'''
                r'''|href=['"]([^'"]+)['"][^>]*class=['"]\s*[^'"]*\btitle\b[^'"]*['"])''',
                item_html,
                flags=re.S | re.I,
            )
            title_match = re.search(
                r'''<div[^>]*class=['"]\s*[^'"]*\bintern-detail__job\b[^'"]*['"][^>]*>.*?'''
                r'''<a[^>]*class=['"][^'"]*\btitle\b[^'"]*['"][^>]*>(.*?)</a>''',
                item_html,
                flags=re.S | re.I,
            )
            company_match = re.search(
                r'''<div[^>]*class=['"]\s*[^'"]*\bintern-detail__company\b[^'"]*['"][^>]*>.*?'''
                r'''<a[^>]*class=['"][^'"]*\btitle\b[^'"]*['"][^>]*>(.*?)</a>''',
                item_html,
                flags=re.S | re.I,
            )
            salary_match = re.search(
                r'''<div[^>]*class=['"]\s*[^'"]*\bintern-detail__job\b[^'"]*['"][^>]*>.*?'''
                r'''<p[^>]*class=['"][^'"]*\btip\b[^'"]*['"][^>]*>(.*?)</p>''',
                item_html,
                flags=re.S | re.I,
            )
            salary = ''
            if salary_match:
                font_spans = re.findall(
                    r'''<span[^>]*class=['"][^'"]*\bfont\b[^'"]*['"][^>]*>(.*?)</span>''',
                    salary_match.group(1),
                    flags=re.S | re.I,
                )
                if font_spans:
                    salary = cls._clean_text(font_spans[0])

            detail_url = ''
            if detail_url_match:
                detail_url = detail_url_match.group(1) or detail_url_match.group(2) or ''

            jobs.append({
                'title': cls._clean_text(title_match.group(1)) if title_match else '',
                'company': cls._clean_text(company_match.group(1)) if company_match else '',
                'salary': salary,
                'detail_url': detail_url,
            })

        return jobs

    # ── main scrape loop ─────────────────────────────────────────────

    async def scrape_jobs(self) -> List[Dict[str, Any]]:
        await self.start_browser()
        try:
            await self.navigate_to(self.url)
            collected_jobs: List[Dict[str, Any]] = []

            for page_index in range(1, 4):
                print(f'\n{"="*50}')
                print(f'  第 {page_index} 页')
                print(f'{"="*50}')

                # 1. scroll to trigger lazy-load
                await self.smooth_scroll(steps=5, delay_ms=300)

                # 2. wait for cards to appear
                try:
                    await self.page.wait_for_selector(
                        '.intern-item, .intern-wrap, [class*="intern-item"]',
                        timeout=15000,
                    )
                except Exception:
                    logger.warning('第 %d 页未找到职位卡片', page_index)

                # 3. extract jobs (Playwright DOM first, fallback to regex)
                page_jobs = await self.extract_jobs_via_playwright()
                if not page_jobs:
                    logger.info('  Playwright 提取为空，尝试正则回退方案…')
                    html_str = await self.get_page_content_str()
                    page_jobs = self.parse_job_list(html_str)

                collected_jobs.extend(page_jobs)

                # pretty-print each job to terminal in real time
                for job in page_jobs:
                    print(f'  📌 {job["title"]}')
                    print(f'     🏢 {job["company"]}')
                    print(f'     💰 {job["salary"]}')
                    print(f'     🔗 {job["detail_url"]}')
                    print()

                logger.info('第 %d 页抓取完成，获取 %d 条', page_index, len(page_jobs))

                if page_index == 3:
                    break

                # 4. find & click next-page
                prev_count = len(await self.page.query_selector_all(
                    '.intern-item, .intern-wrap, [class*="intern-item"]'
                ))
                next_btn = await self._find_next_button()

                if next_btn is None:
                    logger.warning('未找到“下一页”按钮，停止翻页')
                    break

                disabled = await next_btn.evaluate(
                    'el => el.disabled || el.classList.contains("disabled") || el.getAttribute("aria-disabled") === "true"'
                )
                if disabled:
                    logger.info('“下一页”按钮已禁用，已到最后一页')
                    break

                logger.info('点击“下一页” →')
                await next_btn.click()

                # 5. wait until DOM actually refreshes
                refreshed = await self._wait_for_item_refresh(prev_count, timeout_ms=10000)
                if not refreshed:
                    logger.warning('翻页后内容未变化，尝试额外等待…')
                    await self.page.wait_for_timeout(3000)
                else:
                    logger.info('页面已刷新')

                await self.page.wait_for_timeout(800)

            return collected_jobs
        finally:
            await self.stop_browser()

    async def scrape_job_descriptions(
        self,
        jobs_json_path: str = 'data/jobs.json',
        output_json_path: str = 'data/jobs_detailed.json',
        limit: int = 20,
    ) -> List[Dict[str, Any]]:
        """Read jobs from JSON, visit each detail URL, and write enriched output."""
        import random

        with open(jobs_json_path, 'r', encoding='utf-8') as f:
            jobs = json.load(f)

        os.makedirs(os.path.dirname(output_json_path) or 'data', exist_ok=True)

        existing_jobs: List[Dict[str, Any]] = []
        scraped_urls = set()
        if os.path.exists(output_json_path):
            with open(output_json_path, 'r', encoding='utf-8') as f:
                existing_jobs = json.load(f)
            scraped_urls = {
                job.get('detail_url', '')
                for job in existing_jobs
                if job.get('detail_url')
            }
            logger.info('已加载 %d 条已处理 URL', len(scraped_urls))

        await self.start_browser()

        try:
            for idx, job in enumerate(jobs[:limit]):
                detail_url = job.get('detail_url', '')
                if not detail_url:
                    logger.warning('[%d/%d] 缺少 detail_url，跳过', idx + 1, limit)
                    continue

                if detail_url in scraped_urls:
                    print('[INFO] URL already processed. Skipping...')
                    continue

                delay_ms = random.uniform(2000, 5000)
                await self.page.wait_for_timeout(int(delay_ms))

                page = None
                try:
                    page = await self.context.new_page()
                    logger.info('[%d/%d] 访问: %s', idx + 1, limit, detail_url)
                    await page.goto(detail_url, timeout=self.timeout, wait_until='domcontentloaded')

                    job_description = ''
                    for selector in ('.job-detail', '.job-description', '.desc',
                                     '[class*="content"]', 'article'):
                        element = await page.query_selector(selector)
                        if element:
                            text = await element.inner_text()
                            if text and len(text.strip()) > 30:
                                job_description = text
                                break

                    job['job_description'] = self._clean_text(job_description) if job_description else ''
                    
                    # AI parsing — parse_jd falls back to regex internally on failure
                    if job.get('job_description'):
                        logger.info('  ⚙️ AI 解析中…')
                        ai_results = await self.parser.parse_jd(job['job_description'])
                        job.update(ai_results)
                        logger.info('  ✓ AI 解析完成')
                    
                    existing_jobs.append(job)
                    scraped_urls.add(detail_url)

                    with open(output_json_path, 'w', encoding='utf-8') as f:
                        json.dump(existing_jobs, f, ensure_ascii=False, indent=2)

                    logger.info('  ✓ 描述已提取 (%d 字符)', len(job.get('job_description', '')))

                except Exception as exc:
                    logger.error('  ✗ URL 抓取失败 [%s]: %s', detail_url, exc)
                    job['job_description'] = ''
                    continue
                finally:
                    if page is not None:
                        await page.close()

        except KeyboardInterrupt:
            logger.warning('用户中断 (Ctrl+C)，正在保存已抓取数据…')
        finally:
            await self.stop_browser()

        with open(output_json_path, 'w', encoding='utf-8') as f:
            json.dump(existing_jobs, f, ensure_ascii=False, indent=2)
        logger.info('数据已保存至 %s (%d 条)', output_json_path, len(existing_jobs))

        return existing_jobs


# ── save function ────────────────────────────────────────────────────

def load_jobs_from_json(filepath: str = 'data/jobs.json') -> List[Dict[str, Any]]:
    """Load job list from JSON file."""
    if not os.path.exists(filepath):
        logger.warning(f'File not found: {filepath}')
        return []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def save_jobs_to_json(jobs: List[Dict[str, Any]], filepath: str = 'data/jobs.json') -> None:
    """Save job list to JSON file with UTF-8 encoding."""
    dir_path = os.path.dirname(filepath)
    if dir_path and not os.path.exists(dir_path):
        os.makedirs(dir_path, exist_ok=True)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2)
    
    print(f'🎉 Data successfully saved to {filepath}')


async def enrich_jobs_with_descriptions(jobs: List[Dict[str, Any]], limit: int = 20) -> List[Dict[str, Any]]:
    """Fetch job descriptions from detail pages and enrich job data."""
    import random

    enriched_jobs = []
    scraper = InternshipScraper(headless=False)

    try:
        await scraper.start_browser()

        for idx, job in enumerate(jobs[:limit]):
            detail_url = job.get('detail_url', '')
            if not detail_url:
                logger.warning('[%d/%d] 缺少 detail_url，跳过', idx + 1, limit)
                enriched_jobs.append(job)
                continue

            try:
                delay_ms = random.uniform(2000, 5000)
                logger.info('[%d/%d] 等待 %.1fs …', idx + 1, limit, delay_ms / 1000)
                await scraper.page.wait_for_timeout(int(delay_ms))

                logger.info('[%d/%d] 访问: %s - %s', idx + 1, limit, job.get('title', ''), job.get('company', ''))
                await scraper.navigate_to(detail_url)

                jd_selectors = [
                    '.job-detail', '.desc', '[class*="description"]',
                    '[class*="content"]', '.el-card__body', 'main', 'article',
                ]

                job_description = ''
                for selector in jd_selectors:
                    try:
                        element = await scraper.page.query_selector(selector)
                        if element:
                            job_description = await element.text_content()
                            if job_description and len(job_description) > 50:
                                break
                    except Exception:
                        continue

                if not job_description:
                    job_description = await scraper.page.evaluate('() => document.body.innerText')

                job_description = InternshipScraper._clean_text(job_description)

                enriched_job = job.copy()
                enriched_job['description'] = job_description[:1000]
                enriched_jobs.append(enriched_job)

                logger.info('  ✓ 描述已提取 (%d 字符)', len(enriched_job['description']))

            except Exception as exc:
                logger.warning('  ✗ 提取失败 [%s]: %s', detail_url, exc)
                enriched_jobs.append(job)

    except KeyboardInterrupt:
        logger.warning('用户中断 (Ctrl+C)，正在保存已抓取数据…')
    finally:
        await scraper.stop_browser()

    os.makedirs('data', exist_ok=True)
    with open('data/jobs_detailed.json', 'w', encoding='utf-8') as f:
        json.dump(enriched_jobs, f, ensure_ascii=False, indent=2)
    logger.info('数据已保存至 data/jobs_detailed.json (%d 条)', len(enriched_jobs))

    return enriched_jobs


# ── entry point ──────────────────────────────────────────────────────

async def main() -> None:
    if hasattr(sys.stdout, 'reconfigure'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    print('\n🐍 Deep-Scan 实习僧爬虫启动\n')

    # Step 1: Scrape job listings
    scraper = InternshipScraper(headless=False)
    jobs = await scraper.scrape_jobs()

    print(f'\n{"="*50}')
    print(f'  总计抓取 {len(jobs)} 条职位')
    print(f'{"="*50}\n')

    # final structured json dump
    print(json.dumps(jobs, ensure_ascii=False, indent=2))
    
    # save to file
    save_jobs_to_json(jobs)
    
    # Step 2: Enrich jobs with detailed descriptions
    print(f'\n{"="*50}')
    print(f'  Day 4: 数据丰富 - 抓取详情页')
    print(f'{"="*50}\n')
    
    enriched_jobs = await enrich_jobs_with_descriptions(jobs, limit=20)
    
    print(f'\n{"="*50}')
    print(f'  完成 {len(enriched_jobs)} 条职位的详情页抓取')
    print(f'{"="*50}\n')
    
    # save enriched data
    save_jobs_to_json(enriched_jobs, 'data/jobs_detailed.json')

    # clean and save pristine output
    cleaner = DataCleaner()
    cleaned_jobs = cleaner.clean(enriched_jobs)
    save_jobs_to_json(cleaned_jobs, 'data/jobs_cleaned.json')
    print(f'🧹 Data cleaning complete. Total original rows: {len(enriched_jobs)} | Valid clean rows remaining: {len(cleaned_jobs)}.')


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%H:%M:%S',
    )
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning('用户中断 (Ctrl+C)，脚本已退出')
