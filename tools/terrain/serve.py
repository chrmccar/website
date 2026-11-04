#!/usr/bin/env python3
"""Local-only static pilot server with real single-byte-range support; no uploads/API."""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re

class Handler(SimpleHTTPRequestHandler):
    def send_head(self):
        path = Path(self.translate_path(self.path))
        if path.suffix != '.pmtiles' or not path.is_file():
            return super().send_head()
        size = path.stat().st_size
        header = self.headers.get('Range')
        start, end = 0, size - 1
        if header:
            match = re.fullmatch(r'bytes=(\d+)-(\d*)', header)
            if not match or int(match[1]) >= size:
                self.send_response(416); self.send_header('Content-Range', f'bytes */{size}'); self.end_headers(); return None
            start = int(match[1]); end = min(int(match[2]) if match[2] else end, end)
            if start > end:
                self.send_response(416); self.send_header('Content-Range', f'bytes */{size}'); self.end_headers(); return None
        self.send_response(206 if header else 200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Cache-Control', 'no-store')
        if header:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.end_headers()
        f = path.open('rb'); f.seek(start); self.remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, 'remaining', None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        while remaining:
            chunk = source.read(min(remaining, 65536))
            if not chunk: break
            outputfile.write(chunk); remaining -= len(chunk)
        self.remaining = None

    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Expose-Headers', 'Content-Range, Accept-Ranges, Content-Length')
        super().end_headers()

    def log_message(self, *args):
        pass

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--directory', default='.')
    p.add_argument('--port',type=int,default=8766)
    args=p.parse_args()
    root=Path(args.directory).resolve()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),partial(Handler,directory=str(root)))
    print(f'Pilot server bound to loopback port {args.port}; root {root}',flush=True)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
