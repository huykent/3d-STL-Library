from pathlib import Path
import os
from dotenv import load_dotenv
from fabric import Connection

def get_openssh_key_from_ppk(ppk_path):
    import base64
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives import serialization

    with open(ppk_path, 'r') as f:
        lines = f.read().splitlines()
    
    priv_data = ""
    in_priv = False
    for line in lines:
        if line.startswith("Private-Lines:"):
            in_priv = True
            continue
        if in_priv and not line.startswith("Private-MAC:"):
            priv_data += line
        if line.startswith("Private-MAC:"):
            break
            
    priv_bytes = base64.b64decode(priv_data)
    seed = priv_bytes[4:36]
    
    key = Ed25519PrivateKey.from_private_bytes(seed)
    pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption()
    )
    
    openssh_path = str(ppk_path) + ".pem"
    with open(openssh_path, 'wb') as f:
        f.write(pem)
    return openssh_path

load_dotenv('.env.deploy')
host = os.getenv('DEPLOY_HOST')
user = os.getenv('DEPLOY_USER')
deploy_dir = os.getenv('DEPLOY_DIR', '/root/telebot')

ppk_path = Path("pc2.ppk")
openssh_path = get_openssh_key_from_ppk(ppk_path)

cmd = """docker compose exec -T api python -c "
import asyncio, uuid
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.services.auth_service import get_password_hash

async def seed():
    async with AsyncSessionLocal() as db:
        user = User(
            id=uuid.uuid4(),
            username='admin',
            email='admin@example.com',
            password_hash=get_password_hash('admin123'),
            role=UserRole.admin
        )
        db.add(user)
        await db.commit()
        print('\n--- TAO THANH CONG ---')
        print('User: admin')
        print('Pass: admin123')
        print('----------------------')

asyncio.run(seed())
"
"""

print(f"Connecting to {user}@{host} to run seed...")
with Connection(host=host, user=user, connect_kwargs={"key_filename": openssh_path}) as c:
    c.run(f"cd {deploy_dir} && {cmd}")

Path(openssh_path).unlink()
