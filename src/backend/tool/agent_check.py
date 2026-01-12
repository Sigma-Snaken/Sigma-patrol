import os
import sys
import platform

def verify_environment():
    print("="*40)
    print("Agent Execution Verification")
    print("="*40)
    
    # Check OS
    print(f"OS: {platform.system()} {platform.release()}")
    
    # Check Python Version
    print(f"Python: {sys.version.split()[0]}")
    
    # Check Hostname (should be container ID or set hostname)
    print(f"Hostname: {platform.node()}")
    
    # Check Workdir
    print(f"Current Directory: {os.getcwd()}")
    
    # Check File System Access (Volume Mount)
    files = os.listdir('.')
    print(f"Files in /app: {files}")
    
    if 'Dockerfile' in files and 'agent_check.py' in files:
        print("\n[SUCCESS] Volume mount verified: Project files detected.")
    else:
        print("\n[dFAILURE] Volume mount issue: Project files missing.")

if __name__ == "__main__":
    verify_environment()
