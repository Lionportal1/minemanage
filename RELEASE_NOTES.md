# MineManage v1.4 Release Notes

## 🚀 What's New

### ⚒️ Forge Support
MineManage now fully supports **Forge**! You can now install and run both modern (1.17+) and legacy (1.12.2 and older) Forge servers with ease.
-   **Initialize**: `minemanage init --type forge --version 1.20.1`
-   **Legacy Support**: Automatically detects and handles legacy Forge launch chains (Java 8 recommended for 1.16.5 and below).

### ⌨️ CLI Polish & Experience Improvements
We've listened to your feedback and polished the CLI experience:
-   **Detached Start**: `minemanage start` now runs in the background (detached) by default. No more accidental server shutdowns when closing your terminal! Use `--attach` to run in the foreground.
-   **Search Commands**: You can now search for content directly:
    -   `minemanage mods search <query>`
    -   `minemanage plugins search <query>`
-   **Easier Restores**: Restore backups simply with `minemanage restore mybackup.zip`.
-   **Ban Management**: Manage bans from the CLI with `minemanage users bans <list|add|remove>`.

### 📦 Dynamic Installer
The installation script (`install.sh`) has been upgraded:
-   **Auto-Update**: Automatically fetches the latest stable release.
-   **Dev Mode**: Use `./install.sh --dev` to install the latest bleeding-edge code from the `main` branch.

## 🐛 Bug Fixes
-   Fixed an issue where `cmd_start` logic could be bypassed.
-   Fixed `restore` command ignoring positional arguments.
-   Fixed indentation and syntax errors in manager logic.

## 📝 Upgrading
To upgrade, simply run the installer again:
```bash
curl -O https://raw.githubusercontent.com/Lionportal1/minemanage/v1.4/install.sh && sudo bash install.sh
```
