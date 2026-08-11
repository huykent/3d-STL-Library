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
            "backend/thumbnails", "backend/temp", ".pytest_cache",
            "deploy_archive.tar.gz", "superpowers", ".claude", ".agents",
            ".gitnexus"
        ]
        for exc in excludes:
            if exc in tarinfo.name:
                return None
        return tarinfo

    with tarfile.open(output_filename, "w:gz") as tar:
        tar.add(source_dir, arcname=os.path.basename(source_dir), filter=exclude_filter)
    print("Archive created.")

def deploy():
    load_dotenv('.env.deploy')
    
    host = os.getenv('DEPLOY_HOST')
    user = os.getenv('DEPLOY_USER')
    password = os.getenv('DEPLOY_PASS')
    deploy_dir = os.getenv('DEPLOY_DIR', '/root/3d-STL-Library')
    
    if not all([host, user, password]):
        print("Error: Missing deployment credentials in .env.deploy")
        sys.exit(1)
        
    project_root = Path(__file__).parent.parent
    archive_name = "deploy_archive.tar.gz"
    archive_path = project_root / archive_name
    
    create_archive(project_root, archive_path)
    
    print(f"Connecting to {user}@{host}...")
    try:
        with Connection(host=host, user=user, connect_kwargs={"password": password}) as c:
            print("Creating remote directory if not exists...")
            c.run(f"mkdir -p {deploy_dir}")
            
            print("Uploading archive...")
            c.put(str(archive_path), remote=f"{deploy_dir}/{archive_name}")
            
            print("Extracting archive...")
            c.run(f"cd {deploy_dir} && tar -xzf {archive_name} --strip-components=1")
            c.run(f"cd {deploy_dir} && rm {archive_name}")
            
            print("Restarting docker-compose...")
            try:
                c.run(f"cd {deploy_dir} && docker-compose down")
            except UnexpectedExit:
                pass # Might fail if not up yet
                
            c.run(f"cd {deploy_dir} && docker-compose up -d --build")
            
            print("Deployment completed successfully!")
            
    except Exception as e:
        print(f"Deployment failed: {e}")
    finally:
        if archive_path.exists():
            archive_path.unlink()
            print("Cleaned up local archive.")

if __name__ == "__main__":
    deploy()
