# Installation

MineManage is designed to run on **macOS**, **Linux**, and **Windows (via WSL)**.

## Prerequisites

Before installing, ensure you have the following dependencies:

1.  **Python 3.8+**: Required to run the application.
2.  **Java (JDK)**: Required to run the Minecraft server.
    *   Java 17 for Minecraft 1.18+
    *   Java 21 for Minecraft 1.20.5+
3.  **Screen**: Used to run the server in the background.
    *   macOS: Pre-installed (usually).
    *   Linux: `sudo apt install screen` (Debian/Ubuntu) or equivalent.

## Automatic Installation (Recommended)

Run the following command in your terminal:

```bash
curl -sL https://raw.githubusercontent.com/Lionportal1/minemanage/v1.2/install.sh | bash
```

This will:
1.  Create a `~/.minemanage` directory.
2.  Download the latest version of `manager.py`.
3.  Create a wrapper script in `~/.local/bin`.
4.  Prompt you to add `~/.local/bin` to your PATH if needed.

## Manual Installation

1.  Clone the repository:
    ```bash
    git clone https://github.com/Lionportal1/minemanage.git
    cd minemanage
    ```
2.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
3.  Run the manager directly:
    ```bash
    python3 manager.py dashboard
    ```

## Post-Installation

Verify the installation by running:

```bash
minemanage --help
```

If the command is not found, ensure `~/.local/bin` is in your PATH.
[[Troubleshooting#command-not-found]]
