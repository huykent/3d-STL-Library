import os
from dotenv import load_dotenv
from fabric import Connection
from pathlib import Path

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

ppk_path = Path("pc2.ppk")
openssh_path = get_openssh_key_from_ppk(ppk_path)

print(f"Connecting to {user}@{host} to NUKE everything...")
with Connection(host=host, user=user, connect_kwargs={"key_filename": openssh_path}) as c:
    print("\n=== STOPPING AND REMOVING ALL DOCKER CONTAINERS ===")
    c.run("docker rm -f $(docker ps -aq) || true")
    
    print("\n=== PRUNING DOCKER NETWORK ===")
    c.run("docker network prune -f || true")
    
    print("\n=== DELETING OLD PROJECT FOLDERS ===")
    c.run("rm -rf /root/telebot /root/3d-STL-Library")
    
    print("\nNUKE SUCCESSFUL! VPS is now completely clean.")

Path(openssh_path).unlink()
