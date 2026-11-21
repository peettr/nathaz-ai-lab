"""Verified-size OSDF download; never silently accept an incomplete HTTP 200."""
import hashlib
import re
import time
import urllib.request
from pathlib import Path

HEADERS = {'User-Agent': 'Mozilla/5.0'}


def expected_bytes(url):
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS, method='HEAD'), timeout=120) as r:
            size = r.headers.get('Content-Length')
            if r.status == 200 and size and int(size) > 0:
                return int(size), 'HEAD'
    except Exception:
        pass
    with urllib.request.urlopen(urllib.request.Request(url, headers={**HEADERS, 'Range': 'bytes=0-0'}), timeout=120) as r:
        match = re.search(r'bytes\s+0-0/(\d+)', r.headers.get('Content-Range', ''))
        if r.status != 206 or not match:
            raise RuntimeError(f'cannot establish full size: status={r.status} range={r.headers.get("Content-Range")}')
        return int(match.group(1)), 'Range'


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def complete(path, size):
    path = Path(path)
    return path.stat().st_size == size and path.stat().st_size >= 4 and path.open('rb').read(4) == b'GRIB'


def get(url, dest, *, prior_sha=None, preserve_truncated=False):
    """Return verified metadata; only the named 58th historical truncation is renamed."""
    dest = Path(dest)
    size, method = expected_bytes(url)
    if dest.exists():
        if complete(dest, size):
            sha = digest(dest)
            if prior_sha is not None and sha != prior_sha:
                raise RuntimeError(f'historical hash changed: {dest}')
            return {'url': url, 'bytes': size, 'sha256': sha, 'size_source': method, 'reused': True}
        if not preserve_truncated or dest.with_name(dest.name + '.truncated').exists():
            raise RuntimeError(f'existing invalid file left untouched: {dest} ({dest.stat().st_size}/{size})')
        dest.rename(dest.with_name(dest.name + '.truncated'))
    for attempt in range(1, 4):
        part = dest.with_name(dest.name + f'.attempt{attempt}.partial')
        if part.exists():
            raise FileExistsError(part)
        error = None
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=200) as response, part.open('xb') as out:
                if response.status != 200:
                    raise RuntimeError(f'HTTP {response.status}')
                while chunk := response.read(4 * 1024 * 1024):
                    out.write(chunk)
            if complete(part, size):
                part.rename(dest)
                return {'url': url, 'bytes': size, 'sha256': digest(dest), 'size_source': method, 'reused': False, 'attempt': attempt}
            error = f'short or invalid payload: {part.stat().st_size}/{size}'
        except Exception as exc:
            error = f'{type(exc).__name__}: {exc}'
        print('DOWNLOAD_ATTEMPT_FAILED', url, attempt, error, flush=True)
        # Keep failed attempt for provenance; no deleting or overwriting any evidence.
        if attempt < 3:
            time.sleep(2 ** attempt)
    raise RuntimeError(f'download incomplete after 3 attempts: {url}; last={error}')
