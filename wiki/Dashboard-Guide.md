# Dashboard Guide

The MineManage Dashboard is a powerful TUI (Text User Interface) that lets you control your server without remembering complex commands.

## Accessing the Dashboard

Run:
```bash
minemanage dashboard
```

## Main Menu Navigation

The dashboard is divided into several sections:

### 1. Server Control
*   **[S]tart**: Starts the server in a detached screen session.
*   **[X] Stop**: Gracefully stops the server.
*   **[K]ill**: Forcefully kills the server process (requires admin password).
*   **[C]onsole**: Attaches to the server console. Press `Ctrl+A` then `D` to detach.
*   **[C]onsole**: Attaches to the server console. Press `Ctrl+A` then `D` to detach.
*   **[L]ogs**: Views the latest server logs (`tail -f`). Press `Ctrl+C` to exit.
*   **[I]nitialize**: Re-install or initialize the server (useful for fixing broken installs).

### 2. Content Management
*   **[M]ods**: Search, install, and remove mods.
*   **[P]lugins**: Search, install, and remove plugins.
*   **[B]ackup**: Create a zip backup of your world.
*   **[R]estore**: Restore a previous backup (WARNING: Overwrites current world).

### 3. Configuration & Users
*   **[E]dit Properties**: Interactive editor for `server.properties`.
*   **[U]sers**: Manage Whitelist and Operators (Ops).
*   **[G]lobal Config**: Edit global settings like Java path.

### 4. Instance Manager
*   **[I]nstances**: Create, switch, delete, or import instances.

### 5. System & Network
*   **[N]etwork**: View IP, set port, or attempt UPnP port mapping.

## Tips
*   **Live Stats**: The top of the dashboard shows CPU usage, RAM usage, and Player Count in real-time.
*   **Colors**: Green indicates success or running status. Red indicates errors or stopped status.
