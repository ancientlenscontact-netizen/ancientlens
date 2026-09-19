"""Send status-only heartbeats around verified backup maintenance; never send logs."""
import os
import re
import subprocess
import sys
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

def ping(url, state):
    if not re.fullmatch(r'https://hc-ping\.com/[0-9a-fA-F-]{36}', url):
        raise ValueError('Expected private Healthchecks ping URL')
    suffix={'start':'/start','success':'','failure':'/fail'}[state]
    request=urllib.request.Request(url+suffix, data=b'', method='POST')
    with urllib.request.build_opener(NoRedirect).open(request,timeout=10) as response:
        if response.status != 200:
            raise RuntimeError('Heartbeat rejected')

def run(args):
    url=os.environ.get('ANCIENTLENS_BACKUP_PING_URL','')
    if not url:
        print('Backup monitoring is not configured.',file=sys.stderr)
        return 1
    # Invalid configuration must fail before starting, without leaking its value.
    if not re.fullmatch(r'https://hc-ping\.com/[0-9a-fA-F-]{36}',url):
        print('Invalid backup monitoring configuration.',file=sys.stderr)
        return 1
    try:ping(url,'start')
    except Exception:print('Backup start notification failed.',file=sys.stderr)
    result=subprocess.run([sys.executable,'-m','app.data.offdevice',*args])
    try:ping(url,'success' if result.returncode==0 else 'failure')
    except Exception:
        print('Backup completion notification failed; check the private receipt.',file=sys.stderr)
        return result.returncode or 1
    return result.returncode

if __name__=='__main__':
    raise SystemExit(run(sys.argv[1:]))
