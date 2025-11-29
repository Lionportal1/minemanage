#!/usr/bin/env python3
import argparse
import json
import os
import sys
import subprocess
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path

import shutil
import datetime
import time
import hashlib
import getpass
import socket
import struct
import xml.etree.ElementTree as ET
from tqdm import tqdm
import miniupnpc
import readline
import zipfile

__version__ = "1.5.0"

# Check for dev mode
if os.path.exists(os.path.join(os.path.expanduser("~/.minemanage"), ".dev_mode")):
    __version__ += " (DEV)"

# Constants
# Constants
CONFIG_DIR = os.path.expanduser("~/.minemanage")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
INSTANCES_DIR = "instances"
INSTANCE_CONFIG_FILE = "instance.json"
BACKUP_DIR = "backups"
LOGS_DIR = "logs"
EULA_FILE = "eula.txt"
SERVER_JAR = "server.jar"

# Configuration Keys
GLOBAL_CONFIG_KEYS = ["java_path", "current_instance", "admin_password_hash", "login_delay"]
INSTANCE_CONFIG_KEYS = ["ram_min", "ram_max", "server_type", "server_version"]
SERVER_TYPES = ["vanilla", "paper", "fabric", "neoforge", "forge"]

def get_global_config():
    default_config = {
        "java_path": "java",
        "current_instance": "default",
        "admin_password_hash": ""
    }
    
    if not os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'w') as f:
                json.dump(default_config, f, indent=4)
        except IOError as e:
            print_error(f"Failed to create config file: {e}")
        return default_config
        
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print_error(f"Failed to load config file: {e}. Using defaults.")
        return default_config

def save_global_config(config):
    try:
        # Write to temp file first
        temp_file = CONFIG_FILE + ".tmp"
        with open(temp_file, 'w') as f:
            json.dump(config, f, indent=4)
        # Atomic rename
        os.replace(temp_file, CONFIG_FILE)
    except IOError as e:
        print_error(f"Failed to save config file: {e}")



def verify_checksum(file_path, expected_hash, algorithm='sha1'):
    """Verify the checksum of a file."""
    if not expected_hash:
        return True
        
    print_info(f"Verifying {algorithm} checksum...")
    try:
        if algorithm == 'sha1':
            hasher = hashlib.sha1()
        elif algorithm == 'sha256':
            hasher = hashlib.sha256()
        elif algorithm == 'md5':
            hasher = hashlib.md5()
        else:
            print_error(f"Unsupported checksum algorithm: {algorithm}")
            return False
            
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        
        calculated = hasher.hexdigest()
        if calculated.lower() == expected_hash.lower():
            print_success("Checksum verified.")
            return True
        else:
            print_error(f"Checksum mismatch! Expected: {expected_hash}, Got: {calculated}")
            return False
    except Exception as e:
        print_error(f"Checksum verification failed: {e}")
        return False

def download_file_with_progress(url, dest, expected_hash=None, hash_algo='sha1', retries=3):
    """Download a file with a progress bar (tqdm) and optional checksum verification."""
    attempt = 0
    while attempt <= retries:
        try:
            # Set a global socket timeout if not already set, or just pass timeout to urlopen
            with urllib.request.urlopen(url, timeout=60) as response:
                total_size = int(response.info().get('Content-Length', -1))
                
                with open(dest, 'wb') as out_file, tqdm(
                    desc=os.path.basename(dest),
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    unit_divisor=1024,
                ) as bar:
                    block_size = 8192
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        out_file.write(buffer)
                        bar.update(len(buffer))
            
            if expected_hash:
                if not verify_checksum(dest, expected_hash, hash_algo):
                    print_error("Deleting corrupted file...")
                    os.remove(dest)
                    raise Exception("Checksum mismatch")
            
            # If we get here, success
            return

        except Exception as e:
            attempt += 1
            if attempt <= retries:
                print_warning(f"Download failed: {e}. Retrying ({attempt}/{retries})...")
                time.sleep(1) # Wait a bit before retry
            else:
                print_error(f"Download failed after {retries} retries.")
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
            
    sys.stdout.write(f"\r{output:<60}")
    sys.stdout.flush()

def validate_instance_name(name):
    """Validate that the instance name contains only allowed characters."""
    if not name:
        return False
    # Allow alphanumeric, underscore, hyphen
    # Prevent path traversal (..) and other special chars
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-")
    return all(c in allowed for c in name)

def validate_filename(filename):
    """Validate a filename to prevent path traversal."""
    if not filename:
        return False
    # Basic check against path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        return False
    return True

# Helper Functions
def hash_password(password):
    """
    Hash a password using PBKDF2-HMAC-SHA256 with a random salt.
    
    Args:
        password (str): The password to hash.
        
    Returns:
        str: The salted and hashed password string.
    """
    salt = os.urandom(16)
    # 100,000 iterations is a reasonable balance for 2024
    pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    return f"{salt.hex()}${pwd_hash.hex()}"

def verify_password(stored_password, provided_password):
    """Verify a password against the stored hash (supports legacy SHA-256).

    Returns:
        - True if password matches (no action needed) [modern hash]
        - False if password does not match.
        - (True, new_hash) if password matches legacy SHA-256 hash; should upgrade to new_hash.
    """
    if "$" in stored_password:
        salt_hex, hash_hex = stored_password.split("$")
        salt = bytes.fromhex(salt_hex)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', provided_password.encode(), salt, 100000)
        return pwd_hash.hex() == hash_hex
    else:
        # Legacy SHA-256 support; transparently upgrade the hash on successful login
        print_warning("Legacy password hash detected. Your password hash will be upgraded for better security.")
        # Add delay so brute-force attempts are computationally expensive
        time.sleep(1)  # Artificial computational delay
        if hashlib.sha256(provided_password.encode()).hexdigest() == stored_password:
            # Create new PBKDF2 hash for this password
            new_hash = hash_password(provided_password)
            # Indicate caller should update the stored value to new_hash
            return True, new_hash
        else:
            return False

def read_server_properties(server_dir):
    """
    Read server.properties into a dictionary.
    
    Args:
        server_dir (str): Path to the server directory.
        
    Returns:
        dict: Dictionary of properties.
    """
    props = {}
    props_file = os.path.join(server_dir, "server.properties")
    if os.path.exists(props_file):
        with open(props_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    if "=" in line:
                        k, v = line.split("=", 1)
                        props[k.strip()] = v.strip()
    return props

def get_instance_dir(instance_name=None):
    """
    Get the directory path for a specific instance.
    
    Args:
        instance_name (str, optional): The name of the instance. 
                                       Defaults to the currently active instance.
                                       
    Returns:
        str: The absolute path to the instance directory.
    """
    if instance_name:
        return os.path.join(INSTANCES_DIR, instance_name)
    config = get_global_config()
    current = config.get("current_instance", "default")
    return os.path.join(INSTANCES_DIR, current)

def load_instance_config(instance_name=None):
    """
    Load the configuration for a specific instance.
    
    Args:
        instance_name (str, optional): The name of the instance.
        
    Returns:
        dict: The instance configuration dictionary.
    """
    instance_dir = get_instance_dir(instance_name)
    config_path = os.path.join(instance_dir, INSTANCE_CONFIG_FILE)
    if os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}

def save_instance_config(config, instance_name=None):
    """
    Save the configuration for a specific instance.
    
    Args:
        config (dict): The configuration dictionary to save.
        instance_name (str, optional): The name of the instance.
    """
    instance_dir = get_instance_dir(instance_name)
    ensure_directories(instance_dir)
    config_path = os.path.join(instance_dir, INSTANCE_CONFIG_FILE)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=4)

def cmd_migrate(args):
    """Migrate legacy server structure to instances."""
    old_server_dir = "server"
    default_dir = os.path.join(INSTANCES_DIR, "default")
    
    if not os.path.exists(old_server_dir):
        print_info("No legacy 'server' directory found. Nothing to migrate.")
        return

    if os.path.exists(default_dir):
        print_error(f"Target directory {default_dir} already exists. Cannot migrate safely.")
        return

    print_info("Migrating to instance-based structure...")
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
        
        g_cfg = get_global_config()
        g_cfg["current_instance"] = "default"
        if "admin_password_hash" in old_cfg:
            g_cfg["admin_password_hash"] = old_cfg["admin_password_hash"]
        
        save_global_config(g_cfg)
    print_success("Migration complete.")

def load_config(instance_name=None):
    # Migration is now manual via 'migrate' command
    g_cfg = get_global_config()
    target = instance_name if instance_name else g_cfg.get("current_instance")
    i_cfg = load_instance_config(target)
    g_cfg.update(i_cfg)
    return g_cfg

def save_config(config, instance_name=None):
    g_cfg = {k: config[k] for k in GLOBAL_CONFIG_KEYS if k in config}
    save_global_config(g_cfg)
    
    i_cfg = {k: config[k] for k in INSTANCE_CONFIG_KEYS if k in config}
    save_instance_config(i_cfg, instance_name)

def ensure_directories(instance_dir=None):
    if instance_dir is None:
        instance_dir = get_instance_dir()
    Path(instance_dir).mkdir(parents=True, exist_ok=True)
    Path(BACKUP_DIR).mkdir(exist_ok=True)
    Path(os.path.join(instance_dir, "logs")).mkdir(parents=True, exist_ok=True)





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



def send_command(cmd):
    if not is_server_running():
        print("Server is not running.")
        return False
    
    # Sanitize input: prevent control characters (except newline if needed, but usually cmd is single line)
    # Allow printable characters only
    if any(ord(c) < 32 or ord(c) == 127 for c in cmd):
        print_error("Invalid characters in command.")
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

def print_warning(msg):
    print(f"{Colors.WARNING}{msg}{Colors.ENDC}")

def print_header(text):
    print(f"\n{Colors.HEADER}=== {text} (v{__version__}) ==={Colors.ENDC}")

class SimpleCompleter:
    def __init__(self, options):
        self.options = sorted(options)
        
    def complete(self, text, state):
        if state == 0:
            if text:
                self.matches = [s for s in self.options if s.startswith(text)]
            else:
                self.matches = self.options[:]
        
        try:
            return self.matches[state]
        except IndexError:
            return None

