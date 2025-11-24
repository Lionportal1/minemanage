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
# Constants
CONFIG_FILE = "config.json"
INSTANCES_DIR = "instances"
INSTANCE_CONFIG_FILE = "instance.json"
BACKUP_DIR = "backups"
LOGS_DIR = "logs"
EULA_FILE = "eula.txt"
SERVER_JAR = "server.jar"

def get_global_config():
    if not os.path.exists(CONFIG_FILE):
        default_config = {
            "java_path": "java",
            "current_instance": "default",
            "admin_password_hash": ""
        }
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=4)
        return default_config
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_global_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)

def download_file_with_progress(url, dest):
    try:
        # Set a global socket timeout if not already set, or just pass timeout to urlopen
        with urllib.request.urlopen(url, timeout=60) as response:
            total_size = int(response.info().get('Content-Length', -1))
            
            with open(dest, 'wb') as out_file:
                downloaded = 0
                block_size = 8192
                
                last_update = 0
                
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    
                    out_file.write(buffer)
                    downloaded += len(buffer)
                    
                    current_time = time.time()
                    # Update max 5 times a second to avoid spamming stdout
                    if current_time - last_update > 0.2:
                        show_progress_manual(downloaded, total_size)
                        last_update = current_time
                
                # Final update
                show_progress_manual(downloaded, total_size)
                print() # Newline
                
    except Exception as e:
        print() # Ensure newline if we crash mid-bar
        raise e

