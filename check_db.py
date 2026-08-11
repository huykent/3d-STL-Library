import os
from fabric import Connection
from pathlib import Path
import sys
sys.path.append('scripts')
from deploy import get_openssh_key_from_ppk

ppk_path = Path('pc2.ppk')
pem = get_openssh_key_from_ppk(ppk_path)
c = Connection(host='13.212.136.82', user='root', connect_kwargs={'key_filename': pem})

res = c.run("docker exec stl_postgres psql -U postgres -d stl_library -c \"SELECT key FROM settings;\"", hide=True, warn=True)
print(res.stdout)
os.unlink(pem)
