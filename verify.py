import os
import sys
import time
import requests
import re
from pathlib import Path
from fabric import Connection

sys.path.append('scripts')
from deploy import get_openssh_key_from_ppk

ppk_path = Path('pc2.ppk')
pem = get_openssh_key_from_ppk(ppk_path)
c = Connection(host='13.212.136.82', user='root', connect_kwargs={'key_filename': pem})

print("Checking Worker Status logs...")
res = c.run("docker compose -f /root/3d-STL-Library/docker-compose.yml logs --tail 50 worker", hide=True)
with open('logs.txt', 'w', encoding='utf-8') as f:
    f.write(res.stdout)
print("Logs saved to logs.txt")

os.unlink(pem)
