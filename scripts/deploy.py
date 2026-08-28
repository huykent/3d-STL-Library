import os
import sys
import tarfile
from pathlib import Path
from dotenv import load_dotenv
from fabric import Connection
from invoke import UnexpectedExit

def create_archive(source_dir, output_filename):
    print(f"Creating archive {output_filename}...")
    def exclude_filter(tarinfo):
        # Exclude directories that shouldn't be deployed
        excludes = [
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "backend/thumbnails", "backend/temp", "backend/sessions",
            ".pytest_cache", "deploy_archive.tar.gz", "superpowers", 
            ".claude", ".agents", ".gitnexus", "frontend/.next", 
            ".gemini", "pc2.ppk", ".vscode"
        ]
        for exc in excludes:
            if exc in tarinfo.name:
                return None
        return tarinfo

    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir), filter=exclude_filter)
    print("Archive created.")

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

def deploy():
    load_dotenv('.env.deploy')
    
    host = os.getenv('DEPLOY_HOST')
    user = os.getenv('DEPLOY_USER')
    password = os.getenv('DEPLOY_PASS')
    deploy_dir = os.getenv('DEPLOY_DIR', '/root/3d-STL-Library')
    
    project_root = Path(__file__).parent.parent
    archive_name = "deploy_archive.tar.gz"
    archive_path = project_root / archive_name
    
    # Check for PPK key
    ppk_path = project_root / "pc2.ppk"
    connect_kwargs = {}
    
    if ppk_path.exists():
        print("Found pc2.ppk, converting to OpenSSH format...")
        openssh_path = get_openssh_key_from_ppk(ppk_path)
        connect_kwargs["key_filename"] = openssh_path
    elif password:
        connect_kwargs["password"] = password
    else:
        print("Error: No password in .env.deploy and no pc2.ppk found!")
        sys.exit(1)
    
    create_archive(project_root, archive_path)
    
    print(f"Connecting to {user}@{host}...")
    try:
        with Connection(host=host, user=user, connect_kwargs=connect_kwargs) as c:
            print("Creating remote directory if not exists...")
            c.run(f"mkdir -p {deploy_dir}")
            
            print("Uploading archive...")
            c.put(str(archive_path), remote=f"{deploy_dir}/{archive_name}")
            
            print("Extracting archive...")
            c.run(f"cd {deploy_dir} && tar -xzf {archive_name} --strip-components=1")
            c.run(f"cd {deploy_dir} && rm {archive_name}")
            
            print("Restarting docker compose...")
            try:
                c.run(f"cd {deploy_dir} && docker compose down", hide=True)
            except UnexpectedExit:
                pass # Might fail if not up yet
                
            print("Building and starting containers (this may take a few minutes)...")
            c.run(f"cd {deploy_dir} && docker compose up -d --build", hide=True)
            
            print("Deployment completed successfully!")
            
    except Exception as e:
        print(f"Deployment failed: {e}")
    finally:
        if archive_path.exists():
            archive_path.unlink()
            print("Cleaned up local archive.")
        if ppk_path.exists() and Path(str(ppk_path) + ".pem").exists():
            Path(str(ppk_path) + ".pem").unlink()

if __name__ == "__main__":
    deploy()
