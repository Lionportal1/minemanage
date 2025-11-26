# ⛏️ MineManage

> **The friendly, all-in-one CLI for managing your local Minecraft servers.**

MineManage makes it incredibly easy to create, manage, and monitor Minecraft servers right from your terminal. Whether you're a seasoned admin or just want to play with friends, MineManage handles the boring stuff so you can focus on the game.

---

## ✨ Features

- **🚀 Instant Setup**: Initialize a Vanilla, Paper, Fabric, or **NeoForge** server in seconds.
- **🖥️ Interactive Dashboard 2.0**: A redesigned TUI with categorized menus (Control, Content, Config, Instances, Network) and **Global Tab Autocompletion**.
- **🔌 Mod & Plugin Manager**: Search and install mods and plugins directly from **Modrinth** via the CLI.
- **📦 Instance Management**: Switch between different server versions and modpacks effortlessly.
- **🛡️ Automated Backups**: Keep your worlds safe with easy backup and restore commands.
- **🌐 Network Tools**: View your IP, manage ports, and even attempt auto-port forwarding (UPnP).
- **🐧 Linux Ready**: Optimized for both macOS and Linux environments.

## 📥 Installation

### Option 1: Quick Install (Recommended)
Get up and running with a single command:

```bash
curl -O https://raw.githubusercontent.com/Lionportal1/minemanage/v1.3/install.sh && sudo bash install.sh
```

### Option 2: GitHub Releases
You can also download the latest release from the [Releases Page](https://github.com/Lionportal1/minemanage/releases).
1. Download `install.sh` from the latest release.
2. Run `sudo bash install.sh`.

*Note: Sudo access is required to install the global `minemanage` command.*

## 🎮 Usage

### The Dashboard (Recommended)

The easiest way to use MineManage is through its interactive dashboard. Just run:

```bash
minemanage dashboard
```

From here, you can start/stop the server, view live logs, manage plugins, and more—all with simple keyboard shortcuts!

### CLI Commands

Prefer the command line? We've got you covered:

- `minemanage init` — Create a new server.
- `minemanage start` — Launch the server in the background.
- `minemanage stop` — Gracefully stop the server.
- `minemanage console` — Jump into the server console.
- `minemanage logs` — Watch the logs stream in real-time.
- `minemanage network info` — Check your connection details.
- `minemanage backup` — Save your world.
- `minemanage migrate` — Migrate legacy server structure to instances.

## 🤝 Contributing

We love contributions! If you have an idea for a new feature or found a bug, please open an issue or submit a pull request. Check out [CONTRIBUTING.md](CONTRIBUTING.md) for more details.

## 📄 License

This project is licensed under the [MIT License](LICENSE). Feel free to use, modify, and distribute it as you wish!
