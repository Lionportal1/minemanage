# MineManage v1.6 Release Notes

## 🚀 Major Features

### 🔄 Concurrent Instance Management
Run multiple Minecraft servers simultaneously!
-   **Instance Isolation**: Each server runs in its own screen session with its own configuration.
-   **Switching**: Easily switch between active instances using `minemanage instance select`.
-   **Status**: View the status and port of all running instances at a glance.

### ⚡ Server Optimization
Built-in performance tuning for your servers.
-   **Aikar's Flags**: Automatically applies Aikar's famous JVM optimization flags to reduce lag and GC spikes.
-   **Toggle**: Enable or disable optimizations via `minemanage config optimize <enable|disable>`.

### 📝 Comprehensive Logging
Never miss a detail with the new logging system.
-   **Log File**: All actions, errors, and events are logged to `~/.minemanage/minemanage.log`.
-   **Debugging**: Easier troubleshooting with detailed execution logs.

### 🌐 Networking Improvements
More robust and reliable network operations.
-   **Robust Downloads**: Switched to the `requests` library for stable file downloads and API interactions.
-   **Port Conflict Detection**: Prevents starting a server if the port is already in use.
-   **Better UPnP**: Improved automatic port forwarding using `miniupnpc`.

## ✨ Enhancements

-   **Modrinth Auto-Dependencies**: Automatically downloads required dependencies when installing mods.
-   **Visual Progress**: New progress bars (`tqdm`) for all downloads and long-running operations.
-   **RAM Management**: Adjust server RAM limits directly from the CLI or Dashboard.
-   **Dev Mode**: Clear visual indication when running a development build.
-   **Firewall Management**: Manage system firewall ports directly from the Network menu.

## 🐛 Bug Fixes

-   Fixed `IndentationError` in NeoForge installation logic.
-   Resolved issues with NeoForge startup on Linux.
-   Fixed `AttributeError` related to color codes.
-   Improved error handling for missing executables (Java, Screen).

## 📦 Upgrading

To upgrade to v1.6, run the installer:
```bash
curl -O https://raw.githubusercontent.com/Lionportal1/minemanage/main/install.sh && bash install.sh
```
