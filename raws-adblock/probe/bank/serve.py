#!/usr/bin/env python3
"""Synthetic, local-only fixture. Never logs addresses, cookies, or headers."""
import argparse
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import ssl
import threading
from urllib.parse import parse_qs, urlsplit

PAGES = frozenset({'raws-news.test', 'raws-ads.test'})
BANK = Path(__file__).resolve().parent
NEXT = {
    'blocked-hop': 'blocked-target',
    'allowed-hop': 'allowed-target',
    'excepted-hop': 'excepted-target',
}
TARGETS = {*NEXT.values(), 'allowed-direct'}
TRACK = frozenset(NEXT) | TARGETS
TOKEN = re.compile(r'[0-9a-f]{24}')
SCRIPTLET_PAGE = re.compile(r'/fixture-scriptlet/[0-9a-f]{24}')
HOST = re.compile(r'(raws-(?:news|ads)\.test)(:\d{1,5})?')
PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAACklEQVQImWNgAAAAAgAB'
    '9HFkpgAAAABJRU5ErkJggg==')
ROUTES = {'/fixture': ('index.html', 'text/html; charset=utf-8'),
          '/bank.js': ('bank.js', 'text/javascript; charset=utf-8'),
          '/passive.txt': ('passive.txt', 'text/plain; charset=utf-8'),
          '/reviewed-scriptlets.txt': ('reviewed-scriptlets.txt', 'text/plain; charset=utf-8')}

class Site(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        host = HOST.fullmatch(self.headers.get('Host', ''))
        path = urlsplit(self.path)
        if not host or host[1] not in PAGES or path.scheme or path.netloc:
            self.send_error(400)
            return
        if (host[1] == 'raws-news.test' and not path.query and
                SCRIPTLET_PAGE.fullmatch(path.path)):
            self.respond(200, (BANK/'index.html').read_bytes(), ROUTES['/fixture'][1])
            return
        if host[1] == 'raws-news.test' and path.path in ROUTES:
            file, mime = ROUTES[path.path]
            self.respond(200, (BANK/file).read_bytes(), mime)
            return
        key = path.path.removeprefix('/bank-image/').removesuffix('.png')
        if (host[1] != 'raws-ads.test' or key not in TRACK or
                path.path != f'/bank-image/{key}.png'):
            self.send_error(404)
            return
        q = parse_qs(path.query, keep_blank_values=True)
        tokens = q.get('run', [])
        if q.keys() != {'run'} or len(tokens) != 1 or not TOKEN.fullmatch(tokens[0]):
            self.send_error(400)
            return
        status = 302 if key in NEXT else 200
        self.server.record({'run': tokens[0], 'route': key, 'status': status})
        target = f'/bank-image/{NEXT[key]}.png?run={tokens[0]}' if status == 302 else None
        self.respond(status, b'' if target else PNG, 'image/png', target)

    def respond(self, status, data, mime, location=None):
        self.send_response(status)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Type', mime)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Length', str(len(data)))
        if location:
            self.send_header('Location', location)
        self.end_headers()
        self.wfile.write(data)

class Server(ThreadingHTTPServer):
    def __init__(self, address, log, *, ssl_context=None):
        super().__init__(address, Site)
        self.log = log
        self.lock = threading.Lock()
        if ssl_context:
            self.socket = ssl_context.wrap_socket(self.socket, server_side=True)

    def record(self, event):
        with self.lock:
            self.log.write(json.dumps(event, sort_keys=True)+'\n')
            self.log.flush()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bind', default='127.0.0.1')
    p.add_argument('--port', type=int, default=8080)
    p.add_argument('--log', type=Path, required=True)
    p.add_argument('--cert', type=Path)
    p.add_argument('--key', type=Path)
    a = p.parse_args()
    if bool(a.cert) != bool(a.key):
        p.error('HTTPS requires both a lab cert and key')
    ctx = None
    if a.cert:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(a.cert, a.key)
    with a.log.open('x', encoding='utf-8') as log, Server((a.bind, a.port), log, ssl_context=ctx) as server:
        server.serve_forever()

if __name__ == '__main__':
    main()
