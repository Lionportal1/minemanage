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

### Initialization
Initialize a new server (downloads the jar and accepts EULA):
```bash
python3 manager.py init --version 1.20.4 --type paper
```

### Starting the Server
Start with default settings (2G-4G RAM):
```bash
python3 manager.py start --detach
```

### Dashboard
Open the interactive dashboard:
```bash
python3 manager.py dashboard
```

### Other Commands
- `stop`: Gracefully stop the server.
- `kill`: Force kill the server process (requires admin password).
- `backup`: Create a zip backup of the world.
- `restore`: Restore a previous backup.
- `logs`: Stream the server logs.
- `config`: View or modify configuration.

## Security Note
The `config.json` file containing the admin password hash is **not** version controlled. You will need to set a new password on each new installation:
```bash
python3 manager.py config set-password
```

## Building from Source
To create a standalone executable:
1. Install development dependencies:
   ```bash
   pip install -r requirements-dev.txt
   ```
2. Run the build script:
   ```bash
   ./build.sh
   ```
   The executable will be in `dist/minemanage`.

## Versioning
This project adheres to [Semantic Versioning](https://semver.org/).
Current Version: **1.0.0**

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