def input_with_completion(prompt, options):
    """Get input with tab completion enabled for the given options."""
    completer = SimpleCompleter(options)
    readline.set_completer(completer.complete)
    
    # Enable tab completion
    if 'libedit' in readline.__doc__:
        readline.parse_and_bind("bind ^I rl_complete")
    else:
        readline.parse_and_bind("tab: complete")
        
    try:
        return input(prompt)
    finally:
        # Clear completer
        readline.set_completer(None)

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
def install_fabric(instance_dir, version):
    """Download and install Fabric."""
    print_info(f"Fetching Fabric info for Minecraft {version}...")
    try:
        # Get loader version
        with urllib.request.urlopen(f"https://meta.fabricmc.net/v2/versions/loader/{version}") as response:
            data = json.loads(response.read().decode())
            if not data:
                print_error(f"No Fabric loader found for version {version}.")
                return False
            loader_version = data[0]['loader']['version']
        
        # Get installer version
        with urllib.request.urlopen("https://meta.fabricmc.net/v2/versions/installer") as response:
            data = json.loads(response.read().decode())
            installer_version = data[0]['version']

        # Construct download URL
        # https://meta.fabricmc.net/v2/versions/loader/{game_version}/{loader_version}/{installer_version}/server/jar
        url = f"https://meta.fabricmc.net/v2/versions/loader/{version}/{loader_version}/{installer_version}/server/jar"
        
        jar_path = os.path.join(instance_dir, "server.jar")
        print_info(f"Downloading Fabric server jar from {url}...")
        download_file_with_progress(url, jar_path)
        return True
            
    except Exception as e:
        print_error(f"Failed to install Fabric: {e}")
        return False

def install_forge(instance_dir, mc_version):
    """Download and install Minecraft Forge."""
    print_info(f"Fetching Forge version for Minecraft {mc_version}...")
    try:
        # Fetch promotions_slim.json
        promo_url = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
        with urllib.request.urlopen(promo_url) as response:
            data = json.loads(response.read().decode())
        
        promos = data.get("promos", {})
        # Try recommended first, then latest
        forge_version = promos.get(f"{mc_version}-recommended")
        if not forge_version:
            forge_version = promos.get(f"{mc_version}-latest")
            
        if not forge_version:
            print_error(f"No Forge version found for Minecraft {mc_version}.")
            return False
            
        print_info(f"Found Forge version: {forge_version}")
        
        # Construct Installer URL
        # Modern (1.12.2+): https://maven.minecraftforge.net/net/minecraftforge/forge/{mc_version}-{forge_version}/forge-{mc_version}-{forge_version}-installer.jar
        # Legacy (pre-1.12): https://maven.minecraftforge.net/net/minecraftforge/forge/{mc_version}-{forge_version}-{mc_version}/forge-{mc_version}-{forge_version}-{mc_version}-installer.jar
        # Even older: Different pattern entirely
        
        # Parse MC version to determine URL structure
        version_parts = mc_version.split('.')
        major = int(version_parts[0]) if len(version_parts) > 0 else 1
        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
        
        # For very old versions (1.7.10 and below), the URL structure is different
        if major == 1 and minor <= 7:
            # Format: https://maven.minecraftforge.net/net/minecraftforge/forge/{mc_version}-{forge_version}-{mc_version}/forge-{mc_version}-{forge_version}-{mc_version}-installer.jar
            full_version = f"{mc_version}-{forge_version}-{mc_version}"
            installer_url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{full_version}/forge-{full_version}-installer.jar"
        else:
            # Modern format
            full_version = f"{mc_version}-{forge_version}"
            installer_url = f"https://maven.minecraftforge.net/net/minecraftforge/forge/{full_version}/forge-{full_version}-installer.jar"
        
        installer_path = os.path.join(instance_dir, "installer.jar")
        
        print_info(f"Downloading Forge installer from {installer_url}...")
        download_file_with_progress(installer_url, installer_path)
        
        print_info("Running Forge installer (this may take a while)...")
        # Run installer: java -jar installer.jar --installServer
        subprocess.check_call(["java", "-jar", "installer.jar", "--installServer"], cwd=instance_dir)
        
        # Cleanup
        if os.path.exists(installer_path):
            os.remove(installer_path)
        if os.path.exists(os.path.join(instance_dir, "installer.jar.log")):
             os.remove(os.path.join(instance_dir, "installer.jar.log"))
             
        return True
    except Exception as e:
        print_error(f"Failed to install Forge: {e}")
        return False

def install_neoforge(instance_dir, mc_version):
    """Download and install NeoForge."""
    print_info(f"Fetching NeoForge version for Minecraft {mc_version}...")
    try:
        # NeoForge versions usually start with the MC minor version (e.g. 20.4 for 1.20.4)
        # We need to map 1.20.4 -> 20.4
        parts = mc_version.split('.')
        if len(parts) < 2:
            print_error("Invalid Minecraft version format.")
            return False
            
        # NeoForge version prefix: "20.4"
        nf_prefix = f"{parts[1]}.{parts[2] if len(parts) > 2 else '0'}"
        
        metadata_url = "https://maven.neoforged.net/releases/net/neoforged/neoforge/maven-metadata.xml"
        req = urllib.request.Request(metadata_url)
        req.add_header("User-Agent", "MineManage/1.0")
        
        with urllib.request.urlopen(req) as response:
            xml_data = response.read()
            root = ET.fromstring(xml_data)
            
            # Find latest version matching prefix
            # Use strict matching (e.g. "21.1." to avoid matching "21.10")
            versions = []
            strict_prefix = nf_prefix + "."
            for v in root.findall(".//version"):
                if v.text.startswith(strict_prefix):
                    versions.append(v.text)
            
            if not versions:
                print_error(f"No NeoForge version found for Minecraft {mc_version}")
                return False
                
            # Sort versions? They are usually sorted in metadata, but let's take the last one (latest)
            latest_version = versions[-1]
            print_info(f"Selected NeoForge version: {latest_version}")
            
            installer_url = f"https://maven.neoforged.net/releases/net/neoforged/neoforge/{latest_version}/neoforge-{latest_version}-installer.jar"
            installer_path = os.path.join(instance_dir, "installer.jar")
            
            print_info(f"Downloading installer from {installer_url}...")
            download_file_with_progress(installer_url, installer_path)
            
            print_info("Running NeoForge installer (this may take a while)...")
            # Run installer: java -jar installer.jar --installServer
            # We are in instance_dir, so just use filename
            subprocess.check_call(["java", "-jar", "installer.jar", "--installServer"], cwd=instance_dir)
            
            # Cleanup
            os.remove(installer_path)
            
            return True
            
    except Exception as e:
        print_error(f"Failed to install NeoForge: {e}")
        return False

def install_mrpack(file_path):
    """Install a Modrinth Modpack (.mrpack)."""
    print_info(f"Importing modpack from {file_path}...")
    
    try:
        with zipfile.ZipFile(file_path, 'r') as z:
            # Check for modrinth.index.json
            if "modrinth.index.json" not in z.namelist():
                print_error("Invalid .mrpack file: modrinth.index.json not found.")
                return False
            
            # Read index
            with z.open("modrinth.index.json") as f:
                index = json.load(f)
            
            pack_name = index.get("name", "Imported Modpack")
            print_info(f"Found modpack: {pack_name}")
            
            # Extract dependencies
            mc_version = index["dependencies"]["minecraft"]
            loader = "vanilla"
            loader_version = None
            
            if "fabric-loader" in index["dependencies"]:
                loader = "fabric"
                loader_version = index["dependencies"]["fabric-loader"]
            elif "neoforge" in index["dependencies"]:
                loader = "neoforge"
                loader_version = index["dependencies"]["neoforge"]
            elif "forge" in index["dependencies"]:
                # We don't support forge yet, but let's try neoforge logic or fail
                print_error("Forge is not fully supported yet. Attempting to use NeoForge logic...")
                loader = "neoforge"
                loader_version = index["dependencies"]["forge"]
            
            print_info(f"Target: Minecraft {mc_version} ({loader} {loader_version})")
            
            # Create Instance
            # Sanitize name for directory
            safe_name = "".join(c for c in pack_name if c.isalnum() or c in (' ', '_', '-')).strip().replace(" ", "_")
            instance_dir = get_instance_dir(safe_name)
            
            if os.path.exists(instance_dir):
                print_error(f"Instance '{safe_name}' already exists.")
                confirm = input("Overwrite? [y/N]: ").lower()
                if confirm != 'y':
                    return False
                shutil.rmtree(instance_dir)
            
            # Initialize instance
            ensure_directories(instance_dir)
            
            # Save config
            config = load_config(safe_name)
            config["server_version"] = mc_version
            config["server_type"] = loader
            config["current_instance"] = safe_name
            save_config(config, safe_name)
            
            # Install Loader/Server
            args = argparse.Namespace(version=mc_version, type=loader, instance_name=safe_name)
            # Reuse cmd_init logic partially or just call install functions directly
            # cmd_init does a lot of setup, let's call the specific install functions
            
            jar_file = os.path.join(instance_dir, "server.jar")
            eula_path = os.path.join(instance_dir, "eula.txt")
            
            # EULA
            with open(eula_path, 'w') as f:
                f.write("eula=true\n")
            
            if loader == "neoforge":
                if not install_neoforge(instance_dir, mc_version): return False
            elif loader == "fabric":
                if not install_fabric(instance_dir, mc_version): return False
            elif loader == "paper": # Unlikely for mrpack but possible
                 # ... (Paper logic omitted for brevity, usually mrpacks are fabric/forge)
                 pass
            
            # Download Mods
            print_header("Downloading Mods...")
            mods_dir = os.path.join(instance_dir, "mods")
            os.makedirs(mods_dir, exist_ok=True)
            
            files = index.get("files", [])
            total_files = len(files)
            
            for i, file_data in enumerate(files):
                # Check environment
                env = file_data.get("env", {})
                if env.get("server") == "unsupported":
                    continue # Skip client-only mods
                
                download_url = file_data["downloads"][0]
                file_path = file_data["path"] # e.g. "mods/fabric-api.jar"
                file_name = os.path.basename(file_path)
                
                # We flatten mods structure usually, but let's respect path if it's in subfolders?
                # MineManage expects mods in 'mods/' root usually.
                # Let's put them in mods/
                dest_path = os.path.join(mods_dir, file_name)
                
                print(f"[{i+1}/{total_files}] Downloading {file_name}...")
                try:
                    download_file_with_progress(download_url, dest_path)
                except Exception as e:
                    print_error(f"Failed to download {file_name}: {e}")
            
            # Extract Overrides
            # .mrpack can have an 'overrides' folder in the zip that needs to be copied to root
            for item in z.namelist():
                if item.startswith("overrides/"):
                    # Extract stripping 'overrides/' prefix
                    target_path = os.path.join(instance_dir, item[len("overrides/"):])
                    if item.endswith("/"):
                        os.makedirs(target_path, exist_ok=True)
                    else:
                        # Ensure parent dir exists
                        os.makedirs(os.path.dirname(target_path), exist_ok=True)
                        with z.open(item) as source, open(target_path, "wb") as dest:
                            shutil.copyfileobj(source, dest)
                            
            print_success(f"Modpack '{pack_name}' imported successfully!")
            print_info(f"Instance '{safe_name}' is now active.")
            return True

    except Exception as e:
        print_error(f"Failed to import modpack: {e}")
        return False