def show_progress_manual(downloaded, total_size):
    output = ""
    if total_size > 0:
        percent = downloaded * 100 / total_size
        percent = min(100, percent)
        bar_length = 40
        filled_length = int(bar_length * percent // 100)
        bar = '#' * filled_length + '-' * (bar_length - filled_length)
        output = f"Downloading: [{bar}] {percent:.1f}%"
    else:
        # Convert to MB for readability if large
        if downloaded > 1024*1024:
            output = f"Downloading: {downloaded/1024/1024:.1f} MB"
        else:
            output = f"Downloading: {downloaded} bytes"
            
    # Pad with spaces to clear previous output
    sys.stdout.write(f"\r{output:<60}")
    sys.stdout.flush()

def get_instance_dir(instance_name=None):
    if instance_name:
        return os.path.join(INSTANCES_DIR, instance_name)
    config = get_global_config()
    current = config.get("current_instance", "default")
    return os.path.join(INSTANCES_DIR, current)

def load_instance_config(instance_name=None):
    base_dir = get_instance_dir(instance_name)
    cfg_path = os.path.join(base_dir, INSTANCE_CONFIG_FILE)
    
    if not os.path.exists(cfg_path):
        return {
            "ram_min": "2G",
            "ram_max": "4G",
            "server_type": "paper",
            "server_version": "1.20.2"
        }
    
    with open(cfg_path, 'r') as f:
        return json.load(f)

def save_instance_config(config, instance_name=None):
    base_dir = get_instance_dir(instance_name)
    Path(base_dir).mkdir(parents=True, exist_ok=True)
    cfg_path = os.path.join(base_dir, INSTANCE_CONFIG_FILE)
    with open(cfg_path, 'w') as f:
        json.dump(config, f, indent=4)

def migrate_to_instances():
    old_server_dir = "server"
    # Migrate if 'server' exists and 'instances/default' does NOT exist.
    # This handles the case where 'instances' might exist (e.g. user created one manually or via command before migration ran?)
    # Actually, if 'instances' exists, we should be careful.
    # But if 'server' exists, it's legacy data. We should move it to 'default'.
    
    default_dir = os.path.join(INSTANCES_DIR, "default")
    
    if os.path.exists(old_server_dir) and not os.path.exists(default_dir):
        print("Migrating to instance-based structure...")
        Path(default_dir).mkdir(parents=True, exist_ok=True)
        
        for item in os.listdir(old_server_dir):
            s = os.path.join(old_server_dir, item)
            d = os.path.join(default_dir, item)
            if os.path.exists(d):
                continue
            shutil.move(s, d)
        
        try:
            os.rmdir(old_server_dir)
        except OSError:
            # Directory might not be empty if we skipped some files
            pass
        
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                old_cfg = json.load(f)
            
            i_cfg = {
                "ram_min": old_cfg.get("ram_min", "2G"),
                "ram_max": old_cfg.get("ram_max", "4G"),
                "server_type": old_cfg.get("server_type", "paper"),
                "server_version": old_cfg.get("server_version", "1.20.2")
            }
            save_instance_config(i_cfg, "default")
            
            # Update global config to point to default
            # We need to re-read global config to preserve other keys if any
            # But here we are likely in a state where we want to set defaults
            g_cfg = get_global_config()
            g_cfg["current_instance"] = "default"
            # Preserve admin password if it was in old config
            if "admin_password_hash" in old_cfg:
                g_cfg["admin_password_hash"] = old_cfg["admin_password_hash"]
            
            save_global_config(g_cfg)
        print("Migration complete.")

def load_config(instance_name=None):
    migrate_to_instances()
    g_cfg = get_global_config()
    target = instance_name if instance_name else g_cfg.get("current_instance")
    i_cfg = load_instance_config(target)
    g_cfg.update(i_cfg)
    return g_cfg

def save_config(config):
    g_keys = ["java_path", "current_instance", "admin_password_hash"]
    g_cfg = {k: config[k] for k in g_keys if k in config}
    save_global_config(g_cfg)
    
    i_keys = ["ram_min", "ram_max", "server_type", "server_version"]
    i_cfg = {k: config[k] for k in i_keys if k in config}
    save_instance_config(i_cfg)

def ensure_directories():
    Path(get_instance_dir()).mkdir(parents=True, exist_ok=True)
    Path(BACKUP_DIR).mkdir(exist_ok=True)
    # Logs dir is usually inside server dir, but if we used a global LOGS_DIR before,
    # we should probably stick to server/logs. 
    # The previous code had LOGS_DIR = "logs" but used os.path.join(SERVER_DIR, "logs") in cmd_logs.
    # So the global LOGS_DIR constant was maybe unused or used for global logs?
    # Let's just ensure the instance logs dir exists.
    Path(os.path.join(get_instance_dir(), "logs")).mkdir(parents=True, exist_ok=True)

def get_screen_name():
    config = get_global_config()
    instance = config.get("current_instance", "default")
    return f"minemanage_{instance}"

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
    # Check if screen session exists OR if PID exists
    if get_server_pid() is not None:
        return True
        
    try:
        # grep for the screen name (redundant if get_server_pid checks screen, but good for safety)
        result = subprocess.run(["screen", "-list"], capture_output=True, text=True)
        return get_screen_name() in result.stdout
    except FileNotFoundError:
        return False

def send_command(cmd):
    if not is_server_running():
        print("Server is not running.")
        return False
    
    subprocess.run(["screen", "-S", get_screen_name(), "-X", "stuff", f"{cmd}\n"])
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
    YELLOW = '\033[93m'

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
    # Support initializing a specific instance if provided
    target_instance = getattr(args, 'instance_name', None)
    config = load_config(target_instance)
    
    # Use get_instance_dir with the target instance
    instance_dir = get_instance_dir(target_instance)
    
    # Ensure directory exists (it should if we are calling from create, but good to be safe)
    Path(instance_dir).mkdir(parents=True, exist_ok=True)
    
    jar_path = os.path.join(instance_dir, SERVER_JAR)
    eula_path = os.path.join(instance_dir, EULA_FILE)
    
    if os.path.exists(jar_path) and not args.force:
        print_info("Server jar already exists. Use --force to overwrite.")
    else:
        version = args.version if args.version else config.get("server_version", "1.20.2")
        server_type = args.type if args.type else config.get("server_type", "paper")
        
        url = ""
        if server_type == "paper":
            # PaperMC API
            # https://api.papermc.io/v2/projects/paper/versions/{version}/builds
            # We need to get the latest build
            try:
                print_info(f"Fetching latest Paper build for {version}...")
                api_base = f"https://api.papermc.io/v2/projects/paper/versions/{version}"
                with urllib.request.urlopen(api_base) as response:
                    data = json.loads(response.read().decode())
                    builds = data['builds']
                    latest_build = builds[-1]
                
                # Construct download URL
                # https://api.papermc.io/v2/projects/paper/versions/{version}/builds/{build}/downloads/{download}
                # We need to get the download name from the build info? 
                # Actually the builds list in version info is just integers.
                # We need to query the build info or just construct the name if it follows a pattern.
                # Pattern: paper-{version}-{build}.jar
                jar_name = f"paper-{version}-{latest_build}.jar"
                url = f"{api_base}/builds/{latest_build}/downloads/{jar_name}"
                
            except Exception as e:
                print_error(f"Failed to get Paper build info: {e}")
                return
        elif server_type == "fabric":
             # Fabric API
             # https://meta.fabricmc.net/v2/versions/loader/{game_version}
             try:
                print_info(f"Fetching Fabric loader info for {version}...")
                
                # Get loader version
                with urllib.request.urlopen(f"https://meta.fabricmc.net/v2/versions/loader/{version}") as response:
                    data = json.loads(response.read().decode())
                    if not data:
                        print_error(f"No Fabric loader found for version {version}.")
                        return
                    loader_version = data[0]['loader']['version']
                
                # Get installer version
                with urllib.request.urlopen("https://meta.fabricmc.net/v2/versions/installer") as response:
                    data = json.loads(response.read().decode())
                    installer_version = data[0]['version']

                # Construct download URL
                # https://meta.fabricmc.net/v2/versions/loader/{game_version}/{loader_version}/{installer_version}/server/jar
                url = f"https://meta.fabricmc.net/v2/versions/loader/{version}/{loader_version}/{installer_version}/server/jar"
                
             except Exception as e:
                print_error(f"Failed to get Fabric info: {e}")
                return
        else:
            # Vanilla
            # We need to parse the version manifest to get the URL
            # https://piston-meta.mojang.com/mc/game/version_manifest.json
            try:
                print_info(f"Fetching Vanilla version info for {version}...")
                with urllib.request.urlopen("https://piston-meta.mojang.com/mc/game/version_manifest.json") as response:
                    data = json.loads(response.read().decode())
                    
                version_url = None
                for v in data['versions']:
                    if v['id'] == version:
                        version_url = v['url']
                        break
                
                if not version_url:
                    print_error(f"Version {version} not found.")
                    return
                    
                with urllib.request.urlopen(version_url) as response:
                    v_data = json.loads(response.read().decode())
                    url = v_data['downloads']['server']['url']
                    
            except Exception as e:
                print_error(f"Failed to get Vanilla version info: {e}")
                return

        print_info(f"Downloading server jar from {url}...")
        try:
            download_file_with_progress(url, jar_path)
            print_success("Download complete.")
        except Exception as e:
            print_error(f"Download failed: {e}")
            # Clean up partial file
            if os.path.exists(jar_path):
                os.remove(jar_path)
            return

    # EULA
    if not os.path.exists(eula_path):
        print_info("Creating eula.txt...")
        with open(eula_path, 'w') as f:
            f.write("eula=true\n")
        print_success("EULA accepted (eula=true).")
    else:
        # Check if accepted
        with open(eula_path, 'r') as f:
            content = f.read()
        if "eula=true" not in content:
             print_info("Updating eula.txt to true...")
             with open(eula_path, 'w') as f:
                f.write("eula=true\n")
             print_success("EULA accepted.")
        else:
            print_error("EULA not accepted. Server will not start.")

def cmd_start(args):
    config = load_config()
    server_dir = get_instance_dir()
    jar_path = os.path.join(server_dir, SERVER_JAR)
    eula_path = os.path.join(server_dir, EULA_FILE)
    
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
    
    screen_name = get_screen_name()
    
    if args.detach:
        print_header(f"Starting server in detached mode (screen session: {screen_name})...")
        # screen -dmS name java ...
        screen_cmd = ["screen", "-dmS", screen_name] + java_cmd
        subprocess.run(screen_cmd, cwd=server_dir)
        print_success(f"Server started in background. Use 'screen -r {screen_name}' to attach.")
    else:
        print_header(f"Starting server with: {' '.join(java_cmd)}")
        print_info("Press Ctrl+C to stop safely.")
        
        try:
            process = subprocess.Popen(
                java_cmd, 
                cwd=server_dir, 
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
    
    # Get PID before killing screen
    pid = get_server_pid()
    
    try:
        # screen -X -S name quit
        subprocess.run(["screen", "-X", "-S", get_screen_name(), "quit"])
        print_success("Server session killed.")
    except Exception as e:
        print_error(f"Failed to kill session: {e}")
        
    # Ensure process is dead
    if pid:
        time.sleep(1)
        try:
            # Check if process still exists
            os.kill(pid, 0) # Does not kill, just checks
            print_warning(f"Process {pid} still alive. Force killing...")
            os.kill(pid, signal.SIGKILL)
            print_success(f"Process {pid} killed.")
        except OSError:
            # Process dead
            pass

def cmd_backup(args):
    server_dir = get_instance_dir()
    world_dir = os.path.join(server_dir, "world")
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
        shutil.make_archive(backup_path, 'zip', server_dir, "world")
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

    server_dir = get_instance_dir()
    world_dir = os.path.join(server_dir, "world")
    if os.path.exists(world_dir):
        print_info("Removing current world...")
        shutil.rmtree(world_dir)
    
    backup_path = os.path.join(BACKUP_DIR, target_backup)
    print_info("Unzipping backup...")
    try:
        shutil.unpack_archive(backup_path, server_dir) 
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
        
        server_dir = get_instance_dir()
        prop_file = os.path.join(server_dir, "server.properties")
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
    server_dir = get_instance_dir()
    log_file = os.path.join(server_dir, "logs", "latest.log")
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
        subprocess.run(["screen", "-r", get_screen_name()])
    except Exception as e:
        print_error(f"Failed to attach: {e}")

def get_server_pid():
    # Find PID of the java process running server.jar
    # We need to be careful to find the PID for THIS instance.
    # pgrep -f "server.jar" might match multiple.
    # We can check the CWD of the process or use screen pid.
    # Screen PID is safer if we can get it.
    # "screen -ls" output: 12345.minemanage_instance ...
    try:
        screen_name = get_screen_name()
        result = subprocess.run(["screen", "-list"], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if screen_name in line:
                # Line format: 12345.name (Detached)
                parts = line.strip().split('.')
                if len(parts) > 0:
                    pid_str = parts[0]
                    if pid_str.isdigit():
                        # This is the screen PID. The java process is a child of this.
                        # Getting the child of the screen process is tricky portably.
                        # Fallback to pgrep with cwd check?
                        pass
        
        # Let's stick to pgrep but filter by CWD if possible, or just hope for best for now.
        # Actually, if we use pgrep -f "server.jar", we get all of them.
        # We can iterate them and check /proc/PID/cwd (Linux) or lsof (Mac).
        # Mac: lsof -p PID | grep cwd
        
        cmd = ["pgrep", "-f", SERVER_JAR]
        result = subprocess.run(cmd, capture_output=True, text=True)
        pids = result.stdout.strip().split('\n')
        
        current_instance_dir = os.path.abspath(get_instance_dir())
        
        for pid in pids:
            if not pid: continue
            try:
                if sys.platform == "linux" or sys.platform == "linux2":
                    # Linux: Check /proc/PID/cwd
                    try:
                        cwd_link = f"/proc/{pid}/cwd"
                        if os.path.exists(cwd_link):
                            proc_cwd = os.readlink(cwd_link)
                            if proc_cwd == current_instance_dir:
                                return int(pid)
                    except (PermissionError, FileNotFoundError):
                        pass
                else:
                    # macOS/Other: Check CWD using lsof
                    lsof = subprocess.run(["lsof", "-p", pid, "-F", "n"], capture_output=True, text=True)
                    # Output contains lines like "n/path/to/cwd" (type cwd)
                    if current_instance_dir in lsof.stdout:
                        return int(pid)
            except:
                pass
                
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
    server_dir = get_instance_dir()
    prop_file = os.path.join(server_dir, "server.properties")
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

def dashboard_plugins_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== Plugin Manager ===")
        
        server_dir = get_instance_dir()
        plugins_dir = os.path.join(server_dir, "plugins")
        Path(plugins_dir).mkdir(exist_ok=True)
        plugins = [f for f in os.listdir(plugins_dir) if f.endswith(".jar")]
        
        if not plugins:
            print_info("No plugins installed.")
        else:
            print(f"{Colors.CYAN}Installed Plugins:{Colors.ENDC}")
            for i, p in enumerate(plugins):
                print(f"{i+1}. {p}")
        
        print("\nCommands:")
        print("[I]nstall (URL)")
        print("[R]emove (Filename)")
        print("[B]ack to Dashboard")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'i':
            url = input("Enter Plugin URL: ").strip()
            if url:
                # Call cmd_plugins logic by mocking args
                class Args:
                    action = "install"
                    target = url
                cmd_plugins(Args())
                input("\nPress Enter to continue...")
        elif choice == 'r':
            target_file = input("Enter Plugin Filename to remove: ").strip()
            if target_file:
                class Args:
                    action = "remove"
                    target = target_file
                cmd_plugins(Args())
                input("\nPress Enter to continue...")
        elif choice == 'b':
            break

def dashboard_instances_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== Instance Manager ===")
        
        config = get_global_config()
        current = config.get("current_instance", "default")
        
        if not os.path.exists(INSTANCES_DIR):
            print_info("No instances found.")
        else:
            instances = sorted([d for d in os.listdir(INSTANCES_DIR) if os.path.isdir(os.path.join(INSTANCES_DIR, d))])
            print(f"{Colors.CYAN}Available Instances:{Colors.ENDC}")
            for inst in instances:
                prefix = "* " if inst == current else "  "
                color = Colors.GREEN if inst == current else ""
                print(f"{prefix}{color}{inst}{Colors.ENDC}")
        
        print("\nCommands:")
        print("[C]reate (Name)")
        print("[S]elect (Name)")
        print("[D]elete (Name)")
        print("[B]ack to Dashboard")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'c':
            name = input("Enter new instance name: ").strip()
            if name:
                version = input("Enter Minecraft version (default 1.20.2): ").strip()
                if not version: version = "1.20.2"
                
                stype = input("Enter server type (vanilla/paper/fabric, default paper): ").strip().lower()
                if not stype: stype = "paper"
                
                args = argparse.Namespace(action="create", name=name, version=version, type=stype)
                cmd_instance(args)
                input("\nPress Enter to continue...")
        elif choice == 's':
            name = input("Enter instance name to select: ").strip()
            if name:
                args = argparse.Namespace(action="select", name=name)
                cmd_instance(args)
                input("\nPress Enter to continue...")
        elif choice == 'd':
            name = input("Enter instance name to delete: ").strip()
            if name:
                args = argparse.Namespace(action="delete", name=name)
                cmd_instance(args)
                input("\nPress Enter to continue...")
        elif choice == 'b':
            break

def cmd_dashboard(args):
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== MineManage Dashboard ===")
        
        # Status
        running = is_server_running()
        status_color = Colors.GREEN if running else Colors.FAIL
        status_text = "RUNNING" if running else "STOPPED"
        print(f"Status: {status_color}{status_text}{Colors.ENDC}")
        
        # Config info
        config = load_config()
        instance_name = config.get("current_instance", "default")
        print(f"Instance: {Colors.BLUE}{instance_name}{Colors.ENDC}")
        print(f"Version: {config.get('server_version')} ({config.get('server_type')})")
        print(f"RAM: {config.get('ram_min')} - {config.get('ram_max')}")
        
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
        print("[P]lugins")
        print("[M]ods")
        print("[N]etwork")
        print("[I]nstances")
        print("[B]ackup")
        print("[R]estore")
        print("[L]ogs")
        print("[Q]uit Dashboard")
        
        print("\n(Auto-refreshing stats... Press key to select command)")
        
        import select
        
        i, o, e = select.select( [sys.stdin], [], [], 2 ) # 2 second refresh
        
        if (i):
            choice = sys.stdin.readline().strip().lower()
            
            if choice == 's':
                if not running:
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
            elif choice == 'p':
                dashboard_plugins_menu()
            elif choice == 'm':
                dashboard_mods_menu()
            elif choice == 'n':
                dashboard_network_menu()
            elif choice == 'i':
                dashboard_instances_menu()
            elif choice == 'b':
                cmd_backup(None)
                input("\nPress Enter to continue...")
            elif choice == 'r':
                class Args:
                    file = None
                cmd_restore(Args())
                input("\nPress Enter to continue...")
            elif choice == 'l':
                cmd_logs(None)
                input("\nPress Enter to continue...")
            elif choice == 'q':
                break

def cmd_plugins(args):
    plugins_dir = os.path.join(SERVER_DIR, "plugins")
    Path(plugins_dir).mkdir(exist_ok=True)

    if args.action == "list":
        print_header("Plugins:")
        plugins = [f for f in os.listdir(plugins_dir) if f.endswith(".jar")]
        if not plugins:
            print_info("No plugins found.")
        else:
            for p in plugins:
                print(f"- {p}")
    
    elif args.action == "install":
        if not args.target:
            print_error("Usage: plugins install <url>")
            return
        
        url = args.target
        # Try to guess filename from URL
        filename = url.split("/")[-1]
        if not filename.endswith(".jar"):
            filename += ".jar"
            
        dest_path = os.path.join(plugins_dir, filename)
        
        print_info(f"Installing plugin from {url}...")
        download_file(url, dest_path)
        print_success(f"Installed {filename}. Restart server to load.")
        
    elif args.action == "remove":
        if not args.target:
            print_error("Usage: plugins remove <filename>")
            return
            
        target = args.target
        if not target.endswith(".jar"):
            target += ".jar"
            
        target_path = os.path.join(plugins_dir, target)
        
        if os.path.exists(target_path):
            try:
                os.remove(target_path)
                print_success(f"Removed {target}. Restart server to apply.")
            except Exception as e:
                print_error(f"Failed to remove plugin: {e}")
        else:
            print_error(f"Plugin {target} not found.")

def cmd_mods(args):
    instance_dir = get_instance_dir()
    mods_dir = os.path.join(instance_dir, "mods")
    
    if not os.path.exists(mods_dir):
        Path(mods_dir).mkdir(parents=True, exist_ok=True)
        
    if args.action == "list":
        print_header("Installed Mods:")
        files = [f for f in os.listdir(mods_dir) if f.endswith(".jar")]
        if not files:
            print_info("No mods installed.")
        else:
            for f in files:
                print(f" - {f}")
                
    elif args.action == "install":
        if not args.target:
            print_error("Usage: mods install <url>")
            return
            
        url = args.target
        filename = url.split("/")[-1]
        # Basic heuristic to ensure .jar extension
        if not filename.endswith(".jar"):
            filename += ".jar"
            
        dest = os.path.join(mods_dir, filename)
        print_info(f"Downloading mod from {url}...")
        try:
            download_file_with_progress(url, dest)
            print_success(f"Installed {filename}")
        except Exception as e:
            print_error(f"Failed to install mod: {e}")
            if os.path.exists(dest):
                os.remove(dest)
                
    elif args.action == "remove":
        if not args.target:
            print_error("Usage: mods remove <filename>")
            return
            
        target_file = args.target
        dest = os.path.join(mods_dir, target_file)
        
        if os.path.exists(dest):
            os.remove(dest)
            print_success(f"Removed {target_file}")
        else:
            print_error(f"Mod {target_file} not found.")

def dashboard_mods_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== Mod Manager ===")
        
        instance_dir = get_instance_dir()
        mods_dir = os.path.join(instance_dir, "mods")
        if not os.path.exists(mods_dir):
            Path(mods_dir).mkdir(parents=True, exist_ok=True)
            
        files = [f for f in os.listdir(mods_dir) if f.endswith(".jar")]
        
        print(f"{Colors.CYAN}Installed Mods:{Colors.ENDC}")
        if not files:
            print("  (None)")
        else:
            for f in files:
                print(f"  - {f}")
                
        print("\nCommands:")
        print("[I]nstall (URL)")
        print("[R]emove (Filename)")
        print("[B]ack to Dashboard")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'i':
            url = input("Enter Mod URL: ").strip()
            if url:
                args = argparse.Namespace(action="install", target=url)
                cmd_mods(args)
                input("\nPress Enter to continue...")
        elif choice == 'r':
            name = input("Enter filename to remove: ").strip()
            if name:
                args = argparse.Namespace(action="remove", target=name)
                cmd_mods(args)
                input("\nPress Enter to continue...")
        elif choice == 'b':
            break

def cmd_network(args):
    if args.action == "info":
        print_header("Network Information:")
        
        # Local IP
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
        except Exception:
            local_ip = "Unknown"
        print(f"Local IP: {Colors.GREEN}{local_ip}{Colors.ENDC}")
        
        # Public IP
        try:
            with urllib.request.urlopen("https://ifconfig.me", timeout=5) as response:
                public_ip = response.read().decode().strip()
        except Exception:
            public_ip = "Unknown (Check internet connection)"
        print(f"Public IP: {Colors.BLUE}{public_ip}{Colors.ENDC}")
        
        # Port
        server_dir = get_instance_dir()
        prop_file = os.path.join(server_dir, "server.properties")
        port = "25565 (Default)"
        if os.path.exists(prop_file):
            with open(prop_file, 'r') as f:
                for line in f:
                    if line.strip().startswith("server-port="):
                        port = line.strip().split("=")[1]
                        break
        print(f"Server Port: {Colors.YELLOW}{port}{Colors.ENDC}")
        
    elif args.action == "set-port":
        if not args.value:
            print_error("Usage: network set-port <port>")
            return
        
        # Reuse config set-prop logic essentially
        server_dir = get_instance_dir()
        prop_file = os.path.join(server_dir, "server.properties")
        if not os.path.exists(prop_file):
            print_error("server.properties not found. Run the server once to generate it.")
            return
            
        lines = []
        key_found = False
        with open(prop_file, 'r') as f:
            for line in f:
                if line.strip().startswith("server-port="):
                    lines.append(f"server-port={args.value}\n")
                    key_found = True
                else:
                    lines.append(line)
        
        if not key_found:
            lines.append(f"server-port={args.value}\n")
            
        with open(prop_file, 'w') as f:
            f.writelines(lines)
        print_success(f"Server port set to {args.value}")
        
    elif args.action == "upnp":
        print_info("Attempting UPnP port mapping (Experimental)...")
        # Minimal UPnP implementation
        # 1. Discover
        SSDP_ADDR = "239.255.255.250"
        SSDP_PORT = 1900
        SSDP_MX = 2
        SSDP_ST = "urn:schemas-upnp-org:service:WANIPConnection:1"

        ssdpRequest = "M-SEARCH * HTTP/1.1\r\n" + \
                        "HOST: %s:%d\r\n" % (SSDP_ADDR, SSDP_PORT) + \
                        "MAN: \"ssdp:discover\"\r\n" + \
                        "MX: %d\r\n" % (SSDP_MX) + \
                        "ST: %s\r\n" % (SSDP_ST) + "\r\n"

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(3)
        
        try:
            sock.sendto(ssdpRequest.encode(), (SSDP_ADDR, SSDP_PORT))
            resp = sock.recv(1024)
            
            # Parse location
            import re
            location_re = re.search(r'LOCATION: (.*)', resp.decode(), re.IGNORECASE)
            if not location_re:
                print_error("Could not find UPnP gateway location.")
                return
                
            location = location_re.group(1).strip()
            print_info(f"Found UPnP Gateway at {location}")
            
            # 2. Get Control URL (Skipping full XML parse for brevity, assuming standard paths or simple regex)
            # We need to fetch the XML description
            with urllib.request.urlopen(location) as response:
                desc_xml = response.read().decode()
            
            # Find control URL for WANIPConnection
            # This is very hacky regex parsing
            # Look for <serviceType>urn:schemas-upnp-org:service:WANIPConnection:1</serviceType> ... <controlURL>...</controlURL>
            # Actually, let's just find the controlURL associated with WANIPConnection
            # If multiple, pick first.
            
            # Simple heuristic: Find the service block
            service_block = re.search(r'urn:schemas-upnp-org:service:WANIPConnection:1.*?<controlURL>(.*?)</controlURL>', desc_xml, re.DOTALL)
            if not service_block:
                # Try WANPPPConnection
                service_block = re.search(r'urn:schemas-upnp-org:service:WANPPPConnection:1.*?<controlURL>(.*?)</controlURL>', desc_xml, re.DOTALL)
            
            if not service_block:
                print_error("Could not find WANIPConnection or WANPPPConnection service.")
                return
                
            control_url_path = service_block.group(1).strip()
            
            # Construct full control URL
            from urllib.parse import urlparse
            parsed = urlparse(location)
            control_url = f"{parsed.scheme}://{parsed.netloc}{control_url_path}"
            if control_url_path.startswith("http"):
                control_url = control_url_path
                
            # 3. AddPortMapping
            # Get current port
            server_dir = get_instance_dir()
            prop_file = os.path.join(server_dir, "server.properties")
            port = "25565"
            if os.path.exists(prop_file):
                with open(prop_file, 'r') as f:
                    for line in f:
                        if line.strip().startswith("server-port="):
                            port = line.strip().split("=")[1]
                            break
            
            local_ip = socket.gethostbyname(socket.gethostname())
            # Better local IP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except:
                pass

            soap_body = f"""<?xml version="1.0"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
<s:Body>
<u:AddPortMapping xmlns:u="urn:schemas-upnp-org:service:WANIPConnection:1">
<NewRemoteHost></NewRemoteHost>
<NewExternalPort>{port}</NewExternalPort>
<NewProtocol>TCP</NewProtocol>
<NewInternalPort>{port}</NewInternalPort>
<NewInternalClient>{local_ip}</NewInternalClient>
<NewEnabled>1</NewEnabled>
<NewPortMappingDescription>MineManage</NewPortMappingDescription>
<NewLeaseDuration>0</NewLeaseDuration>
</u:AddPortMapping>
</s:Body>
</s:Envelope>"""

            req = urllib.request.Request(control_url, data=soap_body.encode(), method="POST")
            req.add_header('Content-Type', 'text/xml; charset="utf-8"')
            req.add_header('SOAPAction', '"urn:schemas-upnp-org:service:WANIPConnection:1#AddPortMapping"')
            
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    print_success(f"UPnP Port Mapping successful for port {port} -> {local_ip}")
                else:
                    print_error(f"UPnP failed with status {response.status}")
                    
        except socket.timeout:
            print_error("UPnP Discovery timed out. No gateway found.")
        except Exception as e:
            print_error(f"UPnP failed: {e}")

def dashboard_network_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== Network Manager ===")
        
        # Show info immediately
        args = argparse.Namespace(action="info")
        cmd_network(args)
        
        print("\nCommands:")
        print("[P]ort (Set Port)")
        print("[U]PnP (Auto-Map Port)")
        print("[B]ack to Dashboard")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'p':
            port = input("Enter new port: ").strip()
            if port:
                args = argparse.Namespace(action="set-port", value=port)
                cmd_network(args)
                input("\nPress Enter to continue...")
        elif choice == 'u':
            args = argparse.Namespace(action="upnp")
            cmd_network(args)
            input("\nPress Enter to continue...")
        elif choice == 'b':
            break

def cmd_instance(args):
    config = get_global_config()
    current = config.get("current_instance", "default")
    
    if args.action == "list":
        print_header("Available Instances:")
        if not os.path.exists(INSTANCES_DIR):
            print_info("No instances found.")
            return
            
        instances = sorted([d for d in os.listdir(INSTANCES_DIR) if os.path.isdir(os.path.join(INSTANCES_DIR, d))])
        for inst in instances:
            prefix = "* " if inst == current else "  "
            color = Colors.GREEN if inst == current else ""
            print(f"{prefix}{color}{inst}{Colors.ENDC}")
            
    elif args.action == "create":
        if not args.name:
            print_error("Usage: instance create <name> [--version <ver>] [--type <type>]")
            return
        
        # Validate name (alphanumeric + underscore + hyphen)
        if not all(c.isalnum() or c in ('_', '-') for c in args.name):
            print_error("Instance name must be alphanumeric (underscores and hyphens allowed).")
            return
            
        target_dir = os.path.join(INSTANCES_DIR, args.name)
        if os.path.exists(target_dir):
            print_error(f"Instance {args.name} already exists.")
            return
            
        version = args.version if args.version else "1.20.2"
        server_type = args.type if args.type else "paper"
        
        print_info(f"Creating instance {args.name} ({server_type} {version})...")
        Path(target_dir).mkdir(parents=True, exist_ok=True)
        
        # Create default instance config
        default_i_cfg = {
            "ram_min": "2G",
            "ram_max": "4G",
            "server_type": server_type,
            "server_version": version
        }
        save_instance_config(default_i_cfg, args.name)
        
        # Auto-Init
        print_info("Auto-initializing instance...")
        init_args = argparse.Namespace(
            version=version,
            type=server_type,
            force=False,
            instance_name=args.name
        )
        
        cmd_init(init_args)
        
        print_success(f"Instance {args.name} created and initialized. Use 'instance select {args.name}' to switch to it.")
        
    elif args.action == "select":
        if not args.name:
            print_error("Usage: instance select <name>")
            return
            
        target_dir = os.path.join(INSTANCES_DIR, args.name)
        if not os.path.exists(target_dir):
            print_error(f"Instance {args.name} not found.")
            return
            
        if is_server_running():
            print_error("Cannot switch instances while a server is running. Stop it first.")
            return
            
        config["current_instance"] = args.name
        save_global_config(config)
        print_success(f"Switched to instance: {args.name}")
        
    elif args.action == "delete":
        if not args.name:
            print_error("Usage: instance delete <name>")
            return
            
        if args.name == current:
            print_error("Cannot delete the currently active instance. Switch to another one first.")
            return
            
        target_dir = os.path.join(INSTANCES_DIR, args.name)
        if not os.path.exists(target_dir):
            print_error(f"Instance {args.name} not found.")
            return
            
        print(f"{Colors.WARNING}WARNING: This will permanently delete instance '{args.name}' and ALL its data.{Colors.ENDC}")
        confirm = input("Are you sure? (y/n): ").lower()
        if confirm == 'y':
            try:
                shutil.rmtree(target_dir)
                print_success(f"Instance {args.name} deleted.")
            except Exception as e:
                print_error(f"Failed to delete instance: {e}")

def main():
    # Ensure migration runs before anything else
    migrate_to_instances()

    parser = argparse.ArgumentParser(description="MineManage CLI")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
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

    # Plugins command
    parser_plugins = subparsers.add_parser("plugins", help="Manage plugins")
    parser_plugins.add_argument("action", choices=["list", "install", "remove"], help="Action to perform")
    parser_plugins.add_argument("target", nargs="?", help="Plugin URL (install) or Filename (remove)")

    # Mods command
    parser_mods = subparsers.add_parser("mods", help="Manage mods")
    parser_mods.add_argument("action", choices=["list", "install", "remove"], help="Action to perform")
    parser_mods.add_argument("target", nargs="?", help="Mod URL (install) or Filename (remove)")

    # Network command
    parser_network = subparsers.add_parser("network", help="Network tools")
    parser_network.add_argument("action", choices=["info", "set-port", "upnp"], help="Action to perform")
    parser_network.add_argument("value", nargs="?", help="Value for set-port")

    # Instance command
    parser_instance = subparsers.add_parser("instance", help="Manage server instances")
    parser_instance.add_argument("action", choices=["list", "create", "select", "delete"], help="Action to perform")
    parser_instance.add_argument("name", nargs="?", help="Instance name")
    parser_instance.add_argument("--version", help="Minecraft version (create only)")
    parser_instance.add_argument("--type", choices=["vanilla", "paper", "fabric"], help="Server type (create only)")

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
    elif args.command == "plugins":
        cmd_plugins(args)
    elif args.command == "mods":
        cmd_mods(args)
    elif args.command == "network":
        cmd_network(args)
    elif args.command == "instance":
        cmd_instance(args)
    elif args.command == "logs":
        cmd_logs(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
