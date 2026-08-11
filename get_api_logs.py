import os
from dotenv import load_dotenv
import paramiko

def run():
    load_dotenv('.env.deploy')
    host = os.getenv('DEPLOY_HOST')
    user = os.getenv('DEPLOY_USER')
    deploy_dir = os.getenv('DEPLOY_DIR', '/root/3d-STL-Library')

    # Convert PPK to OpenSSH
    from fabric import Connection
    from pathlib import Path
    import sys

    # using the same logic as get_logs.py to convert
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

    ppk_path = Path("pc2.ppk")
    openssh_path = get_openssh_key_from_ppk(ppk_path)

    print(f"Connecting to {user}@{host} to fetch logs...")
    with Connection(host=host, user=user, connect_kwargs={"key_filename": openssh_path}) as c:
        print("\n=== API LOGS ===")
        res_api = c.run(f"cd {deploy_dir} && docker compose logs --tail=200 api", hide=True, warn=True)
        print(res_api.stdout.encode('utf-8', errors='replace').decode('utf-8', errors='replace'))
        
        print("\n=== WORKER LOGS ===")
        res_worker = c.run(f"cd {deploy_dir} && docker compose logs --tail=200 worker", hide=True, warn=True)
        # Avoid charmap encode error on Windows
        print(res_worker.stdout.encode('utf-8', errors='replace').decode('utf-8', errors='replace').encode('cp1252', errors='replace').decode('cp1252'))

    Path(openssh_path).unlink()

if __name__ == "__main__":
    run()