def install_modpack_from_api(slug_or_id):
    """Install a modpack from Modrinth API."""
    print_info(f"Fetching modpack info for '{slug_or_id}'...")
    
    try:
        # Get Project
        url = f"https://api.modrinth.com/v2/project/{slug_or_id}"
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "MineManage/1.0 (launcher)")
        
        with urllib.request.urlopen(req) as response:
            project = json.load(response)
            
        print_info(f"Found project: {project['title']}")
        
        # Get Versions
        # We want the latest version compatible with any loader we support
        # But modpacks usually define the loader. So let's just get the latest version.
        versions_url = f"https://api.modrinth.com/v2/project/{slug_or_id}/version"
        req = urllib.request.Request(versions_url)
        req.add_header("User-Agent", "MineManage/1.0 (launcher)")
        
        with urllib.request.urlopen(req) as response:
            versions = json.load(response)
            
        if not versions:
            print_error("No versions found for this modpack.")
            return
            
        # Find a version with a .mrpack file
        target_version = None
        target_file = None
        
        for v in versions:
            for f in v['files']:
                if f['filename'].endswith('.mrpack'):
                    target_version = v
                    target_file = f
                    break
            if target_version:
                break
                
        if not target_version:
            print_error("No .mrpack file found in recent versions.")
            return
            
        print_info(f"Selected version: {target_version['name']} ({target_version['version_number']})")
        
        # Download
        download_url = target_file['url']
        filename = target_file['filename']
        print_info(f"Downloading {filename}...")
        
        download_file_with_progress(download_url, filename)
        
        # Install
        if install_mrpack(filename):
            # Clean up
            os.remove(filename)
        
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print_error("Modpack not found.")
        else:
            print_error(f"API Error: {e}")
    except Exception as e:
        print_error(f"Failed to install modpack: {e}")

def cmd_modpacks(args):
    if args.action == "search":
        if not args.target:
            print_error("Usage: modpacks search <query>")
            return
        
        print_info(f"Searching for modpacks matching '{args.target}'...")
        hits = search_modrinth(args.target, "", [], project_type="modpack")
        
        if not hits:
            print_info("No results found.")
            return
            
        print_header(f"Found {len(hits)} modpacks:")
        for hit in hits:
            print(f"• {Colors.GREEN}{hit['title']}{Colors.ENDC} (Slug: {hit['slug']})")
            print(f"  {hit['description'][:60]}...")
            
    elif args.action == "install":
        if not args.target:
            print_error("Usage: modpacks install <slug|file.mrpack>")
            return
            
        target = args.target
        if target.endswith(".mrpack"):
            if not validate_filename(target):
                print_error("Invalid filename. Path traversal is not allowed.")
                return
            if not os.path.exists(target):
                print_error(f"File not found: {target}")
                return
            install_mrpack(target)
        else:
            install_modpack_from_api(target)

def install_server_core(instance_name, version, server_type):
    """Core logic to install server jar and dependencies."""
    instance_dir = get_instance_dir(instance_name)
    ensure_directories(instance_dir)
    
    print_header(f"Initializing instance {Colors.BLUE}{instance_name}{Colors.ENDC} ({server_type} {version})...")

    # Check if server jar exists
    jar_file = os.path.join(instance_dir, "server.jar")
    eula_path = os.path.join(instance_dir, "eula.txt")
    
    if server_type == "neoforge":
        if not install_neoforge(instance_dir, version):
            return False
    elif server_type == "forge":
        if not install_forge(instance_dir, version):
            return False
    elif server_type == "fabric":
        if not install_fabric(instance_dir, version):
            return False
    elif server_type == "paper":
        builds_url = f"https://api.papermc.io/v2/projects/paper/versions/{version}/builds"
        try:
            with urllib.request.urlopen(builds_url) as response:
                data = json.loads(response.read().decode())
                latest_build = data["builds"][-1]["build"]
                download = data["builds"][-1]["downloads"]["application"]["name"]
                
                download_url = f"https://api.papermc.io/v2/projects/paper/versions/{version}/builds/{latest_build}/downloads/{download}"
                
                print_info(f"Downloading Paper {version} build {latest_build}...")
                download_file_with_progress(download_url, jar_file)
        except Exception as e:
            print_error(f"Failed to download Paper: {e}")
            return False
        else:
            pass # Success
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
                return False
                
            with urllib.request.urlopen(version_url) as response:
                v_data = json.loads(response.read().decode())
                url = v_data['downloads']['server']['url']
                
        except Exception as e:
            print_error(f"Failed to get Vanilla version info: {e}")
            return False

        print_info(f"Downloading server jar from {url}...")
        try:
            download_file_with_progress(url, jar_file)
            print_success("Download complete.")
        except Exception as e:
            print_error(f"Download failed: {e}")
            # Clean up partial file
            if os.path.exists(jar_file):
                os.remove(jar_file)
            return False

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
            pass # Already accepted
            
    return True

def cmd_init(args):
    # Support initializing a specific instance if provided
    target_instance = getattr(args, 'instance_name', None)
    
    if target_instance:
        instance_name = target_instance
    else:
        # Load global config to find current instance
        global_config = load_config()
        instance_name = global_config.get("current_instance", "default")
    
    # Use get_instance_dir with the target instance
    instance_dir = get_instance_dir(instance_name)
    ensure_directories(instance_dir)
    
    # Load existing config or create new
    config = load_config(instance_name)
    
    # Determine version and type
    version = args.version if args.version else config.get("server_version", "1.20.4")
    server_type = args.type if args.type else config.get("server_type", "vanilla")
    
    # Save to config immediately
    config["server_version"] = version
    config["server_type"] = server_type
    config["current_instance"] = instance_name # Set as current
    save_config(config, instance_name)
    
    install_server_core(instance_name, version, server_type)

def _get_forge_launch_command(server_dir, config, ram_min, ram_max):
    """
    Constructs the launch command for Forge/NeoForge servers.
    Handles both modern (run.sh/bat) and legacy (jar-based) launch methods.
    """
    run_script = "run.bat" if os.name == 'nt' else "run.sh"
    run_path = os.path.join(server_dir, run_script)
    
    if not os.path.exists(run_path):
            # Check for legacy Forge (jar file)
            # Legacy forge (1.16.5 and older) uses a forge-x.y.z.jar
            forge_jars = [f for f in os.listdir(server_dir) if f.startswith("forge-") and f.endswith(".jar") and "installer" not in f]
            
            if not forge_jars:
                print_error(f"NeoForge/Forge run script not found at {run_path} and no legacy Forge jar found. Run 'init' first.")
                return None
            
            # Found legacy jar
            legacy_jar = forge_jars[0]
            print_info(f"Detected Legacy Forge JAR: {legacy_jar}")
            
            return [
            config.get("java_path", "java"),
            f"-Xms{ram_min}",
            f"-Xmx{ram_max}",
            "-jar",
            legacy_jar,
            "nogui"
        ]
    else:
        # Modern Forge/NeoForge logic
        # Update user_jvm_args.txt with RAM settings
        jvm_args_path = os.path.join(server_dir, "user_jvm_args.txt")
        
        # Read existing args to preserve other settings
        existing_lines = []
        if os.path.exists(jvm_args_path):
            with open(jvm_args_path, 'r') as f:
                existing_lines = f.readlines()
        
        # Filter out old memory settings
        new_lines = [l for l in existing_lines if not l.strip().startswith("-Xms") and not l.strip().startswith("-Xmx")]
        
        # Append new memory settings
        if new_lines and not new_lines[-1].endswith('\n'):
            new_lines[-1] += '\n'
        new_lines.append(f"-Xms{ram_min}\n")
        new_lines.append(f"-Xmx{ram_max}\n")
        
        with open(jvm_args_path, 'w') as f:
            f.writelines(new_lines)
            
        # Ensure it's executable
        if os.name != 'nt':
            os.chmod(run_path, 0o755)

        # Launch command is just the script
        return [f"./{run_script}"]

def _get_vanilla_launch_command(server_dir, config, ram_min, ram_max):
    """Constructs the launch command for Vanilla/Paper/Fabric servers."""
    jar_path = os.path.join(server_dir, SERVER_JAR)
    if not os.path.exists(jar_path):
        print_error(f"Server jar not found at {jar_path}. Run 'init' first.")
        return None

    return [
        config.get("java_path", "java"),
        f"-Xms{ram_min}",
        f"-Xmx{ram_max}",
        "-jar",
        SERVER_JAR,
        "nogui"
    ]

