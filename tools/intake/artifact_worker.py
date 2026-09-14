"""Bounded, source-only artifact verification inside a restricted process.

The coordinator launches this with an empty environment and no application,
credential or home mounts. Never import or execute the downloaded package.
"""
from __future__ import annotations
import hashlib
import ipaddress
import json
import os
import re
import resource
import socket
import stat
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

HOSTS = {'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com', 'raw.githubusercontent.com', 'gitlab.com', 'codeberg.org', 'git.makuluni.com'}
MAX_DOWNLOAD = 50 * 1024 * 1024
MAX_MEMBERS = 5000
MAX_MEMBER = 32 * 1024 * 1024
MAX_SOURCE = 5 * 1024 * 1024
MAX_EXPANDED = 128 * 1024 * 1024


class InvalidArtifact(ValueError):
    pass


class ChecksumMismatch(InvalidArtifact):
    def __init__(self, expected, observed):
        super().__init__('Artifact checksum mismatch')
        self.expected=expected
        self.observed=observed


def validate_url(url, *, resolve=True):
    if not isinstance(url, str) or len(url) > 10000:
        raise InvalidArtifact('Invalid artifact URL')
    u = urllib.parse.urlsplit(url)
    decoded = urllib.parse.unquote(u.path)
    if '\\' in decoded or any(ord(c)<32 for c in decoded) or any(p in ('.','..') for p in decoded.split('/')):
        raise InvalidArtifact('Invalid artifact path')
    if u.scheme != 'https' or u.hostname not in HOSTS or u.username or u.password or u.fragment:
        raise InvalidArtifact('Artifact URL is outside registered HTTPS hosts')
    if u.port not in (None, 443):
        raise InvalidArtifact('Disallowed artifact port')
    if u.hostname == 'raw.githubusercontent.com' and (u.query or not re.fullmatch(
            r'/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[a-f0-9]{40}/(?:[^/]+/)*[^/]+\.apworld', u.path)):
        raise InvalidArtifact('Stored GitHub artifact must be pinned to a full commit')
    if resolve:
        addresses = socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)
        if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):
            raise InvalidArtifact('Non-public artifact destination')
    return url


class CheckedRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def inspect_archive(path):
    total = 0
    seen = set()
    sources = []
    with zipfile.ZipFile(path) as z:
        members = z.infolist()
        if not members or len(members) > MAX_MEMBERS:
            raise InvalidArtifact('Archive member budget exceeded or empty archive')
        for member in members:
            p = PurePosixPath(member.filename)
            mode = member.external_attr >> 16
            if (not member.filename or not p.parts or '\\' in member.filename or '\x00' in member.filename
                    or p.is_absolute() or '..' in p.parts or ':' in p.parts[0]
                    or member.filename in seen or stat.S_ISLNK(mode) or member.flag_bits & 1):
                raise InvalidArtifact('Unsafe archive member')
            seen.add(member.filename)
            total += member.file_size
            if member.file_size > MAX_MEMBER or total > MAX_EXPANDED:
                raise InvalidArtifact('Archive expanded-byte budget exceeded')
            if member.filename.endswith('.py') and member.file_size > MAX_SOURCE:
                raise InvalidArtifact('Python source member budget exceeded')
            if member.file_size > max(1024 * 1024, member.compress_size * 200):
                raise InvalidArtifact('Archive compression ratio exceeded')
            if not member.is_dir():
                # Read every member to validate declared sizes and CRC, without
                # extracting paths or invoking any package code.
                with z.open(member) as f:
                    size = 0
                    while block := f.read(65536):
                        size += len(block)
                        if size > MAX_MEMBER:
                            raise InvalidArtifact('Archive actual-byte budget exceeded')
                if size != member.file_size:
                    raise InvalidArtifact('Archive member size mismatch')
                if member.filename.endswith('.py'):
                    sources.append(member.filename)
        if not sources:
            raise InvalidArtifact('No reviewable Python source in APWorld archive')
    return {'members': len(members), 'expanded_bytes': total, 'python_files': len(sources)}


def verify(job, output):
    url = validate_url(job['url'])
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), CheckedRedirect())
    digest = hashlib.sha256()
    size = 0
    started = time.monotonic()
    with opener.open(urllib.request.Request(url, headers={'User-Agent': 'AP-Pie-intake/1.0'}), timeout=20) as response:
        validate_url(response.url)
        declared = response.headers.get('Content-Length')
        if declared and int(declared) > MAX_DOWNLOAD:
            raise InvalidArtifact('Artifact download budget exceeded')
        with output.open('wb') as f:
            while block := response.read(65536):
                size += len(block)
                if size > MAX_DOWNLOAD or time.monotonic() - started > 90:
                    raise InvalidArtifact('Artifact download budget exceeded')
                digest.update(block)
                f.write(block)
    checksum = digest.hexdigest()
    if job.get('expected') and checksum != job['expected']:
        raise ChecksumMismatch(job['expected'], checksum)
    return {'sha256': checksum, 'bytes': size, **inspect_archive(output)}


def main():
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (60,) * 2)
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_DOWNLOAD,) * 2)
    job = json.loads(Path(sys.argv[1]).read_text())
    output = Path(sys.argv[2])
    try:
        result = {'status': 'verified', **verify(job, output)}
    except ChecksumMismatch as e:
        output.unlink(missing_ok=True)
        result={'status':'checksum_mismatch','expected_sha256':e.expected,'observed_sha256':e.observed,
                'error':'Artifact checksum mismatch'}
    except (InvalidArtifact, zipfile.BadZipFile, RuntimeError, ValueError) as e:
        output.unlink(missing_ok=True)
        result = {'status': 'blocked', 'error': str(e)[:300]}
    except Exception as e:
        output.unlink(missing_ok=True)
        # No signed redirect URLs or raw network errors in queue/public logs.
        result = {'status': 'retry', 'error': type(e).__name__}
    print(json.dumps(result))


if __name__ == '__main__':
    main()
