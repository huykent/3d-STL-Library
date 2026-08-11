import os
from fabric import Connection
from pathlib import Path
import sys
import re

sys.path.append('scripts')
from deploy import get_openssh_key_from_ppk

ppk_path = Path('pc2.ppk')
pem = get_openssh_key_from_ppk(ppk_path)
c = Connection(host='13.212.136.82', user='root', connect_kwargs={'key_filename': pem})

res = c.run("""docker exec stl_api python -c "
import asyncio, sys
sys.path.append('/app')
from app.database import AsyncSessionLocal
from app.models.user import User
from app.services.auth_service import create_access_token
from sqlalchemy import select

async def get_token():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username=='admin'))
        user = result.scalar_one_or_none()
        if user:
            print('TOKEN===' + create_access_token(user.username, user.role))
        else:
            print('No admin user found')

asyncio.run(get_token())
"
""", hide=True)

match = re.search(r'TOKEN===([^\s]+)', res.stdout)
if not match:
    print("Failed to get token", res.stdout)
    sys.exit(1)

token = match.group(1)
print("Token:", token)

cmd = f"curl -s 'http://localhost:8000/api/admin/telegram/send-code' -X POST -H 'Content-Type: application/json' -H 'Authorization: Bearer {token}' -d '{{\"phone\": \"+84981158389\"}}'"
res2 = c.run(cmd, hide=True)
print("Response:", res2.stdout)

os.unlink(pem)
