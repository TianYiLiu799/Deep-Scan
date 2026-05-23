"""One-shot script: parse + clean jobs_detailed.json → jobs_cleaned.json"""
import json
import re
from src.parser import AIJobParser
from src.cleaner import DataCleaner

with open('data/jobs_detailed.json', 'r', encoding='utf-8') as f:
    jobs = json.load(f)

print(f'Loaded {len(jobs)} detailed jobs')

# Tech keyword list for better regex extraction
TECH_KEYWORDS = [
    'Python', 'Django', 'Flask', 'FastAPI', 'JavaScript', 'TypeScript', 'React', 'Vue',
    'Node.js', 'MySQL', 'PostgreSQL', 'MongoDB', 'Redis', 'Elasticsearch',
    'Docker', 'Kubernetes', 'Linux', 'Git', 'AWS', 'GCP', 'Azure',
    'NLP', 'TensorFlow', 'PyTorch', 'Scrapy', 'Selenium', 'REST', 'GraphQL',
    'HTML', 'CSS', 'SQL', 'Shell', 'Angular', 'Spring', 'AI', 'Machine Learning',
    'C++', 'C#', 'Java', 'Go', 'Rust', 'Nginx', 'Jenkins', 'Ansible', 'Terraform',
    'Hadoop', 'Spark', 'Kafka', 'RabbitMQ', 'Celery', 'pytest', 'unittest',
    'OpenCV', 'Keras', 'XPath', 'Regex', 'jQuery', 'Ajax', 'Vue.js', 'AngularJS',
    'RPA', 'OCR', 'BCI', 'EEG', 'Qt',
]

def extract_tech(desc):
    found = []
    desc_lower = desc.lower()
    for tech in TECH_KEYWORDS:
        if tech.lower() in desc_lower:
            found.append(tech)
    return found

# Salary pattern for daily rates in descriptions
SALARY_RE = re.compile(r'(\d{2,4})\s*[-–—to至]+\s*(\d{2,4})\s*[元/天每]')
SALARY_SINGLE_RE = re.compile(r'(\d{2,4})\s*元?\s*/\s*[天日]')

parser = AIJobParser()
for job in jobs:
    desc = job.get('description', '')
    if desc:
        parsed = parser._parse_with_regex(desc)
        # Use keyword-based extraction as primary (much better quality)
        tech = extract_tech(desc)
        job['core_tech_stack'] = tech if tech else parsed.get('core_tech_stack', [])
        job['experience_level'] = parsed.get('experience_level', '')
        job['employment_type'] = parsed.get('employment_type', '')
        job['location'] = parsed.get('location', '')

        # Extract salary from description if the salary field has no numbers
        raw_sal = job.get('salary', '')
        if not re.search(r'\d', raw_sal or ''):
            m = SALARY_RE.search(desc)
            if m:
                job['salary'] = f"{m.group(1)}-{m.group(2)}/天"
            else:
                m = SALARY_SINGLE_RE.search(desc)
                if m:
                    job['salary'] = f"{m.group(1)}/天"
    else:
        job['core_tech_stack'] = []

cleaner = DataCleaner()
cleaned = cleaner.clean(jobs)

with open('data/jobs_cleaned.json', 'w', encoding='utf-8') as f:
    json.dump(cleaned, f, ensure_ascii=False, indent=2)

print(f'Cleaned: {len(cleaned)} / {len(jobs)} records saved')

# Quick stats
all_techs = []
salaries = []
for j in cleaned:
    all_techs.extend(j.get('core_tech_stack', []))
    if j.get('salary_min') and j.get('salary_max'):
        salaries.append((j['salary_min'] + j['salary_max']) / 2)
    elif j.get('salary_min'):
        salaries.append(j['salary_min'])

from collections import Counter
top = Counter(all_techs).most_common(5)
print(f'Top tech: {top}')
print(f'Records with salary: {len(salaries)}')
if salaries:
    print(f'Salary range: {min(salaries):.0f} - {max(salaries):.0f}')
