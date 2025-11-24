# MineManage

A lightweight, Python-based CLI tool for managing local Minecraft servers.

## Features
- **Easy Initialization**: Automatically downloads Vanilla or PaperMC server jars.
- **Lifecycle Management**: Start, stop, and restart servers with ease.
- **Background Execution**: Runs servers in detached `screen` sessions.
- **Backups**: Create and restore world backups.
- **Configuration**: Simple CLI for managing server properties and RAM allocation.
- **TUI Dashboard**: Interactive dashboard for monitoring and control.

## Prerequisites
- **Python 3.6+**
- **Java** (JRE/JDK 17+ recommended for modern Minecraft versions)
- **Screen** (`sudo apt install screen` on Linux, usually pre-installed on macOS)

## Installation
1. Clone this repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/MineManage.git
   cd MineManage
   ```
2. Make the script executable (optional):
   ```bash
   chmod +x manager.py
   ```

## Usage

### Dashboard (Recommended)
Launch the interactive TUI dashboard:
```bash
minemanage dashboard
```

### CLI Commands
You can also run commands directly:
- `minemanage init` - Initialize a new server.
- `minemanage start` - Start the server.
- `minemanage stop` - Stop the server.
- `minemanage kill` - Force kill the server (requires admin password).
- `minemanage console` - Attach to the server console.
- `minemanage logs` - View live server logs.
- `minemanage network info` - View IP and port information.
- `minemanage instance create <name>` - Create a new server instance.
- `minemanage backup` - Create a zip backup of the world.
- `minemanage restore` - Restore a previous backup.
- `minemanage config` - View or modify configuration.

## Security Note
The `config.json` file containing the admin password hash is **not** version controlled. You will need to set a new password on each new installation:
```bash
python3 manager.py config set-password
```
