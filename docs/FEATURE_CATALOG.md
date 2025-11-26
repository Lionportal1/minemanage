# MineManage Feature Catalog (Internal)

This document serves as a comprehensive reference for all features implemented in MineManage v1.3. It is intended for internal review, testing, and validation purposes.

## 1. Installation & Setup

### Automatic Installation
*   **Script**: `install.sh`
*   **Method**: `curl` command downloads the script, which then:
    1.  Creates `~/.minemanage` directory.
    2.  Downloads `manager.py` and `requirements.txt` from the specified tag (e.g., `v1.3`).
    3.  Installs Python dependencies via `pip3`.
    4.  Creates a wrapper script in `~/.local/bin/minemanage` for global access.
*   **Dependencies**: Python 3, `screen`, `java` (must be in PATH).

### Manual Installation
*   Users can manually clone the repo or download `manager.py`.
*   Requires manual installation of `requirements.txt`.

## 2. Core Server Management

### Lifecycle Control
*   **Start**: `minemanage start`
    *   Launches the server in a detached `screen` session.
    *   Checks for EULA acceptance.
    *   Verifies Java availability.
*   **Stop**: `minemanage stop`
    *   Sends `stop` command to the console.
    *   Waits up to 30 seconds for graceful shutdown.
*   **Restart**: `minemanage restart`
    *   Performs `stop` then `start`.
*   **Kill**: `minemanage kill`
    *   Forcefully terminates the screen session.
    *   **Security**: Requires Admin Password.
*   **Status**: `minemanage status`
    *   Checks if the server process is running using `screen -ls`.

### Interaction
*   **Console**: `minemanage console`
    *   Attaches to the running screen session.
    *   Detach using `Ctrl+A` then `D`.
*   **Logs**: `minemanage logs`
    *   Streams `logs/latest.log` (equivalent to `tail -f`).
    *   Handles `Ctrl+C` gracefully.

## 3. Instance Management

MineManage supports multiple isolated server instances.

*   **List**: `minemanage instance list`
    *   Shows all available instances.
    *   Highlights the currently active instance.
*   **Create**: `minemanage init --name <name>` (or via Dashboard)
    *   Creates a new directory in `instances/<name>`.
*   **Switch**: `minemanage instance switch <name>`
    *   Updates `global_config` to point to the new instance.
*   **Delete**: `minemanage instance delete <name>`
    *   Permanently removes the instance directory.
    *   Requires confirmation.

## 4. Content Management

### Mods (Fabric/NeoForge)
*   **Search**: `minemanage mods search <query>`
    *   Queries Modrinth API.
    *   Filters by current Minecraft version and loader.
*   **Install**: `minemanage mods install <slug|url>`
    *   Downloads the mod jar to `mods/`.
    *   Verifies checksums.
*   **Remove**: `minemanage mods remove <filename>`

### Plugins (Paper/Spigot)
*   **Search**: `minemanage plugins search <query>`
    *   Queries Modrinth/Hangar (via Modrinth API facet).
*   **Install**: `minemanage plugins install <slug>`
    *   Downloads the plugin jar to `plugins/`.
*   **Remove**: `minemanage plugins remove <filename>`

### Modpacks
*   **Search**: `minemanage modpacks search <query>`
*   **Install (API)**: `minemanage modpacks install <slug>`
*   **Install (File)**: `minemanage modpacks install <file.mrpack>`
    *   Parses `.mrpack` (zip).
    *   Downloads all included files.
    *   Sets up overrides (config files).
    *   Automatically creates a new instance.

## 5. Configuration & Users

### Configuration
*   **Global Config**: `minemanage config list`
    *   Stored in `config.json`.
    *   Keys: `java_path`, `current_instance`, `admin_password_hash`, `login_delay`.
*   **Instance Config**: Stored in `instances/<name>/instance.json`.
    *   Keys: `server_version`, `server_type`, `ram_min`, `ram_max`.
*   **Server Properties**: `minemanage config properties`
    *   Interactive TUI editor for `server.properties`.
    *   Supports boolean toggles and text input.

### User Management
*   **Whitelist**: `minemanage users whitelist <add|remove|list> <username>`
*   **Operators**: `minemanage users ops <add|remove|list> <username>`
*   **Bans**: `minemanage users bans <add|remove|list> <username>` (Dashboard only)
*   **UUID Fetching**: Automatically fetches UUIDs from Mojang API for offline editing.

## 6. Network Manager

*   **Info**: `minemanage network info`
    *   Displays Local IP and Public IP.
*   **Set Port**: `minemanage network set-port <port>`
    *   Updates `server-port` in `server.properties`.
*   **UPnP**: `minemanage network upnp`
    *   Attempts to automatically map the server port using UPnP (IGD).

## 7. Backup & Restore

*   **Backup**: `minemanage backup`
    *   Creates a full zip archive of the instance directory.
    *   Excludes `backups/`, `logs/`, and `cache/`.
    *   Temporarily disables auto-save (`save-off`) if server is running.
*   **Restore**: `minemanage restore <filename>`
    *   Restores a backup zip.
    *   **Warning**: Overwrites current world data.

## 8. Dashboard (TUI)

A text-based user interface wrapping all CLI features.
*   **Navigation**: Numbered menus (1-5).
*   **Live Status**: Shows CPU, RAM, and Player Count (if supported).
*   **Crash Prevention**: Handles `KeyboardInterrupt` and input errors gracefully.

## 9. Security Features

*   **Password Hashing**: PBKDF2-HMAC-SHA256 with salt.
*   **Login Delay**: Artificial delay (default 1s) to slow down brute-force attacks.
*   **Input Sanitization**:
    *   `validate_instance_name`: Alphanumeric only.
    *   `validate_filename`: Prevents path traversal.
    *   `send_command`: Strips control characters.
*   **Download Integrity**: Verifies SHA1/SHA512 checksums for downloads.

## 10. Migration

*   **Command**: `minemanage migrate`
*   **Function**: Moves legacy (root-level) server files into a `default` instance structure.
*   **Trigger**: Manual execution only (v1.3+).
