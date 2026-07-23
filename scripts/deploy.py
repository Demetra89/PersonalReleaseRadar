import paramiko
import os

HOST = "144.31.148.133"
USER = "root"
PASS = "2Nor8nc2%T)qIzhB"
PUB_KEY_PATH = os.path.expanduser("~/.ssh/id_ed25519.pub")

def run_remote(client, cmd):
    print(f"--- Running: {cmd} ---")
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8')
    err = stderr.read().decode('utf-8')
    if out:
        print(out)
    if err:
        print("ERR:", err)
    return out, err

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS, timeout=10)
print("Connected successfully via SSH!")

# 1. Setup authorized_keys
if os.path.exists(PUB_KEY_PATH):
    with open(PUB_KEY_PATH, 'r') as f:
        pub_key = f.read().strip()

    setup_ssh_cmd = f"""
mkdir -p /root/.ssh
chmod 700 /root/.ssh
grep -qF "{pub_key}" /root/.ssh/authorized_keys 2>/dev/null || echo "{pub_key}" >> /root/.ssh/authorized_keys
chmod 600 /root/.ssh/authorized_keys
"""
    run_remote(client, setup_ssh_cmd)

# 2. Deploy repo
deploy_cmd = """
mkdir -p /opt
cd /opt
if [ -d "PersonalReleaseRadar/.git" ]; then
    cd PersonalReleaseRadar && git pull origin main
else
    rm -rf PersonalReleaseRadar
    git clone https://github.com/Demetra89/PersonalReleaseRadar.git
    cd PersonalReleaseRadar
fi
if [ ! -f .env ]; then
    cp .env.example .env
fi
docker compose up -d
"""
run_remote(client, deploy_cmd)

# 3. Check docker compose status
run_remote(client, "cd /opt/PersonalReleaseRadar && docker compose ps")

client.close()
print("Deploy script completed successfully!")
