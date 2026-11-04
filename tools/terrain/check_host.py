#!/usr/bin/env python3
"""Probe an actual PMTiles archive URL; never infer range support from headers alone."""
import argparse
import json
import re
import urllib.error
import urllib.request


def probe(url, origin=None):
    headers={'Range':'bytes=0-126','Accept-Encoding':'identity','User-Agent':'TasmaniaTerrainPilot/1.0'}
    if origin: headers['Origin']=origin
    request=urllib.request.Request(url,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=30) as response:
            result={'url':url,'status':response.status,'content_range':response.headers.get('Content-Range'),
                    'allow_origin':response.headers.get('Access-Control-Allow-Origin'),
                    'encoding':response.headers.get('Content-Encoding'),'bytes_read':0}
            data=response.read(128);result['bytes_read']=len(data)
            match=re.fullmatch(r'bytes 0-126/(\d+)',result['content_range'] or '')
            result['range_ok']=response.status==206 and match is not None and len(data)==127 and data[:7]==b'PMTiles'
            result['cors_ok']=origin is None or result['allow_origin'] in ('*',origin)
            result['content_encoding_ok']=result['encoding'] in (None,'identity')
            result['ready']=result['range_ok'] and result['cors_ok'] and result['content_encoding_ok']
            if match: result['archive_bytes']=int(match[1])
            return result
    except (OSError,urllib.error.URLError) as error:
        return {'url':url,'ready':False,'error':str(error)}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('url');parser.add_argument('--origin')
    args=parser.parse_args();result=probe(args.url,args.origin);print(json.dumps(result,indent=2))
    raise SystemExit(0 if result['ready'] else 1)
