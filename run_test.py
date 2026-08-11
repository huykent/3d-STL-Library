import os
from fabric import Connection
from pathlib import Path
import sys
sys.path.append('scripts')
from deploy import get_openssh_key_from_ppk

ppk_path = Path('pc2.ppk')
pem = get_openssh_key_from_ppk(ppk_path)
c = Connection(host='13.212.136.82', user='root', connect_kwargs={'key_filename': pem})

script = """
import sys
sys.path.append('/app')
import asyncio
from app.telegram.client import get_telegram_client
import logging
logging.basicConfig(level=logging.DEBUG)

async def test():
    try:
        client = await get_telegram_client()
        await client.connect()
        print("Sending code request...")
        res = await client.send_code_request('+84981158389')
        print("Response:", res)
    except Exception as e:
        print("EXCEPTION:", str(e))
        import traceback
        traceback.print_exc()

asyncio.run(test())
"""

c.run("cat << 'EOF' > /root/test_telethon.py\n" + script + "\nEOF")
c.run("docker cp /root/test_telethon.py stl_api:/tmp/test_telethon.py", hide=True)
print("Running test inside stl_api...")
res = c.run("docker exec stl_api python /tmp/test_telethon.py", hide=True, warn=True)
print(res.stdout)
print(res.stderr)
os.unlink(pem)
