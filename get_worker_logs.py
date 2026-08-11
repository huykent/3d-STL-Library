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
    
    print(f"Connecting to {user}@{host} to fetch logs...")
    connect_kwargs = {}
    if password:
        connect_kwargs["password"] = password
    else:
        print("No password found")
        return

    with Connection(host=host, user=user, connect_kwargs=connect_kwargs) as c:
        res_worker = c.run(f"cd {deploy_dir} && docker compose logs --tail=200 worker", hide=True, warn=True)
        with open("worker_logs.txt", "w", encoding="utf-8") as f:
            f.write(res_worker.stdout)
        
        print("Logs saved to worker_logs.txt")

if __name__ == "__main__":
    run()
