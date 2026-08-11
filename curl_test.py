import os
from fabric import Connection
from pathlib import Path
import sys
sys.path.append('scripts')
from deploy import get_openssh_key_from_ppk

ppk_path = Path('pc2.ppk')
pem = get_openssh_key_from_ppk(ppk_path)
c = Connection(host='13.212.136.82', user='root', connect_kwargs={'key_filename': pem})

# We will generate a JWT token for the admin user using the backend's auth logic
res = c.run("""docker exec stl_api python -c "
import asyncio, sys
sys.path.append('/app')
from app.database import AsyncSessionLocal
from app.models.user import User
from app.core.security import create_access_token
from sqlalchemy import select

async def get_token():
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.username=='admin'))
        user = result.scalar_one_or_none()
        if user:
            print(create_access_token(user.id, user.username, user.role))
        else:
            print('No admin user found')

asyncio.run(get_token())
"
""", hide=True)

token = res.stdout.strip()
print("Token:", token)

# Now use the token to curl the endpoint!
cmd = f"docker exec stl_api curl -s 'http://localhost:8000/api/admin/telegram/send-code' -X POST -H 'Content-Type: application/json' -H 'Authorization: Bearer {token}' -d '{{\"phone\": \"+84981158389\"}}'"
res2 = c.run(cmd, hide=True)
print("Response:", res2.stdout)

os.unlink(pem)
