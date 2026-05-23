"""Main entry point for Deep-Scan project."""

import asyncio
import sys
from src.scraper import InternshipScraper

async def main():
    """Run the scraper."""
    scraper = InternshipScraper(headless=False)
    
    # 抓取列表
    print("开始抓取职位列表...")
    jobs = await scraper.scrape_jobs()
    print(f"获得 {len(jobs)} 条职位")
    
    # 保存列表
    from src.scraper import save_jobs_to_json
    save_jobs_to_json(jobs, 'data/jobs.json')
    
    # 抓取详情
    print("\n开始抓取职位详情...")
    detailed_jobs = await scraper.scrape_job_descriptions(
        jobs_json_path='data/jobs.json',
        output_json_path='data/jobs_detailed.json',
        limit=20
    )
    print(f"已完成 {len(detailed_jobs)} 条职位详情")

if __name__ == '__main__':
    asyncio.run(main())
