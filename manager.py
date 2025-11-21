#!/usr/bin/env python3
import argparse
import json
import os
import sys
import subprocess
import urllib.request
import urllib.error
from pathlib import Path

import shutil
import datetime
import time
import hashlib
import getpass
import socket
import struct

# Constants
CONFIG_FILE = "config.json"
SERVER_DIR = "server"
BACKUP_DIR = "backups"
LOGS_DIR = "logs"
EULA_FILE = "eula.txt"
SERVER_JAR = "server.jar"
SCREEN_NAME = "minemanage_server"
__version__ = "1.0.0"

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(f"Config file {CONFIG_FILE} not found. Creating default.")
        default_config = {
            "java_path": "java",
            "ram_min": "2G",
            "ram_max": "4G",
            "server_type": "vanilla",
            "server_version": "1.20.2"
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def ensure_directories():
    Path(SERVER_DIR).mkdir(exist_ok=True)
    Path(BACKUP_DIR).mkdir(exist_ok=True)
    Path(LOGS_DIR).mkdir(exist_ok=True)

def download_file(url, dest_path):
    print(f"Downloading {url} to {dest_path}...")
    try:
        with urllib.request.urlopen(url) as response, open(dest_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
    except Exception as e:
        print(f"Download failed: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)

def get_vanilla_url(version):
    manifest_url = "https://piston-meta.mojang.com/mc/game/version_manifest.json"
    try:
        with urllib.request.urlopen(manifest_url) as response:
            data = json.loads(response.read().decode())
        
        for v in data['versions']:
            if v['id'] == version:
                version_url = v['url']
                with urllib.request.urlopen(version_url) as v_response:
                    v_data = json.loads(v_response.read().decode())
                return v_data['downloads']['server']['url']
        
        print(f"Version {version} not found in manifest.")
        return None
    except Exception as e:
        print(f"Error fetching version info: {e}")
        return None

def is_server_running():
    # Check if screen session exists
    try:
        # grep for the screen name
        result = subprocess.run(["screen", "-list"], capture_output=True, text=True)
        return SCREEN_NAME in result.stdout
    except FileNotFoundError:
        return False

def send_command(cmd):
    if not is_server_running():
        print("Server is not running.")
        return False
    
    subprocess.run(["screen", "-S", SCREEN_NAME, "-X", "stuff", f"{cmd}\n"])
    return True

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_success(msg):
    print(f"{Colors.GREEN}{msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.FAIL}{msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.BLUE}{msg}{Colors.ENDC}")

def print_header(msg):
    print(f"{Colors.HEADER}{Colors.BOLD}{msg}{Colors.ENDC}")

def get_paper_url(version):
    # PaperMC API: https://api.papermc.io/v2/projects/paper/versions/{version}/builds
    # We need to find the latest build.
    base_url = "https://api.papermc.io/v2/projects/paper"
    try:
        # Get builds for version
        version_url = f"{base_url}/versions/{version}/builds"
        with urllib.request.urlopen(version_url) as response:
            data = json.loads(response.read().decode())
        
        if not data['builds']:
            print_error(f"No builds found for Paper version {version}")
            return None
            
        # Get latest build
        latest_build = data['builds'][-1]
        build_num = latest_build['build']
        file_name = latest_build['downloads']['application']['name']
        
        # Construct download URL
        # https://api.papermc.io/v2/projects/paper/versions/{version}/builds/{build}/downloads/{name}
        download_url = f"{base_url}/versions/{version}/builds/{build_num}/downloads/{file_name}"
        return download_url
        
    except urllib.error.HTTPError as e:
        print_error(f"Error fetching PaperMC info: {e}")
        return None
    except Exception as e:
        print_error(f"Error: {e}")
        return None

def cmd_init(args):
    ensure_directories()
    config = load_config()
    
    version = args.version if args.version else config.get("server_version", "1.20.2")
    server_type = args.type if args.type else config.get("server_type", "vanilla")
    
    print_header(f"Initializing {server_type} server version {version}...")
    
    # Update config
    config["server_version"] = version
    config["server_type"] = server_type
    save_config(config)
    
    jar_path = os.path.join(SERVER_DIR, SERVER_JAR)
    
    if os.path.exists(jar_path) and not args.force:
        print_info(f"{SERVER_JAR} already exists. Use --force to overwrite.")
    else:
        url = None
        if server_type == "vanilla":
            url = get_vanilla_url(version)
        elif server_type == "paper":
            url = get_paper_url(version)
        else:
            print_error(f"Server type {server_type} not yet supported.")
            return

        if url:
            download_file(url, jar_path)
        else:
            print_error("Failed to get download URL.")
            return

    # EULA
    eula_path = os.path.join(SERVER_DIR, EULA_FILE)
    if not os.path.exists(eula_path):
        print_info("You must accept the Minecraft EULA to run the server.")
        print("https://account.mojang.com/documents/minecraft_eula")
        agree = input("Do you agree to the EULA? (y/n): ").lower()
        if agree == 'y':
            with open(eula_path, 'w') as f:
                f.write("eula=true\n")
            print_success("EULA accepted.")
        else:
            print_error("EULA not accepted. Server will not start.")

def cmd_start(args):
    config = load_config()
    jar_path = os.path.join(SERVER_DIR, SERVER_JAR)
    eula_path = os.path.join(SERVER_DIR, EULA_FILE)
    
    if not os.path.exists(jar_path):
        print_error(f"Server jar not found at {jar_path}. Run 'init' first.")
        return

    if not os.path.exists(eula_path):
        print_error("EULA not found. Run 'init' first.")
        return
        
    # Check EULA content
    with open(eula_path, 'r') as f:
        if "eula=true" not in f.read():
            print_error("EULA not accepted in eula.txt. Please edit the file or run init again.")
            return

    if is_server_running():
        print_info("Server is already running.")
        return

    ram_min = args.ram if args.ram else config.get("ram_min", "2G")
    ram_max = args.ram if args.ram else config.get("ram_max", "4G")
    
    if args.ram:
        ram_max = args.ram
        ram_min = args.ram

    java_cmd = [
        config.get("java_path", "java"),
        f"-Xms{ram_min}",
        f"-Xmx{ram_max}",
        "-jar",
        SERVER_JAR,
        "nogui"
    ]
    
    if args.detach:
        print_header(f"Starting server in detached mode (screen session: {SCREEN_NAME})...")
        # screen -dmS name java ...
        screen_cmd = ["screen", "-dmS", SCREEN_NAME] + java_cmd
        subprocess.run(screen_cmd, cwd=SERVER_DIR)
        print_success("Server started in background. Use 'screen -r minemanage_server' to attach.")
    else:
        print_header(f"Starting server with: {' '.join(java_cmd)}")
        print_info("Press Ctrl+C to stop safely.")
        
        try:
            process = subprocess.Popen(
                java_cmd, 
                cwd=SERVER_DIR, 
                stdin=subprocess.PIPE, 
                stdout=sys.stdout, 
                stderr=sys.stderr,
                text=True
            )
            process.wait()
        except KeyboardInterrupt:
            print_info("\nReceived stop signal. Stopping server...")
            if process.poll() is None:
                try:
                    process.communicate(input="stop\n", timeout=30)
                except subprocess.TimeoutExpired:
                    process.kill()
                    print_error("Server forced to stop.")
            print_success("Server stopped.")

def cmd_stop(args):
    if is_server_running():
        print_info("Stopping server...")
        send_command("stop")
        # Wait for it to actually stop
        for _ in range(30):
            if not is_server_running():
                print_success("Server stopped.")
                return
            time.sleep(1)
        print_error("Server did not stop in time. You may need to kill the screen session.")
    else:
        print_info("Server is not running (or not in a managed screen session).")

def cmd_kill(args):
    config = load_config()
    admin_hash = config.get("admin_password_hash")
    
    if not admin_hash:
        print_error("Admin password not set. Run 'config set-password' first.")
        return

    if not is_server_running():
        print_info("Server is not running.")
        return

    print(f"{Colors.WARNING}WARNING: This will instantly kill the server process. Data loss may occur.{Colors.ENDC}")
    password = getpass.getpass("Enter admin password: ")
    
    if hashlib.sha256(password.encode()).hexdigest() != admin_hash:
        print_error("Incorrect password.")
        return
        
    print_info("Killing server session...")
    try:
        # screen -X -S name quit
        subprocess.run(["screen", "-X", "-S", SCREEN_NAME, "quit"])
        print_success("Server session killed.")
    except Exception as e:
        print_error(f"Failed to kill session: {e}")

def cmd_backup(args):
    world_dir = os.path.join(SERVER_DIR, "world")
    if not os.path.exists(world_dir):
        print_error(f"World directory {world_dir} not found. Has the server run yet?")
        return

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"backup_{timestamp}"
    backup_path = os.path.join(BACKUP_DIR, backup_name) # shutil.make_archive adds .zip

    running = is_server_running()
    
    if running:
        print_info("Server is running. Turning off auto-save...")
        send_command("save-off")
        send_command("save-all")
        time.sleep(2) # Give it a moment to save
    
    print_info(f"Creating backup {backup_name}.zip...")
    try:
        shutil.make_archive(backup_path, 'zip', SERVER_DIR, "world")
        print_success(f"Backup created at {backup_path}.zip")
    except Exception as e:
        print_error(f"Backup failed: {e}")
    finally:
        if running:
            print_info("Re-enabling auto-save...")
            send_command("save-on")

def cmd_restore(args):
    if is_server_running():
        print_error("Cannot restore while server is running. Please stop the server first.")
        return

    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.endswith(".zip")])
    if not backups:
        print_error("No backups found.")
        return

    if not args.file:
        print_header("Available backups:")
        for i, b in enumerate(backups):
            print(f"{i+1}. {b}")
        try:
            choice = int(input("Select backup number to restore: "))
            if 1 <= choice <= len(backups):
                target_backup = backups[choice-1]
            else:
                print_error("Invalid selection.")
                return
        except ValueError:
            print_error("Invalid input.")
            return
    else:
        target_backup = args.file
        if target_backup not in backups:
            print_error(f"Backup {target_backup} not found.")
            return

    print_info(f"Restoring {target_backup}...")
    print(f"{Colors.WARNING}WARNING: This will delete the current world data.{Colors.ENDC}")
    confirm = input("Are you sure? (y/n): ").lower()
    if confirm != 'y':
        print_info("Restore cancelled.")
        return

    world_dir = os.path.join(SERVER_DIR, "world")
    if os.path.exists(world_dir):
        print_info("Removing current world...")
        shutil.rmtree(world_dir)
    
    backup_path = os.path.join(BACKUP_DIR, target_backup)
    print_info("Unzipping backup...")
    try:
        shutil.unpack_archive(backup_path, SERVER_DIR) 
        print_success("Restore complete.")
    except Exception as e:
        print_error(f"Restore failed: {e}")

def cmd_config(args):
    config = load_config()
    
    if args.action == "list":
        print_header("Configuration:")
        for k, v in config.items():
            # Don't show hash
            val = v if k != "admin_password_hash" else "********"
            print(f"{Colors.CYAN}{k}{Colors.ENDC}: {val}")
    elif args.action == "set":
        if not args.key or not args.value:
            print_error("Usage: config set <key> <value>")
            return
        
        config[args.key] = args.value
        save_config(config)
        print_success(f"Set {args.key} to {args.value}")
    elif args.action == "set-prop":
        if not args.key or not args.value:
            print_error("Usage: config set-prop <key> <value>")
            return
        
        prop_file = os.path.join(SERVER_DIR, "server.properties")
        if not os.path.exists(prop_file):
            print_error(f"{prop_file} not found. Has the server run yet?")
            return
            
        lines = []
        key_found = False
        with open(prop_file, 'r') as f:
            for line in f:
                if line.strip().startswith(f"{args.key}="):
                    lines.append(f"{args.key}={args.value}\n")
                    key_found = True
                else:
                    lines.append(line)
        
        if not key_found:
            print_info(f"Property {args.key} not found in server.properties. Appending it.")
            lines.append(f"{args.key}={args.value}\n")
            
        with open(prop_file, 'w') as f:
            f.writelines(lines)
        print_success(f"Updated {args.key} to {args.value} in server.properties")
    elif args.action == "set-password":
        print_info("Setting admin password for 'kill' command.")
        p1 = getpass.getpass("Enter new password: ")
        p2 = getpass.getpass("Confirm password: ")
        
        if p1 != p2:
            print_error("Passwords do not match.")
            return
            
        if not p1:
            print_error("Password cannot be empty.")
            return
            
        config["admin_password_hash"] = hashlib.sha256(p1.encode()).hexdigest()
        save_config(config)
        print_success("Admin password set.")

def cmd_logs(args):
    log_file = os.path.join(SERVER_DIR, "logs", "latest.log")
    if not os.path.exists(log_file):
        print_error(f"Log file {log_file} not found. Has the server run yet?")
        return

    print_header(f"Streaming logs from {log_file} (Ctrl+C to exit)...")
    try:
        # tail -f equivalent
        subprocess.run(["tail", "-f", log_file])
    except KeyboardInterrupt:
        print_info("\nStopped streaming logs.")

def cmd_console(args):
    if not is_server_running():
        print_error("Server is not running.")
        return

    print_header("Attaching to server console...")
    print_info("Press Ctrl+A, then D to detach and return here.")
    print_info("Press Enter to continue...")
    input()
    
    try:
        # screen -r name
        subprocess.run(["screen", "-r", SCREEN_NAME])
    except Exception as e:
        print_error(f"Failed to attach: {e}")

def get_server_pid():
    # Find PID of the java process running server.jar
    try:
        # pgrep -f "server.jar"
        cmd = ["pgrep", "-f", SERVER_JAR]
        result = subprocess.run(cmd, capture_output=True, text=True)
        pids = result.stdout.strip().split('\n')
        
        # If multiple, we might need to be more specific, but for now take the first one
        # that isn't empty
        for pid in pids:
            if pid:
                return int(pid)
    except Exception:
        pass
    return None

def get_system_stats(pid):
    if not pid:
        return 0.0, 0
    try:
        # ps -p PID -o %cpu,rss
        cmd = ["ps", "-p", str(pid), "-o", "%cpu,rss"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            # Parse second line
            # %CPU   RSS
            # 12.5  204800
            parts = lines[1].split()
            if len(parts) >= 2:
                cpu = float(parts[0])
                rss_kb = int(parts[1])
                rss_mb = rss_kb / 1024
                return cpu, rss_mb
    except Exception:
        pass
    return 0.0, 0

def get_player_count():
    # Minecraft Server List Ping (SLP) 1.7+
    host = "localhost"
    port = 25565
    
    # Read port from server.properties if possible
    prop_file = os.path.join(SERVER_DIR, "server.properties")
    if os.path.exists(prop_file):
        with open(prop_file, 'r') as f:
            for line in f:
                if line.strip().startswith("server-port="):
                    try:
                        port = int(line.split('=')[1].strip())
                    except:
                        pass
                    break

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1.0) # Short timeout
        sock.connect((host, port))
        
        # Handshake packet
        # Length | ID | Proto Ver | Host Len | Host | Port | Next State
        host_encoded = host.encode('utf-8')
        handshake = b'\x00\x00' + struct.pack('B', len(host_encoded)) + host_encoded + struct.pack('>H', port) + b'\x01'
        length = struct.pack('B', len(handshake))
        sock.send(length + handshake)
        
        # Request packet
        sock.send(b'\x01\x00')
        
        # Read response
        # Length (varint) | ID (varint) | JSON String (string)
        # We'll just read a chunk and parse the JSON
        data = sock.recv(4096)
        sock.close()
        
        # Skip varints at start to find JSON '{'
        # This is a lazy parser but works for standard responses
        json_start = data.find(b'{')
        if json_start != -1:
            json_str = data[json_start:].decode('utf-8', errors='ignore')
            status = json.loads(json_str)
            
            online = status['players']['online']
            max_players = status['players']['max']
            return online, max_players
            
    except Exception:
        pass
        
    return None, None

def cmd_dashboard(args):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== MineManage Dashboard ===")
        
        # Status
        running = is_server_running()
        status_color = Colors.GREEN if running else Colors.FAIL
        status_text = "RUNNING" if running else "STOPPED"
        print(f"Status: {status_color}{status_text}{Colors.ENDC}")
        
        # Stats
        cpu = 0.0
        ram = 0
        players_online = "?"
        players_max = "?"
        
        if running:
            pid = get_server_pid()
            if pid:
                cpu, ram = get_system_stats(pid)
            
            p_online, p_max = get_player_count()
            if p_online is not None:
                players_online = p_online
                players_max = p_max
        
        # Config info
        config = load_config()
        print(f"Version: {config.get('server_version')} ({config.get('server_type')})")
        print(f"RAM: {config.get('ram_min')} - {config.get('ram_max')}")
        
        # Live Stats Display
        print("-" * 30)
        print(f"CPU: {cpu:.1f}%")
        print(f"RAM: {ram:.0f} MB")
        print(f"Players: {players_online} / {players_max}")
        print("-" * 30)
        
        print("\nCommands:")
        print("[S]tart (Detached)")
        print("[X] Stop (Graceful)")
        print("[K]ill (Force)")
        print("[C]onsole")
        print("[B]ackup")
        print("[R]estore")
        print("[L]ogs")
        print("[Q]uit Dashboard")
        
        print("\n(Auto-refreshing stats... Press key to select command)")
        
        # Simple non-blocking input is hard in pure Python without curses/external libs
        # So we will just ask for input and refresh only when user hits Enter or types a command
        # To make it "Live", we'd need a timeout on input.
        # Using select on stdin (Unix only)
        import select
        
        i, o, e = select.select( [sys.stdin], [], [], 2 ) # 2 second refresh
        
        if (i):
            choice = sys.stdin.readline().strip().lower()
            
            if choice == 's':
                if not running:
                    # We need to construct args object or call cmd_start manually
                    # Let's just call cmd_start with a dummy args object
                    class Args:
                        ram = None
                        detach = True
                    cmd_start(Args())
                    input("\nPress Enter to continue...")
                else:
                    print_info("Server already running.")
                    time.sleep(1)
            elif choice == 'x':
                if running:
                    cmd_stop(None)
                    input("\nPress Enter to continue...")
                else:
                    print_info("Server not running.")
                    time.sleep(1)
            elif choice == 'k':
                if running:
                    cmd_kill(None)
                    input("\nPress Enter to continue...")
                else:
                    print_info("Server not running.")
                    time.sleep(1)
            elif choice == 'c':
                cmd_console(None)
            elif choice == 'b':
                cmd_backup(None)
                input("\nPress Enter to continue...")
            elif choice == 'r':
                # Restore needs args, let's just call it and it will prompt
                class Args:
                    file = None
                cmd_restore(Args())
                input("\nPress Enter to continue...")
            elif choice == 'l':
                cmd_logs(None)
                input("\nPress Enter to continue...")
            elif choice == 'q':
                break

def main():
    parser = argparse.ArgumentParser(description="MineManage CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    parser.add_argument("--version", action="version", version=f"MineManage {__version__}")
    
    # Init command
    parser_init = subparsers.add_parser("init", help="Initialize the server")
    parser_init.add_argument("--version", help="Minecraft version (e.g., 1.20.2)")
    parser_init.add_argument("--type", choices=["vanilla", "paper", "fabric"], help="Server type")
    parser_init.add_argument("--force", action="store_true", help="Force download even if jar exists")
    
    # Start command
    parser_start = subparsers.add_parser("start", help="Start the server")
    parser_start.add_argument("--ram", help="RAM allocation (e.g. 4G)")
    parser_start.add_argument("--detach", action="store_true", help="Run in background using screen")
    
    # Stop command
    parser_stop = subparsers.add_parser("stop", help="Stop the server")

    # Kill command
    parser_kill = subparsers.add_parser("kill", help="Force kill the server")

    # Console command
    parser_console = subparsers.add_parser("console", help="Attach to server console")

    # Backup command
    parser_backup = subparsers.add_parser("backup", help="Backup the world")

    # Restore command
    parser_restore = subparsers.add_parser("restore", help="Restore a backup")
    parser_restore.add_argument("--file", help="Backup filename to restore")

    # Config command
    parser_config = subparsers.add_parser("config", help="Manage configuration")
    parser_config.add_argument("action", choices=["list", "set", "set-prop", "set-password"], help="Action to perform")
    parser_config.add_argument("key", nargs="?", help="Config key")
    parser_config.add_argument("value", nargs="?", help="Config value")

    # Logs command
    parser_logs = subparsers.add_parser("logs", help="View server logs")

    # Dashboard command
    parser_dashboard = subparsers.add_parser("dashboard", help="Open TUI dashboard")

    args = parser.parse_args()
    
    if args.command == "init":
        cmd_init(args)
    elif args.command == "start":
        cmd_start(args)
    elif args.command == "stop":
        cmd_stop(args)
    elif args.command == "kill":
        cmd_kill(args)
    elif args.command == "console":
        cmd_console(args)
    elif args.command == "backup":
        cmd_backup(args)
    elif args.command == "restore":
        cmd_restore(args)
    elif args.command == "config":
        cmd_config(args)
    elif args.command == "logs":
        cmd_logs(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
