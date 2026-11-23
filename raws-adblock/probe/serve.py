#!/usr/bin/env python3
"""Controlled two-site HTTP fixture. No third-party traffic or browsing logs."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent
class Site(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        host=(self.headers.get('Host') or '').split(':',1)[0].lower()
        if host not in {'raws-news.test','raws-ads.test'}: self.send_error(400); return
        path=urlsplit(self.path).path
        if host=='raws-news.test' and path in {'/', '/cosmetic-parity'}:
            mime='text/html; charset=utf-8'; data=(ROOT/'index.html').read_bytes()
        elif path in {'/raws-fixture/banner.js','/raws-fixture/shim.js','/raws-fixture/clean.js'}:
            mime='application/javascript';data=b'window.rawsExecutions=(window.rawsExecutions||0)+1;'
        elif path=='/rules.txt':
            mime='text/plain'; data=(ROOT/'rules.txt').read_bytes()
        else: self.send_error(404); return
        self.send_response(200);self.send_header('Content-Type',mime);self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bind',default='127.0.0.1');p.add_argument('--port',type=int,default=8080);a=p.parse_args()
    ThreadingHTTPServer((a.bind,a.port),Site).serve_forever()
