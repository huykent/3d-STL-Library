import os
import sys
from pathlib import Path
from fabric import Connection

sys.path.append('scripts')
try:
    from deploy import get_openssh_key_from_ppk
except ImportError:
    print("Could not import deploy.py")
    sys.exit(1)

ppk_path = Path('pc2.ppk')
pem = get_openssh_key_from_ppk(ppk_path)
c = Connection(host='13.212.136.82', user='root', connect_kwargs={'key_filename': pem})

print("--- Source Groups ---")
res1 = c.run("docker exec stl_postgres psql -U postgres -d stl_library -c \"SELECT id, chat_id, name, is_active FROM source_groups;\"", hide=True, warn=True)
print(res1.stdout)

print("--- App Configs (CRAWL_HISTORY_DAYS) ---")
res2 = c.run("docker exec stl_postgres psql -U postgres -d stl_library -c \"SELECT key, value FROM app_configs WHERE key = 'CRAWL_HISTORY_DAYS';\"", hide=True, warn=True)
print(res2.stdout)

os.unlink(pem)
