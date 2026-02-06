import os
import sys
import time
import json
import subprocess
import urllib.request
import urllib.error

# Configuration
# The UUID to use for both the Proxy User and the API Report
TARGET_UUID = "779548c3-2ea9-4bea-a3b4-8618a26566ae"
REPORT_URL = f"https://traffic-recorder.aung-245.workers.dev/?uuid={TARGET_UUID}"
API_INTERVAL = 300 # 5 minutes
V2RAY_API_PORT = 10085
V2RAY_API = f"127.0.0.1:{V2RAY_API_PORT}"
USER_EMAIL = "user@v2ray"

# Paths
ORIGINAL_CONFIG = "/etc/v2ray/config.json"
RUNTIME_CONFIG = "/etc/v2ray/config_runtime.json"

def detect_binary():
    if os.system("which xray > /dev/null 2>&1") == 0:
        return "xray"
    if os.system("which v2ctl > /dev/null 2>&1") == 0:
        return "v2ctl"
    if os.system("which v2ray > /dev/null 2>&1") == 0:
        return "v2ray"
    return "v2ray" # Default fallback

V2CTL = detect_binary()
print(f"Using binary for API calls: {V2CTL}")

def generate_runtime_config():
    print("Generating runtime configuration...")
    try:
        with open(ORIGINAL_CONFIG, 'r') as f:
            config = json.load(f)
        
        # 1. Inject API
        config["api"] = {
            "tag": "api",
            "services": ["StatsService", "HandlerService", "LoggerService"]
        }
        
        # 2. Inject Stats
        config["stats"] = {}
        
        # 3. Inject Policy
        config["policy"] = {
            "levels": {
                "0": {
                    "statsUserUplink": True,
                    "statsUserDownlink": True
                }
            },
            "system": {
                "statsInboundUplink": True,
                "statsInboundDownlink": True,
                "statsOutboundUplink": True,
                "statsOutboundDownlink": True
            }
        }
        
        # 4. Inject API Inbound
        api_inbound = {
            "listen": "127.0.0.1",
            "port": V2RAY_API_PORT,
            "protocol": "dokodemo-door",
            "settings": {
                "address": "127.0.0.1"
            },
            "tag": "api"
        }
        # Prepend to inbounds
        if "inbounds" not in config:
            config["inbounds"] = []
        config["inbounds"].insert(0, api_inbound)
        
        # 5. Inject API Routing Rule
        api_rule = {
            "inboundTag": ["api"],
            "outboundTag": "api",
            "type": "field"
        }
        if "routing" not in config:
            config["routing"] = {"rules": []}
        if "rules" not in config["routing"]:
            config["routing"]["rules"] = []
        config["routing"]["rules"].insert(0, api_rule)
        
        # 6. Update User UUID in VLESS Inbound
        # Find the vless inbound (usually the one with settings.clients)
        found = False
        for inbound in config["inbounds"]:
            if inbound.get("protocol") == "vless":
                clients = inbound.get("settings", {}).get("clients", [])
                if clients:
                    # Update the first client or add if missing
                    clients[0]["id"] = TARGET_UUID
                    clients[0]["email"] = USER_EMAIL
                    clients[0]["level"] = 0
                    found = True
                    print(f"Updated VLESS client UUID to {TARGET_UUID}")
        
        if not found:
            print("Warning: Could not find VLESS inbound to update UUID.")

        with open(RUNTIME_CONFIG, 'w') as f:
            json.dump(config, f, indent=2)
            
        print(f"Runtime config saved to {RUNTIME_CONFIG}")
        return True
    except Exception as e:
        print(f"Error generating runtime config: {e}")
        return False

def run_v2ray():
    print("Starting V2Ray with runtime config...")
    # Determine the executable (v2ray or xray)
    # The Dockerfile uses 'v2ray' command usually, but let's check what's available
    # The 'detect_binary' finds the tool for API, but the runner might be different.
    # teddysun/v2ray image has 'v2ray' in path.
    
    cmd = ["v2ray", "run", "-config", RUNTIME_CONFIG]
    
    # If xray is present (some images switch), use it
    if os.system("which xray > /dev/null 2>&1") == 0:
        cmd = ["xray", "run", "-config", RUNTIME_CONFIG]

    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)
    return proc

def api_call(method, request_json):
    cmd = [V2CTL, "api", f"--server={V2RAY_API}", method]
    process = subprocess.Popen(
        cmd, 
        stdin=subprocess.PIPE, 
        stdout=subprocess.PIPE, 
        stderr=subprocess.PIPE,
        text=True
    )
    stdout, stderr = process.communicate(input=json.dumps(request_json))
    if process.returncode != 0:
        print(f"API Call Failed: {method}")
        return None
    return stdout

def query_stats():
    # Query all stats
    res = api_call("StatsService.QueryStats", {"pattern": "user>>>", "reset": False})
    if not res:
        return None
        
    try:
        data = json.loads(res)
        uplink = 0
        downlink = 0
        if 'stat' in data:
            for s in data['stat']:
                # s['name'] e.g., "user>>>user@v2ray>>>traffic>>>uplink"
                parts = s['name'].split('>>>')
                # Check if it matches our email
                if len(parts) >= 4 and parts[1] == USER_EMAIL:
                    val = int(s['value'])
                    if 'uplink' in parts[3]:
                        uplink += val
                    elif 'downlink' in parts[3]:
                        downlink += val
        return {"uplink": uplink, "downlink": downlink}
    except Exception as e:
        print(f"Error parsing stats: {e}")
        return None

def report_usage(stats):
    try:
        print(f"Reporting stats for {TARGET_UUID}: {stats}")
        # Send simple JSON payload
        req = urllib.request.Request(
            REPORT_URL, 
            data=json.dumps(stats).encode(),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req) as response:
            print(f"Report success. Status: {response.status}")
    except Exception as e:
        print(f"Error reporting stats: {e}")

def main_loop():
    if not generate_runtime_config():
        sys.exit(1)
        
    v2ray_proc = run_v2ray()
    time.sleep(10) # Wait for startup
    
    while True:
        if v2ray_proc.poll() is not None:
            print("V2Ray process exited!")
            sys.exit(1)
            
        stats = query_stats()
        if stats:
            report_usage(stats)
        
        # Sleep
        time.sleep(API_INTERVAL)

if __name__ == "__main__":
    main_loop()
