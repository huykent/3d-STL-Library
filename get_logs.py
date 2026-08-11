import os
from fabric import Connection
from pathlib import Path
import sys
sys.path.append('scripts')
from deploy import get_openssh_key_from_ppk

ppk_path = Path('pc2.ppk')
pem = get_openssh_key_from_ppk(ppk_path)
c = Connection(host='13.212.136.82', user='root', connect_kwargs={'key_filename': pem})

import sys
container = sys.argv[1] if len(sys.argv) > 1 else 'stl_api'
res = c.run(f"docker logs --tail 200 {container}", hide=True, warn=True)
with open('log.txt', 'wb') as f:
    f.write(b'STDOUT:\n')
    f.write(res.stdout.encode('utf-8', 'replace'))
    f.write(b'\nSTDERR:\n')
    f.write(res.stderr.encode('utf-8', 'replace'))
os.unlink(pem)