def cmd_start(args):
    config = load_config()
    
    # Determine target instance
    target_instance = config.get("current_instance", "default")
    if hasattr(args, 'name') and args.name:
        target_instance = args.name
        
    server_dir = os.path.abspath(get_instance_dir(target_instance))
    jar_path = os.path.join(server_dir, SERVER_JAR)
    eula_path = os.path.join(server_dir, EULA_FILE)
    
    if not os.path.exists(eula_path):
        print_error(f"EULA not found for '{target_instance}'. Run 'init' first.")
        return
        
    # Check EULA content
    with open(eula_path, 'r') as f:
        if "eula=true" not in f.read():
            print_error(f"EULA not accepted for '{target_instance}'. Please edit eula.txt or run init again.")
            return

    if is_server_running(target_instance):
        print_info(f"Server '{target_instance}' is already running.")
        return

    # Load instance config
    i_cfg = load_instance_config(target_instance)
    
    # Check for port conflicts
    # Get target port
    props = read_server_properties(server_dir)
    target_port = int(props.get("server-port", "25565"))
    
    # Check if port is actually in use by ANY process
    if is_port_in_use(target_port):
        print_error(f"Port conflict! Port {target_port} is already in use by another process.")
        return

    ram_min = args.ram if args.ram else i_cfg.get("ram_min", "2G")
    ram_max = args.ram if args.ram else i_cfg.get("ram_max", "4G")
    
    if args.ram:
        ram_max = args.ram
        ram_min = args.ram

    # Construct command
    launch_cmd = []
    
    stype = i_cfg.get("server_type", "vanilla")
    if stype == "neoforge" or stype == "forge":
        launch_cmd = _get_forge_launch_command(server_dir, i_cfg, ram_min, ram_max)
    else:
        launch_cmd = _get_vanilla_launch_command(server_dir, i_cfg, ram_min, ram_max)

    if not launch_cmd:
        return

    # Execute
    if not args.attach:
        # Run in screen
        screen_name = get_screen_name(target_instance)
        
        print_info(f"Starting server '{target_instance}' in detached screen session '{screen_name}'...")
        
        # Construct screen command
        cmd_str = " ".join(launch_cmd)
        full_cmd = f"cd \"{server_dir}\" && {cmd_str}"
        
        try:
            subprocess.run(["screen", "-dmS", screen_name, "bash", "-c", full_cmd], cwd=server_dir, check=True)
            print_success(f"Server '{target_instance}' started.")
            print_info(f"Use 'minemanage console {target_instance}' to view the console.")
        except subprocess.CalledProcessError as e:
            print_error(f"Failed to start screen session: {e}")
        except FileNotFoundError:
            print_error("Failed to start server: 'screen' command not found. Please install screen.")
        except Exception as e:
            print_error(f"An unexpected error occurred while starting the server: {e}")
            
    else:
        # Run in foreground
        print_info(f"Starting server '{target_instance}' in foreground (Ctrl+C to stop)...")
        try:
            subprocess.run(launch_cmd, cwd=server_dir)
        except KeyboardInterrupt:
            print_info("\nServer stopped.")
        except FileNotFoundError:
            print_error(f"Failed to start server: Java executable not found. Please check your config.")
        except Exception as e:
            print_error(f"An unexpected error occurred: {e}")

def cmd_stop(args):
    config = load_config()
    target_instance = config.get("current_instance", "default")
    if hasattr(args, 'name') and args.name:
        target_instance = args.name

    if is_server_running(target_instance):
        print_info(f"Stopping server '{target_instance}'...")
        # We need to send the command to the specific screen session
        # send_command uses is_server_running() which defaults to current.
        # We need to refactor send_command or just use subprocess directly here for robustness
        
        # Refactored send_command logic inline for specific instance:
        screen_name = get_screen_name(target_instance)
        cmd = "stop"
        try:
            subprocess.run(["screen", "-S", screen_name, "-X", "stuff", f"{cmd}\r"], check=True)
        except subprocess.CalledProcessError:
            print_error(f"Failed to send stop command to '{target_instance}'.")
            
        # Wait for it to actually stop
        for _ in range(30):
            if not is_server_running(target_instance):
                print_success(f"Server '{target_instance}' stopped.")
                return
            time.sleep(1)
        print_error(f"Server '{target_instance}' did not stop in time. You may need to kill the screen session.")
    else:
        print_info(f"Server '{target_instance}' is not running.")

# ... (skipping to cmd_console)

def cmd_console(args):
    config = load_config()
    target_instance = config.get("current_instance", "default")
    if hasattr(args, 'name') and args.name:
        target_instance = args.name

    if not is_server_running(target_instance):
        print_error(f"Server '{target_instance}' is not running.")
        return

    print_header(f"Attaching to server console for '{target_instance}'...")
    print_info("Press Ctrl+A, then D to detach and return here.")
    print_info("Press Enter to continue...")
    input()
    
    try:
        # screen -r name
        subprocess.run(["screen", "-r", get_screen_name(target_instance)])
    except Exception as e:
        print_error(f"Failed to attach: {e}")

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
    
    if not verify_password(admin_hash, password):
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
        # Calculate total files for progress bar
        file_count = 0
        for root, dirs, files in os.walk(server_dir):
            if "backups" in root or "logs" in root or "cache" in root or "libraries" in root or "versions" in root:
                continue
            file_count += len(files)

        # Use zipfile to manually include all files except exclusions
        with zipfile.ZipFile(f"{backup_path}.zip", 'w', zipfile.ZIP_DEFLATED) as zipf:
            with tqdm(total=file_count, unit="file", desc="Backing up") as pbar:
                for root, dirs, files in os.walk(server_dir):
                    # Exclude backup directory itself and logs/cache/libraries/versions to save space
                    if "backups" in root or "logs" in root or "cache" in root or "libraries" in root or "versions" in root:
                        continue
                        
                    for file in files:
                        file_path = os.path.join(root, file)
                        arcname = os.path.relpath(file_path, server_dir)
                        zipf.write(file_path, arcname)
                        pbar.update(1)
                    
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

    target_backup = None
    if args.filename:
        target_backup = args.filename
    elif args.file:
        target_backup = args.file

    if not target_backup:
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


    backup_path = os.path.join(BACKUP_DIR, target_backup)
    if not os.path.exists(backup_path):
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
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            file_list = zipf.namelist()
            with tqdm(total=len(file_list), unit="file", desc="Restoring") as pbar:
                for file in file_list:
                    zipf.extract(file, server_dir)
                    pbar.update(1)
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
            
        config["admin_password_hash"] = hash_password(p1)
        save_config(config)
        print_success("Admin password set.")
    elif args.action == "properties":
        edit_server_properties()

def edit_server_properties():
    server_dir = get_instance_dir()
    prop_file = os.path.join(server_dir, "server.properties")
    
    if not os.path.exists(prop_file):
        print_error("server.properties not found. Run the server once to generate it.")
        return

    # Helper to read properties
    def read_props():
        props = {}
        with open(prop_file, 'r') as f:
            for line in f:
                if "=" in line and not line.startswith("#"):
                    k, v = line.strip().split("=", 1)
                    props[k] = v
        return props

    # Helper to write a property
    def write_prop(key, value):
        lines = []
        key_found = False
        with open(prop_file, 'r') as f:
            for line in f:
                if line.strip().startswith(f"{key}="):
                    lines.append(f"{key}={value}\n")
                    key_found = True
                else:
                    lines.append(line)
        if not key_found:
            lines.append(f"{key}={value}\n")
        with open(prop_file, 'w') as f:
            f.writelines(lines)

    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== Server Properties Editor ===")
        props = read_props()
        
        # Define menu items: (Label, Property Key, Current Value)
        menu_items = [
            ("Gamemode", "gamemode", props.get("gamemode", "survival")),
            ("Difficulty", "difficulty", props.get("difficulty", "easy")),
            ("PVP", "pvp", props.get("pvp", "true")),
            ("Whitelist", "white-list", props.get("white-list", "false")),
            ("Max Players", "max-players", props.get("max-players", "20")),
            ("Online Mode", "online-mode", props.get("online-mode", "true")),
            ("MOTD", "motd", props.get("motd", "A Minecraft Server"))
        ]
        
        for i, (label, key, val) in enumerate(menu_items):
            print(f"[{i+1}] {label}: {Colors.CYAN}{val}{Colors.ENDC}")
        print("[B]ack to Dashboard")
        
        choice = input("\nSelect option to edit: ").lower()
        
        if choice == 'b':
            break
            
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(menu_items):
                label, key, current_val = menu_items[idx]
                
                # Handle toggles/cycles
                if key == "pvp" or key == "white-list" or key == "online-mode":
                    new_val = "false" if current_val == "true" else "true"
                    write_prop(key, new_val)
                elif key == "gamemode":
                    modes = ["survival", "creative", "adventure", "spectator"]
                    try:
                        curr_idx = modes.index(current_val)
                        new_val = modes[(curr_idx + 1) % len(modes)]
                    except ValueError:
                        new_val = "survival"
                    write_prop(key, new_val)
                elif key == "difficulty":
                    diffs = ["peaceful", "easy", "normal", "hard"]
                    try:
                        curr_idx = diffs.index(current_val)
                        new_val = diffs[(curr_idx + 1) % len(diffs)]
                    except ValueError:
                        new_val = "easy"
                    write_prop(key, new_val)
                else:
                    # Text input
                    new_val = input(f"Enter new value for {label} (current: {current_val}): ").strip()
                    if new_val:
                        write_prop(key, new_val)
        except ValueError:
            pass

def get_uuid(username):
    """Fetch UUID from Mojang API."""
    try:
        url = f"https://api.mojang.com/users/profiles/minecraft/{username}"
        with urllib.request.urlopen(url) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                # Mojang returns UUID without dashes, Minecraft uses dashes
                raw_uuid = data['id']
                formatted_uuid = f"{raw_uuid[:8]}-{raw_uuid[8:12]}-{raw_uuid[12:16]}-{raw_uuid[16:20]}-{raw_uuid[20:]}"
                return formatted_uuid, data['name']
    except Exception as e:
        pass
    return None, None

