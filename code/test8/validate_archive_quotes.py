#!/usr/bin/env python3
"""Validate English quotations against indexed local PDF physical pages; offline."""
import csv
import re
import subprocess
import unicodedata
from pathlib import Path

BASE = Path(__file__).resolve().parent
INDEX = BASE.parent / 'archive_index' / 'kareem_archive_index.csv'
ANSWER = BASE / 'archive_answers.md'
OUT = BASE / 'quote_validation.txt'
STAGING = Path('./.hermes/profiles/researchos-literature/Kareem12_PDF_Staging/06_PeakFactors.pdf')
PATTERN = re.compile(r'\[(KA-\d{4}),\s*(T[0123]|未知),\s*PDF 第(\d+)页\]\s*“([^”]+)”')

def norm(s):
    s = unicodedata.normalize('NFKC', s)
    s = re.sub(r'(?<=[A-Za-z])-\s+(?=[A-Za-z])', '', s)
    return re.sub(r'\s+', ' ', s).strip().casefold()

def main():
    rows = {r['archive_id']: r for r in csv.DictReader(INDEX.open(encoding='utf-8-sig'))}
    text = ANSWER.read_text(encoding='utf-8')
    entries = PATTERN.findall(text)
    assert len(entries) == text.count('PDF 第'), 'Some PDF citations were not parsed'
    cache = {}
    results = []
    for aid, tier, page, quote in entries:
        row = rows.get(aid)
        path = STAGING if aid == 'KA-0106' else Path(row['local_pdf_path'].split(';')[0]) if row and row['local_pdf_path'] else None
        state = 'PASS'
        if row is None or row['tier'] != tier or path is None or not path.is_file():
            state = 'FAIL metadata/path'
        else:
            key = (str(path), int(page))
            if key not in cache:
                proc = subprocess.run(['pdftotext', '-f', page, '-l', page, '-raw', str(path), '-'], capture_output=True, text=True)
                cache[key] = proc.stdout if proc.returncode == 0 else ''
            if norm(quote) not in norm(cache[key]):
                state = 'FAIL literal/page'
        results.append(f'{state}\t{aid}\tp{page}\t{quote}')
    ok = sum(x.startswith('PASS') for x in results)
    summary = f'{ok}/{len(results)} quotations located on indexed PDF physical pages; errors={len(results)-ok}; unique PDF pages={len(cache)}.\n'
    OUT.write_text(summary + '\n'.join(results) + '\n', encoding='utf-8')
    print(summary.strip())
    for line in results:
        if not line.startswith('PASS'):
            print(line)
    return 0 if ok == len(results) and len(results) > 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
