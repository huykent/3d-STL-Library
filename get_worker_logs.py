import os
from pathlib import Path
from dotenv import load_dotenv
from fabric import Connection

def run():
    load_dotenv('.env.deploy')
    host = os.getenv('DEPLOY_HOST')
    user = os.getenv('DEPLOY_USER')
    password = os.getenv('DEPLOY_PASS')
    deploy_dir = os.getenv('DEPLOY_DIR', '/root/telebot')
    
    project_root = Path(__file__).parent
    connect_kwargs = {"password": password}
    
    with Connection(host=host, user=user, connect_kwargs=connect_kwargs) as c:
        print(c.run(f"cd {deploy_dir} && docker compose exec worker cat /etc/apt/sources.list.d/debian.sources", warn=True).stdout)

if __name__ == "__main__":
    run()