def cmd_users(args):
    if not args.list_type or not args.action:
        print_error("Usage: users <whitelist|ops> <add|remove|list> [username]")
        return

    list_type = args.list_type # whitelist or ops
    action = args.action # add, remove, list
    username = args.username

    server_dir = get_instance_dir()
    
    # Map list_type to filename
    if list_type == "bans":
        json_file = os.path.join(server_dir, "banned-players.json")
    else:
        json_file = os.path.join(server_dir, f"{list_type}.json") # whitelist.json or ops.json

    # If server is running, use console commands
    if is_server_running():
        if action == "list":
            cmd = f"{list_type} list"
            if list_type == "bans":
                cmd = "banlist players"
            send_command(cmd)
            # We can't easily capture output from screen, so we just say check console/logs
            print_info(f"Sent '{cmd}' to server. Check logs or console.")
        elif action == "add":
            if not username:
                print_error("Username required.")
                return
            # For ops, command is 'op', for whitelist it's 'whitelist add'
            if list_type == "ops":
                cmd = f"op {username}"
            elif list_type == "bans":
                cmd = f"ban {username}"
            else:
                cmd = f"whitelist add {username}"
            
            send_command(cmd)
            print_success(f"Sent '{cmd}' to server.")
        elif action == "remove":
            if not username:
                print_error("Username required.")
                return
                
            if list_type == "ops":
                cmd = f"deop {username}"
            elif list_type == "bans":
                cmd = f"pardon {username}"
            else:
                cmd = f"whitelist remove {username}"
                
            send_command(cmd)
            print_success(f"Sent '{cmd}' to server.")
        return

    # If server is stopped, edit JSON files
    print_info(f"Server stopped. Editing {list_type}.json directly...")
    
    # Ensure file exists
    if not os.path.exists(json_file):
        with open(json_file, 'w') as f:
            json.dump([], f)

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except json.JSONDecodeError:
        data = []

    if action == "list":
        print_header(f"{list_type.capitalize()} List:")
        if not data:
            print("  (Empty)")
        for entry in data:
            print(f"  - {entry.get('name', 'Unknown')} ({entry.get('uuid', 'Unknown')})")

    elif action == "add":
        if not username:
            print_error("Username required.")
            return
        
        # Check if already exists
        for entry in data:
            if entry.get('name', '').lower() == username.lower():
                print_error(f"{username} is already in {list_type}.")
                return

        print_info(f"Fetching UUID for {username}...")
        uuid, real_name = get_uuid(username)
        
        if not uuid:
            print_error("Could not find UUID. Is the username correct? (Offline editing requires valid Mojang account)")
            return
            
        new_entry = {
            "uuid": uuid,
            "name": real_name
        }
        
        # Ops need extra fields
        if list_type == "ops":
            new_entry["level"] = 4
            new_entry["bypassesPlayerLimit"] = False

        data.append(new_entry)
        with open(json_file, 'w') as f:
            json.dump(data, f, indent=4)
        print_success(f"Added {real_name} to {list_type}.")

    elif action == "remove":
        if not username:
            print_error("Username required.")
            return
        
        initial_len = len(data)
        data = [entry for entry in data if entry.get('name', '').lower() != username.lower()]
        
        if len(data) < initial_len:
            with open(json_file, 'w') as f:
                json.dump(data, f, indent=4)
            print_success(f"Removed {username} from {list_type}.")
        else:
            print_error(f"{username} not found in {list_type}.")

def manage_user_list(list_type, display_name):
    """Generic menu for managing whitelist/ops."""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header(f"=== Manage {display_name} ===")
        
        # Show list immediately
        args = argparse.Namespace(list_type=list_type, action="list", username=None)
        cmd_users(args)
        
        print("\nCommands:")
        print(f"[A]dd to {display_name}")
        print(f"[R]emove from {display_name}")
        print("[B]ack")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'a':
            username = input("Enter username: ").strip()
            if username:
                args = argparse.Namespace(list_type=list_type, action="add", username=username)
                cmd_users(args)
                input("\nPress Enter to continue...")
        elif choice == 'r':
            # Get names for completion
            names = []
            if not is_server_running():
                f_path = os.path.join(get_instance_dir(), f"{list_type}.json")
                if os.path.exists(f_path):
                    try:
                        with open(f_path, 'r') as f:
                            names = [u['name'] for u in json.load(f)]
                    except: pass
            
            username = input_with_completion("Enter username to remove (Tab to complete): ", names).strip()
            if username:
                args = argparse.Namespace(list_type=list_type, action="remove", username=username)
                cmd_users(args)
                input("\nPress Enter to continue...")
        elif choice == 'b':
            break

def manage_bans_menu():
    """Menu for managing bans."""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== Manage Bans ===")
        print("\nCommands:")
        print("[B]an Player")
        print("[U]nban Player")
        print("[I]P Ban")
        print("[Un]ban IP")
        print("[L]ist Bans")
        print("[Back] to User Menu")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'b':
            username = input("Enter username to ban: ").strip()
            reason = input("Enter reason (optional): ").strip()
            if username:
                # We don't have a direct cmd_users action for ban yet, 
                # but we can use console command if running, or manual JSON edit if not.
                # For now, let's rely on console commands as bans are usually runtime.
                if is_server_running():
                    cmd = f"ban {username} {reason}"
                    send_command(cmd)
                    print_success(f"Banned {username}")
                else:
                    print_error("Server must be running to ban players (for now).")
                input("\nPress Enter to continue...")
        elif choice == 'u':
            username = input("Enter username to unban: ").strip()
            if username:
                if is_server_running():
                    send_command(f"pardon {username}")
                    print_success(f"Unbanned {username}")
                else:
                    print_error("Server must be running to unban players.")
                input("\nPress Enter to continue...")
        elif choice == 'i':
            ip = input("Enter IP to ban: ").strip()
            reason = input("Enter reason (optional): ").strip()
            if ip:
                if is_server_running():
                    send_command(f"ban-ip {ip} {reason}")
                    print_success(f"Banned IP {ip}")
                else:
                    print_error("Server must be running to ban IPs.")
                input("\nPress Enter to continue...")
        elif choice == 'un':
            ip = input("Enter IP to unban: ").strip()
            if ip:
                if is_server_running():
                    send_command(f"pardon-ip {ip}")
                    print_success(f"Unbanned IP {ip}")
                else:
                    print_error("Server must be running to unban IPs.")
                input("\nPress Enter to continue...")
        elif choice == 'l':
            print_header("Banned Players:")
            if is_server_running():
                send_command("banlist players")
            else:
                # Try reading banned-players.json
                f_path = os.path.join(get_instance_dir(), "banned-players.json")
                if os.path.exists(f_path):
                    try:
                        with open(f_path, 'r') as f:
                            bans = json.load(f)
                            for b in bans:
                                print(f"- {b['name']} (Reason: {b.get('reason', 'None')})")
                    except: print("Could not read ban list.")
            
            print_header("Banned IPs:")
            if is_server_running():
                send_command("banlist ips")
            else:
                 f_path = os.path.join(get_instance_dir(), "banned-ips.json")
                 if os.path.exists(f_path):
                    try:
                        with open(f_path, 'r') as f:
                            bans = json.load(f)
                            for b in bans:
                                print(f"- {b['ip']} (Reason: {b.get('reason', 'None')})")
                    except: print("Could not read ban list.")
            input("\nPress Enter to continue...")
        elif choice == 'back':
            break

def dashboard_users_menu():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== User Manager ===")
        print("\nCommands:")
        print("[W]hitelist")
        print("[O]perators")
        print("[B]ans")
        print("[Back] to Configuration Menu")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'w':
            manage_user_list("whitelist", "Whitelist")
        elif choice == 'o':
            manage_user_list("ops", "Operators")
        elif choice == 'b':
            manage_bans_menu()
        elif choice == 'back':
            break

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
    config = load_config()
    target_instance = config.get("current_instance", "default")
    if hasattr(args, 'name') and args.name:
        target_instance = args.name

    if not is_server_running(target_instance):
        print_error(f"Server '{target_instance}' is not running.")
        return

    print_header(f"Attaching to server console for '{target_instance}'...")
    print_info("Press Ctrl+A, then D to detach and return here.")
    print_info("Press Enter to continue...")
    input()
    
    try:
        # screen -r name
        subprocess.run(["screen", "-r", get_screen_name(target_instance)])
    except Exception as e:
        print_error(f"Failed to attach: {e}")

def get_screen_name(instance_name=None):
    """
    Get the screen session name for a specific instance.
    Defaults to the currently selected instance if none provided.
    """
    if not instance_name:
        config = get_global_config()
        instance_name = config.get("current_instance", "default")
    return f"minemanage_{instance_name}"

def get_server_pid(instance_name=None):
    """
    Get the PID of the screen session for the specified instance.
    Reliably parses 'screen -ls' output.
    """
    screen_name = get_screen_name(instance_name)
    try:
        # Run screen -ls
        # Output format:
        # There is a screen on:
        # 	12345.minemanage_default	(Detached)
        # 1 Socket in /run/screen/S-user.
        
        result = subprocess.run(["screen", "-list"], capture_output=True, text=True)
        output = result.stdout
        
        if screen_name not in output:
            return None
            
        for line in output.splitlines():
            line = line.strip()
            if screen_name in line:
                # Extract PID: "12345.minemanage_default" -> "12345"
                parts = line.split('.')
                if parts and parts[0].isdigit():
                    return int(parts[0])
    except Exception:
        pass
        
    return None

def is_server_running(instance_name=None):
    """
    Check if the server instance is currently running.
    Checks for both a PID and the screen session existence.
    """
    # Check if screen session exists OR if PID exists
    if get_server_pid(instance_name) is not None:
        return True
        
    try:
        # grep for the screen name (redundant if get_server_pid checks screen, but good for safety)
        result = subprocess.run(["screen", "-list"], capture_output=True, text=True)
        return get_screen_name(instance_name) in result.stdout
    except FileNotFoundError:
        return False

