"""Check public guides and discover setup documents without package execution."""
import hashlib
import ipaddress
import json
import re
import resource
import socket
import sys
import time
import urllib.parse
import urllib.request

HOSTS = {'github.com', 'raw.githubusercontent.com', 'archipelago.gg', 'archipelago.miraheze.org', 'ap-pie.com', 'beta.ap-pie.com'}


def check_url(url):
    u = urllib.parse.urlsplit(url)
    if u.scheme != 'https' or u.hostname not in HOSTS or u.username or u.password or u.port not in (None, 443):
        raise ValueError('Guide host requires source registration')
    if any(not ipaddress.ip_address(a[4][0]).is_global for a in socket.getaddrinfo(u.hostname, 443, type=socket.SOCK_STREAM)):
        raise ValueError('Non-public guide address')
    return urllib.parse.urlunsplit(u._replace(fragment=''))


class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        check_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url):
    url = check_url(url)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), Redirect())
    with opener.open(urllib.request.Request(url, headers={'User-Agent': 'AP-Pie-guide-intake/1.0'}), timeout=15) as response:
        check_url(response.url)
        body = response.read(2 * 1024 * 1024 + 1)
        if not body or len(body) > 2 * 1024 * 1024:
            raise ValueError('Guide content exceeds budget or is empty')
        return body


def find(job):
    if job.get('setup_guide'):
        body = fetch(job['setup_guide'])
        return {'url': job['setup_guide'], 'content_sha256': hashlib.sha256(body).hexdigest(),
                'checked_at': time.time(), 'kind': 'existing-link-reachable'}
    repo = re.match(r'https://github\.com/([^/]+/[^/]+)/releases/download/', job['artifact_url'])
    if not repo:
        return None
    root = 'https://github.com/' + repo.group(1) + '/'
    readme = fetch(root + 'raw/HEAD/README.md').decode('utf-8', errors='replace')
    # Discover documentation from the artifact's repository only. External
    # links need explicit source registration rather than following arbitrary URLs.
    links = re.findall(r'\[[^\]]*(?:setup|installation)[^\]]*\]\(([^\s)]+)\)', readme, re.I)
    for link in links[:5]:
        if link.startswith(('http:', 'https:', '//')) or '..' in link.split('/'):
            continue
        url = root + 'blob/HEAD/' + link.lstrip('./')
        body = fetch(root + 'raw/HEAD/' + link.lstrip('./'))
        text = body.decode('utf-8', errors='replace').lower()
        if 'archipelago' in text and any(word in text for word in ('connect', 'install', 'setup')):
            return {'url': url, 'content_sha256': hashlib.sha256(body).hexdigest(),
                    'checked_at': time.time(), 'kind': 'repository-setup-document'}
    return None


if __name__ == '__main__':
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024,) * 2)
    resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
    try:
        result = find(json.load(open(sys.argv[1])))
        print(json.dumps({'result': result}))
    except Exception as exc:
        print(json.dumps({'error': type(exc).__name__}))
