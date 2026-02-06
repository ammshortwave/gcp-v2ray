import sys
import shutil

print(f"Python version: {sys.version}")
print(f"shutil location: {shutil.__file__}")

binaries = ["v2ray", "xray", "v2ctl"]
found = []
for b in binaries:
    path = shutil.which(b)
    if path:
        print(f"Found {b} at {path}")
        found.append(b)
    else:
        print(f"{b} not found")

if not found:
    print("CRITICAL: No V2Ray binaries found in environment!")
    sys.exit(1)
    
print("Environment check passed.")