def is_port_in_use(port):
    """
    Check if a TCP port is already in use by any process.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', int(port))) == 0

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
            # Get list of plugins for completion
            plugins_dir = os.path.join(get_instance_dir(), "plugins")
            plugins_list = []
            if os.path.exists(plugins_dir):
                plugins_list = [f for f in os.listdir(plugins_dir) if f.endswith(".jar")]
            
            target_file = input_with_completion("Enter Plugin Filename to remove (Tab to complete): ", plugins_list).strip()
            if target_file:
                args = argparse.Namespace(action="remove", target=target_file)
                cmd_plugins(args)
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
                
                # Get status and port
                status = f"{Colors.RED}Stopped{Colors.ENDC}"
                if is_server_running(inst):
                    status = f"{Colors.GREEN}Running{Colors.ENDC}"
                
                i_dir = os.path.join(INSTANCES_DIR, inst)
                props = read_server_properties(i_dir)
                port = props.get("server-port", "25565")
                
                print(f"{prefix}{color}{inst}{Colors.ENDC} ({status}, Port: {port})")
        
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
            # Get instances list
            instances_dir = "instances"
            instances_list = []
            if os.path.exists(instances_dir):
                instances_list = [d for d in os.listdir(instances_dir) if os.path.isdir(os.path.join(instances_dir, d))]
                
            name = input_with_completion("Enter instance name to select (Tab to complete): ", instances_list).strip()
            if name:
                args = argparse.Namespace(action="select", name=name)
                cmd_instance(args)
                input("\nPress Enter to continue...")
        elif choice == 'd':
            # Get instances list
            instances_dir = "instances"
            instances_list = []
            if os.path.exists(instances_dir):
                instances_list = [d for d in os.listdir(instances_dir) if os.path.isdir(os.path.join(instances_dir, d))]
                
            name = input_with_completion("Enter instance name to delete (Tab to complete): ", instances_list).strip()
            if name:
                args = argparse.Namespace(action="delete", name=name)
                cmd_instance(args)
                input("\nPress Enter to continue...")
        elif choice == 'b':
            break
def dashboard_server_control():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== Server Control ===")
        
        running = is_server_running()
        status_color = Colors.GREEN if running else Colors.FAIL
        status_text = "RUNNING" if running else "STOPPED"
        print(f"Status: {status_color}{status_text}{Colors.ENDC}")
        
        print("\nCommands:")
        print("[S]tart (Detached)")
        print("[X] Stop (Graceful)")
        print("[R]estart")
        print("[K]ill (Force)")
        print("[C]onsole")
        print("[L]ogs")
        print("[I]nitialize/Re-install Server")
        print("[B]ack to Main Menu")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 's':
            if not running:
                class Args:
                    ram = None
                    attach = False
                cmd_start(Args())
                input("\nPress Enter to continue...")
            else:
                print_info("Server already running.")
                input("\nPress Enter to continue...")
        elif choice == 'x':
            if running:
                cmd_stop(None)
                input("\nPress Enter to continue...")
            else:
                print_info("Server not running.")
                input("\nPress Enter to continue...")
        elif choice == 'r':
            if running:
                cmd_stop(None)
                time.sleep(2)
            class Args:
                ram = None
                attach = False
            cmd_start(Args())
            input("\nPress Enter to continue...")
        elif choice == 'k':
            if running:
                cmd_kill(None)
                input("\nPress Enter to continue...")
            else:
                print_info("Server not running.")
                input("\nPress Enter to continue...")
        elif choice == 'c':
            cmd_console(None)
        elif choice == 'l':
            cmd_logs(None)
            try:
                input("\nPress Enter to continue...")
            except KeyboardInterrupt:
                pass
        elif choice == 'i':
            # Re-Initialize
            config = load_config()
            current = config.get("current_instance", "default")
            version = config.get("server_version", "unknown")
            stype = config.get("server_type", "unknown")
            
            print_header(f"Re-Initialize Instance: {current}")
            print(f"Target: {stype} {version}")
            print(f"{Colors.WARNING}Warning: This will re-download server.jar and overwrite eula.txt.{Colors.ENDC}")
            
            confirm = input("Are you sure? [y/N]: ").lower()
            if confirm == 'y':
                if install_server_core(current, version, stype):
                    print_success("\nRe-initialization complete.")
                else:
                    print_error("\nRe-initialization failed.")
            else:
                print("Cancelled.")
            input("\nPress Enter to continue...")
        elif choice == 'b':
            break

def dashboard_content_management():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== Content Management ===")
        print("\nCommands:")
        print("[M]ods")
        print("[P]lugins")
        print("[B]ackups")
        print("[R]estore Backup")
        print("[Back] to Main Menu")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'm':
            dashboard_mods_menu()
        elif choice == 'p':
            dashboard_plugins_menu()
        elif choice == 'b':
            cmd_backup(argparse.Namespace())
            input("\nPress Enter to continue...")
        elif choice == 'r':
            cmd_restore(argparse.Namespace(filename=None, file=None))
            input("\nPress Enter to continue...")
        elif choice == 'back':
            break

def dashboard_config_users():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== Configuration & Users ===")
        print("\nCommands:")
        print("[E]dit Server Properties")
        print("[U]sers (Whitelist/Ops/Bans)")
        print("[G]lobal Settings")
        print("[B]ack to Main Menu")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'e':
            args = argparse.Namespace(action="properties", key=None, value=None)
            cmd_config(args)
            input("\nPress Enter to continue...")
        elif choice == 'u':
            dashboard_users_menu()
        elif choice == 'g':
            args = argparse.Namespace(action="list", key=None, value=None)
            cmd_config(args)
            input("\nPress Enter to continue...")
        elif choice == 'b':
            break

def dashboard_instance_manager():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== Instance Manager ===")
        
        config = load_config()
        current = config.get("current_instance", "default")
        print(f"Current Instance: {Colors.BLUE}{current}{Colors.ENDC}")
        
        print("\nCommands:")
        print("[S]witch / List Instances")
        print("[C]reate New Instance")
        print("[M]odpacks (Search/Import)")
        print("[R]AM Settings")
        print("[D]elete Instance")
        print("[B]ack to Main Menu")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 's':
            dashboard_instances_menu() # Reusing existing menu which handles select/delete/list
        elif choice == 'c':
            # Interactive create
            name = input("Enter new instance name: ").strip()
            if name:
                version = input("Enter Minecraft version (default 1.20.4): ").strip()
                types_str = "/".join(SERVER_TYPES)
                stype = input(f"Enter server type ({types_str}, default paper): ").strip().lower()
                
                args = argparse.Namespace(
                    action="create", 
                    name=name, 
                    version=version if version else None, 
                    type=stype if stype else None
                )
                cmd_instance(args)
                input("\nPress Enter to continue...")
        elif choice == 'm':
            print("\nModpack Options:")
            print("1. Search Modrinth")
            print("2. Install from File (.mrpack)")
            sub = input("Select option: ")
            
            if sub == '1':
                query = input("Search query: ").strip()
                if query:
                    args = argparse.Namespace(action="search", target=query)
                    cmd_modpacks(args)
                    
                    slug = input("\nEnter slug to install (or Enter to cancel): ").strip()
                    if slug:
                        args = argparse.Namespace(action="install", target=slug)
                        cmd_modpacks(args)
                        input("\nPress Enter to continue...")
            elif sub == '2':
                path = input("Enter path to .mrpack file: ").strip()
                if path:
                    path = path.strip("'").strip('"')
                    args = argparse.Namespace(action="install", target=path)
                    cmd_modpacks(args)
                    input("\nPress Enter to continue...")
        elif choice == 'r':
            # RAM Settings
            i_cfg = load_instance_config(current)
            print(f"\nCurrent RAM Settings for {current}:")
            print(f"  Min RAM: {i_cfg.get('ram_min', '2G')}")
            print(f"  Max RAM: {i_cfg.get('ram_max', '4G')}")
            
            new_min = input("\nEnter new Min RAM (e.g. 4G) [Enter to keep]: ").strip()
            new_max = input("Enter new Max RAM (e.g. 8G) [Enter to keep]: ").strip()
            
            if new_min or new_max:
                args = argparse.Namespace(
                    action="ram",
                    min_ram=new_min if new_min else None,
                    max_ram=new_max if new_max else None
                )
                cmd_instance(args)
                input("\nUpdated! Press Enter to continue...")
        elif choice == 'd':
             # Reuse existing menu logic or just call cmd_instance
             # dashboard_instances_menu has 'd' option
             dashboard_instances_menu()
        elif choice == 'b':
            break

def dashboard_system_network():
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== System & Network ===")
        print("\nCommands:")
        print("[N]etwork Manager (Ports/UPnP)")
        print("[B]ack to Main Menu")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'n':
            dashboard_network_menu()
        elif choice == 'b':
            break

def dashboard_admin_menu():
    """Admin/Settings menu for managing MineManage itself."""
    while True:
        os.system('cls' if os.name == 'nt' else 'clear')
        print_header("=== Admin / Settings ===")
        
        config = load_config()
        
        # Display current settings
        print("\nCurrent Global Settings:")
        print(f"  Java Path: {config.get('java_path', 'java')}")
        print(f"  Current Instance: {config.get('current_instance', 'default')}")
        print(f"  Login Delay: {config.get('login_delay', 1.0)}s")
        print(f"  Admin Password: {'SET' if config.get('admin_password_hash') else 'NOT SET'}")
        
        print("\nCommands:")
        print("[1] Change Admin Password")
        print("[2] Edit Global Config")
        print("[3] Reset Admin Password (Remove)")
        print("[B]ack to Main Menu")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == '1':
            # Change password
            print_header("Change Admin Password")
            current_pass = getpass.getpass("Enter current password (or press Enter if none set): ")
            
            # Verify current password if one is set
            if config.get('admin_password_hash'):
                if not verify_password(current_pass, config['admin_password_hash']):
                    print_error("Incorrect password!")
                    input("\nPress Enter to continue...")
                    continue
            
            new_pass = getpass.getpass("Enter new password: ")
            confirm_pass = getpass.getpass("Confirm new password: ")
            
            if new_pass != confirm_pass:
                print_error("Passwords do not match!")
            elif len(new_pass) < 4:
                print_error("Password must be at least 4 characters!")
            else:
                config['admin_password_hash'] = hash_password(new_pass)
                save_config(config)
                print_success("Password changed successfully!")
            
            input("\nPress Enter to continue...")
            
        elif choice == '2':
            # Edit global config
            print_header("Edit Global Config")
            print("Available settings:")
            print("  [1] Java Path")
            print("  [2] Login Delay")
            
            setting = input("\nSelect setting to edit (or Enter to cancel): ")
            
            if setting == '1':
                current_path = config.get('java_path', 'java')
                print(f"Current: {current_path}")
                new_path = input("Enter new Java path (or Enter to keep current): ").strip()
                if new_path:
                    config['java_path'] = new_path
                    save_config(config)
                    print_success("Java path updated!")
                    
            elif setting == '2':
                current_delay = config.get('login_delay', 1.0)
                print(f"Current: {current_delay}s")
                new_delay = input("Enter new login delay in seconds (or Enter to keep current): ").strip()
                if new_delay:
                    try:
                        delay_float = float(new_delay)
                        config['login_delay'] = delay_float
                        save_config(config)
                        print_success("Login delay updated!")
                    except ValueError:
                        print_error("Invalid number!")
            
            input("\nPress Enter to continue...")
            
        elif choice == '3':
            # Reset password
            print_header("Reset Admin Password")
            print(f"{Colors.WARNING}WARNING: This will remove password protection from the dashboard!{Colors.ENDC}")
            confirm = input("Are you sure? (yes/no): ").lower()
            
            if confirm == 'yes':
                config['admin_password_hash'] = ""
                save_config(config)
                print_success("Admin password removed!")
            else:
                print_info("Cancelled.")
            
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
        print(f"Instance: {Colors.BLUE}{instance_name}{Colors.ENDC} | {config.get('server_version')} ({config.get('server_type')})")
        
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
        print(f"CPU: {cpu:.1f}% | RAM: {ram:.0f} MB | Players: {players_online}/{players_max}")
        print("-" * 30)
        
        print("\nMain Menu:")
        print("[1] Server Control...")
        print("[2] Content Management...")
        print("[3] Configuration & Users...")
        print("[4] Instance Manager...")
        print("[5] System & Network...")
        print("[6] Admin / Settings...")
        print("[Q]uit")
        
        print("\n(Auto-refreshing stats... Press key to select command)")
        
        import select
        
        i, o, e = select.select( [sys.stdin], [], [], 2 ) # 2 second refresh
        
        if (i):
            choice = sys.stdin.readline().strip().lower()
            
            if choice == '1':
                dashboard_server_control()
            elif choice == '2':
                dashboard_content_management()
            elif choice == '3':
                dashboard_config_users()
            elif choice == '4':
                dashboard_instance_manager()
            elif choice == '5':
                dashboard_system_network()
            elif choice == '6':
                dashboard_admin_menu()
            elif choice == 'q':
                print("Goodbye!")
                break

def cmd_plugins(args):
    plugins_dir = os.path.join(get_instance_dir(), "plugins")
    if not os.path.exists(plugins_dir):
        os.makedirs(plugins_dir, exist_ok=True)

    if args.action == "list":
        print_header("Plugins:")
        plugins = [f for f in os.listdir(plugins_dir) if f.endswith(".jar")]
        if not plugins:
            print_info("No plugins found.")
        else:
            for p in plugins:
                print(f"- {p}")
    
    elif args.action == "search":
        if not args.target:
            print_error("Usage: plugins search <query>")
            return
            
        config = load_config()
        version = config.get("server_version")
        # For plugins, we assume paper/spigot/bukkit compatibility
        loaders = ["paper", "spigot", "bukkit"]
        
        print_info(f"Searching Modrinth for plugin '{args.target}' ({version})...")
        hits = search_modrinth(args.target, version, loaders, project_type="plugin")
        
        if not hits:
            print_error("No compatible plugins found.")
            return
            
        print_header("Search Results:")
        for i, hit in enumerate(hits):
            print(f"[{i+1}] {hit['title']} ({hit['author']}) - {hit['description'][:50]}...")
            print(f"    Slug: {Colors.CYAN}{hit['slug']}{Colors.ENDC}")

    elif args.action == "install":
        if not args.target:
            print_error("Usage: plugins install <url|name>")
            return
            
        target = args.target
        
        # If URL
        if target.startswith("http://") or target.startswith("https://"):
            url = target
            filename = url.split("/")[-1]
            if not filename.endswith(".jar"):
                filename += ".jar"
            dest = os.path.join(plugins_dir, filename)
            print_info(f"Downloading plugin from {url}...")
            try:
                download_file_with_progress(url, dest)
                print_success(f"Installed {filename}")
            except Exception as e:
                print_error(f"Failed to install plugin: {e}")
                if os.path.exists(dest):
                    os.remove(dest)
        else:
            # Search Modrinth
            config = load_config()
            version = config.get("server_version")
            # For plugins, we assume paper/spigot/bukkit compatibility
            loaders = ["paper", "spigot", "bukkit"]
            
            print_info(f"Searching Modrinth for plugin '{target}' ({version})...")
            hits = search_modrinth(target, version, loaders, project_type="plugin")
            
            if not hits:
                print_error("No compatible plugins found.")
                return
                
            print_header("Search Results:")
            for i, hit in enumerate(hits):
                print(f"[{i+1}] {hit['title']} ({hit['author']}) - {hit['description'][:50]}...")
                
            try:
                choice = int(input("\nSelect plugin to install (0 to cancel): "))
                if choice == 0:
                    return
                if 1 <= choice <= len(hits):
                    selected = hits[choice-1]
                    slug = selected['slug']
                    print_info(f"Fetching latest version for {selected['title']}...")
                    url, filename = get_latest_project_file(slug, version, loaders)
                    
                    if url and filename:
                        dest = os.path.join(plugins_dir, filename)
                        print_info(f"Downloading {filename}...")
                        download_file_with_progress(url, dest)
                        print_success(f"Installed {filename}")
                    else:
                        print_error("Could not find a compatible file for download.")
                else:
                    print_error("Invalid selection.")
            except ValueError:
                print_error("Invalid input.")
        
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

def search_modrinth(query, version, loaders, project_type="mod"):
    """Search Modrinth for projects compatible with version and loaders."""
    try:
        base_url = "https://api.modrinth.com/v2/search"
        
        # Facets for filtering
        # Loaders can be a single string or a list of strings
        if isinstance(loaders, str):
            loaders = [loaders]
            
        loader_facet = [f"categories:{l}" for l in loaders]
        
        facets_list = [
            [f"project_type:{project_type}"]
        ]
        
        if version:
            facets_list.append([f"versions:{version}"])
        
        if loader_facet:
            facets_list.append(loader_facet)
            
        facets = json.dumps(facets_list)
        params = {
            "query": query,
            "facets": facets,
            "limit": 5
        }
        query_string = urllib.parse.urlencode(params)
        url = f"{base_url}?{query_string}"
        
        req = urllib.request.Request(url)
        req.add_header("User-Agent", "MineManage/1.0 (launcher)")
        
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("hits", [])
    except Exception as e:
        print_error(f"Modrinth search failed: {e}")
    return []

def get_latest_project_file(slug, version, loaders):
    """Get the latest compatible file URL for a project."""
    try:
        if isinstance(loaders, str):
            loaders = [loaders]
            
        url = f"https://api.modrinth.com/v2/project/{slug}/version"
        params = {
            "loaders": json.dumps(loaders),
            "game_versions": json.dumps([version])
        }
        query_string = urllib.parse.urlencode(params)
        
        full_url = f"{url}?{query_string}"
        req = urllib.request.Request(full_url)
        req.add_header("User-Agent", "MineManage/1.0 (launcher)")
        
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                versions = json.loads(response.read().decode())
                # Versions are returned sorted by date (newest first) by default
                for v in versions:
                    # Double check compatibility
                    if version in v['game_versions']:
                        # Check if any of our loaders are in the version's loaders
                        if any(l in v['loaders'] for l in loaders):
                            files = v.get('files', [])
                            if files:
                                # Prefer primary file
                                primary = next((f for f in files if f.get('primary')), files[0])
                                return primary['url'], primary['filename'], v.get('dependencies', [])
    except Exception as e:
        print_error(f"Failed to get project file: {e}")
    return None, None, []

def install_mod_with_dependencies(slug, version, loader, mods_dir, installed_ids=None):
    """
    Recursively install a mod and its required dependencies.
    
    Args:
        slug (str): The slug or project ID of the mod to install.
        version (str): The Minecraft version.
        loader (str): The mod loader (fabric, forge, etc.).
        mods_dir (str): The directory to install mods into.
        installed_ids (set, optional): Set of already processed project IDs to prevent loops.
    """
    if installed_ids is None:
        installed_ids = set()
        
    # Modrinth API allows using Project ID or Slug interchangeably in most endpoints
    # We use the ID/Slug to track what we've processed to avoid infinite loops
    if slug in installed_ids:
        return
    
    installed_ids.add(slug)
    
    print_info(f"Resolving {slug}...")
    url, filename, dependencies = get_latest_project_file(slug, version, loader)
    
    if not url or not filename:
        print_error(f"Could not find compatible version for {slug}")
        return

    dest = os.path.join(mods_dir, filename)
    if os.path.exists(dest):
        print_info(f"Mod {filename} already exists. Skipping download.")
    else:
        print_info(f"Downloading {filename}...")
        try:
            download_file_with_progress(url, dest)
            print_success(f"Installed {filename}")
        except Exception as e:
            print_error(f"Failed to download {filename}: {e}")
            return

    # Handle dependencies
    if dependencies:
        for dep in dependencies:
            dep_type = dep.get('dependency_type')
            project_id = dep.get('project_id')
            
            if dep_type == "required" and project_id:
                print_info(f"Found required dependency for {slug}: {project_id}")
                install_mod_with_dependencies(project_id, version, loader, mods_dir, installed_ids)

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
                
    elif args.action == "search":
        if not args.target:
            print_error("Usage: mods search <query>")
            return
            
        config = load_config()
        version = config.get("server_version")
        loader = config.get("server_type", "vanilla").lower()
        
        print_info(f"Searching Modrinth for '{args.target}' ({loader} {version})...")
        hits = search_modrinth(args.target, version, loader, project_type="mod")
        
        if not hits:
            print_error("No compatible mods found.")
            return
            
        print_header("Search Results:")
        for i, hit in enumerate(hits):
            print(f"[{i+1}] {hit['title']} ({hit['author']}) - {hit['description'][:50]}...")
            print(f"    Slug: {Colors.CYAN}{hit['slug']}{Colors.ENDC}")

    elif args.action == "install":
        if not args.target:
            print_error("Usage: mods install <url|name>")
            return
            
        target = args.target
        
        # If it looks like a URL, download directly
        if target.startswith("http://") or target.startswith("https://"):
            url = target
            filename = url.split("/")[-1]
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
        else:
            # Search Modrinth
            config = load_config()
            version = config.get("server_version")
            loader = config.get("server_type", "vanilla").lower()
            
            # Map 'paper' to 'bukkit' or 'spigot' if we supported plugins here, 
            # but for mods we assume Fabric/Forge/NeoForge.
            # If loader is 'paper', warn user.
            if loader not in ["fabric", "forge", "neoforge", "quilt"]:
                print_info(f"{Colors.YELLOW}Warning: Your server type is '{loader}'. Mods usually require Fabric, Forge, or NeoForge.{Colors.ENDC}")
                # We'll try searching for 'fabric' compatible mods by default if they insist, or just 'mod' category?
                # Let's default to 'fabric' for search if unknown, or ask user?
                # For now, let's just try to use the loader as is, but if it's paper, maybe search for plugins?
                # The prompt asked for "Mod installation", so let's stick to mods.
                if loader == "paper":
                     print_error("Paper servers use Plugins, not Mods. Use 'plugins install' instead.")
                     return

            print_info(f"Searching Modrinth for '{target}' ({loader} {version})...")
            hits = search_modrinth(target, version, loader, project_type="mod")
            
            if not hits:
                print_error("No compatible mods found.")
                return
                
            print_header("Search Results:")
            for i, hit in enumerate(hits):
                print(f"[{i+1}] {hit['title']} ({hit['author']}) - {hit['description'][:50]}...")
                
            try:
                choice = int(input("\nSelect mod to install (0 to cancel): "))
                if choice == 0:
                    return
                if 1 <= choice <= len(hits):
                    selected = hits[choice-1]
                    slug = selected['slug']
                    print_info(f"Installing {selected['title']} and dependencies...")
                    install_mod_with_dependencies(slug, version, loader, mods_dir)
                    
            except ValueError:
                print_error("Invalid input.")

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
        print("[I]nstall (Search or URL)")
        print("[R]emove (Filename)")
        print("[B]ack to Dashboard")
        
        choice = input("\nEnter command: ").lower()
        
        if choice == 'i':
            url = input("Enter Mod Name or URL: ").strip()
            if url:
                args = argparse.Namespace(action="install", target=url)
                cmd_mods(args)
                input("\nPress Enter to continue...")
        elif choice == 'r':
            # Get list of mods for completion
            mods_list = [f for f in os.listdir(mods_dir) if f.endswith(".jar")]
            if not mods_list:
                print_error("No mods to remove.")
                continue
                
            target_file = input_with_completion("Enter filename to remove (Tab to complete): ", mods_list).strip()
            if target_file:
                args = argparse.Namespace(action="remove", target=target_file)
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
        props = read_server_properties(server_dir)
        port = props.get("server-port", "25565 (Default)")
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
        print_info("Attempting UPnP port mapping via miniupnpc...")
        
        try:
            u = miniupnpc.UPnP()
            u.discoverdelay = 200
            print_info("Discovering UPnP devices...")
            ndevices = u.discover()
            print_info(f"Found {ndevices} devices.")
            
            print_info("Selecting IGD...")
            u.selectigd()
            
            external_ip = u.externalipaddress()
            print_info(f"External IP: {external_ip}")
            
            # Get port
            server_dir = get_instance_dir()
            props = read_server_properties(server_dir)
            port = int(props.get("server-port", "25565"))
            
            # Get local IP
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
            except Exception:
                local_ip = u.lanaddr
            
            print_info(f"Adding port mapping: {external_ip}:{port} -> {local_ip}:{port} (TCP/UDP)")
            
            # addportmapping(external_port, protocol, internal_host, internal_port, description, remote_host)
            res_tcp = u.addportmapping(port, 'TCP', local_ip, port, 'MineManage Server', '')
            res_udp = u.addportmapping(port, 'UDP', local_ip, port, 'MineManage Server', '')
            
            if res_tcp:
                print_success(f"TCP Port {port} mapped successfully!")
            else:
                print_warning(f"TCP Port mapping returned {res_tcp}")

            if res_udp:
                print_success(f"UDP Port {port} mapped successfully!")
            
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
        print("[F]irewall (UFW)")
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
        elif choice == 'f':
            while True:
                os.system('cls' if os.name == 'nt' else 'clear')
                print_header("=== Firewall Manager (UFW) ===")
                
                # Show status
                args = argparse.Namespace(action="firewall", value="status", port=None)
                cmd_network(args)
                
                print("\nCommands:")
                print("[A]llow Current Port")
                print("[D]eny Port")
                print("[E]nable Firewall")
                print("[X]Disable Firewall")
                print("[B]ack")
                
                f_choice = input("\nEnter command: ").lower()
                
                if f_choice == 'a':
                    args = argparse.Namespace(action="firewall", value="allow", port=None)
                    cmd_network(args)
                    input("\nPress Enter to continue...")
                elif f_choice == 'd':
                    p = input("Enter port to deny: ").strip()
                    if p:
                        args = argparse.Namespace(action="firewall", value="deny", port=p)
                        cmd_network(args)
                        input("\nPress Enter to continue...")
                elif f_choice == 'e':
                    args = argparse.Namespace(action="firewall", value="enable", port=None)
                    cmd_network(args)
                    input("\nPress Enter to continue...")
                elif f_choice == 'x':
                    args = argparse.Namespace(action="firewall", value="disable", port=None)
                    cmd_network(args)
                    input("\nPress Enter to continue...")
                elif f_choice == 'b':
                    break
        elif choice == 'b':
            break

def cmd_instance(args):
    config = get_global_config()
    current = config.get("current_instance", "default")
    
    if args.action == "list":
        if not os.path.exists(INSTANCES_DIR):
            print_info("No instances found.")
            return
            
        instances = sorted([d for d in os.listdir(INSTANCES_DIR) if os.path.isdir(os.path.join(INSTANCES_DIR, d))])
        for inst in instances:
            prefix = "* " if inst == current else "  "
            color = Colors.GREEN if inst == current else ""
            
            # Get status and port
            status = f"{Colors.RED}Stopped{Colors.ENDC}"
            if is_server_running(inst):
                status = f"{Colors.GREEN}Running{Colors.ENDC}"
                
            # Get port
            i_dir = os.path.join(INSTANCES_DIR, inst)
            props = read_server_properties(i_dir)
            port = props.get("server-port", "25565")
            
            print(f"{prefix}{color}{inst}{Colors.ENDC} ({status}, Port: {port})")
            
    elif args.action == "create":
        if not args.name:
            print_error("Usage: instance create <name> [--version <ver>] [--type <type>]")
            return
        
        # Validate name
        if not validate_instance_name(args.name):
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
            
        # We now allow switching while running to support concurrency
        # if is_server_running():
        #    print_error("Cannot switch instances while a server is running. Stop it first.")
        #    return
            
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

    elif args.action == "ram":
        # Load config for current instance
        i_cfg = load_instance_config(current)
        
        if not args.min_ram and not args.max_ram:
            # Just display current
            print_info(f"Current RAM settings for '{current}':")
            print(f"  Min RAM: {i_cfg.get('ram_min', '2G')}")
            print(f"  Max RAM: {i_cfg.get('ram_max', '4G')}")
            return
            
        if args.min_ram:
            i_cfg["ram_min"] = args.min_ram
        if args.max_ram:
            i_cfg["ram_max"] = args.max_ram
            
        save_instance_config(i_cfg, current)
        print_success(f"Updated RAM settings for '{current}': Min={i_cfg.get('ram_min')}, Max={i_cfg.get('ram_max')}")

def main():


    parser = argparse.ArgumentParser(description="MineManage - Minecraft Server Manager")
    parser.add_argument("--version", action="version", version=f"MineManage v{__version__}")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Init command
    parser_init = subparsers.add_parser("init", help="Initialize the server")
    parser_init.add_argument("--version", help="Minecraft version (e.g., 1.20.2)")
    parser_init.add_argument("--type", choices=SERVER_TYPES, help="Server type")
    parser_init.add_argument("--force", action="store_true", help="Force download even if jar exists")
    
    # Start command
    parser_start = subparsers.add_parser("start", help="Start the server")
    parser_start.add_argument("--ram", help="RAM allocation (e.g. 4G)")
    parser_start.add_argument("--attach", action="store_true", help="Run in foreground (attached)")
    
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
    parser_restore.add_argument("filename", nargs="?", help="Backup filename to restore")
    parser_restore.add_argument("--file", help="Backup filename to restore (deprecated)")

    # Config command
    parser_config = subparsers.add_parser("config", help="Manage configuration")
    parser_config.add_argument("action", choices=["list", "set", "set-prop", "set-password", "properties"], help="Action to perform")
    parser_config.add_argument("key", nargs="?", help="Config key")
    parser_config.add_argument("value", nargs="?", help="Config value")

    # Users command
    parser_users = subparsers.add_parser("users", help="Manage whitelist and ops")
    parser_users.add_argument("list_type", choices=["whitelist", "ops", "bans"], help="List to modify")
    parser_users.add_argument("action", choices=["add", "remove", "list"], help="Action to perform")
    parser_users.add_argument("username", nargs="?", help="Username")

    # Plugins command
    parser_plugins = subparsers.add_parser("plugins", help="Manage plugins")
    parser_plugins.add_argument("action", choices=["list", "install", "remove", "search"], help="Action to perform")
    parser_plugins.add_argument("target", nargs="?", help="Plugin URL (install) or Filename (remove)")

    # Mods command
    parser_mods = subparsers.add_parser("mods", help="Manage mods")
    parser_mods.add_argument("action", choices=["list", "install", "remove", "search"], help="Action to perform")
    parser_mods.add_argument("target", nargs="?", help="Mod URL (install) or Filename (remove)")

    # Network command
    parser_network = subparsers.add_parser("network", help="Network tools")
    parser_network.add_argument("action", choices=["info", "set-port", "upnp", "firewall"], help="Action to perform")
    parser_network.add_argument("value", nargs="?", help="Value for set-port or firewall sub-action (allow/deny/status)")
    parser_network.add_argument("--port", help="Port for firewall action")

    # Instance command
    parser_instance = subparsers.add_parser("instance", help="Manage server instances")
    parser_instance.add_argument("action", choices=["list", "create", "select", "delete", "ram"], help="Action to perform")
    parser_instance.add_argument("name", nargs="?", help="Instance name")
    parser_instance.add_argument("--version", help="Minecraft version (create only)")
    parser_instance.add_argument("--type", choices=SERVER_TYPES, help="Server type (create only)")
    parser_instance.add_argument("--min-ram", help="Minimum RAM (e.g. 2G) for 'ram' action")
    parser_instance.add_argument("--max-ram", help="Maximum RAM (e.g. 4G) for 'ram' action")

    # Logs command
    parser_logs = subparsers.add_parser("logs", help="View server logs")

    # Modpacks
    parser_modpacks = subparsers.add_parser("modpacks", help="Manage modpacks")
    parser_modpacks.add_argument("action", choices=["search", "install"], help="Action to perform")
    parser_modpacks.add_argument("target", nargs="?", help="Search query, Slug, or .mrpack file")
    parser_modpacks.set_defaults(func=cmd_modpacks)

    # Dashboard command
    parser_dashboard = subparsers.add_parser("dashboard", help="Open TUI dashboard")

    # Migrate command
    parser_migrate = subparsers.add_parser("migrate", help="Migrate legacy server to instances")

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
    elif args.command == "users":
        cmd_users(args)
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
    elif args.command == "modpacks":
        cmd_modpacks(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    elif args.command == "migrate":
        cmd_migrate(args)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
