# Getting Started

Once installed, you can start managing your Minecraft servers immediately.

## 1. Initialize a Server

To create your first server instance, use the `init` command or the interactive dashboard.

**CLI Method:**
```bash
minemanage init --version 1.20.4 --type paper
# OR
minemanage init --version 1.20.1 --type forge
```

**Dashboard Method:**
1.  Run `minemanage dashboard`.
2.  Select `[C]reate New Instance`.
3.  Follow the prompts to choose a name, version, and loader.

## 2. Start the Server

To start your server:

```bash
minemanage start
```

Or press `[S]tart` in the dashboard.

*   **Note**: The first launch may take a while as it downloads the server jar and generates files.
*   **EULA**: MineManage automatically accepts the EULA for you.

## 3. Access the Console

To view the server console and type commands:

```bash
minemanage console
```

To detach from the console (leave it running in the background), press `Ctrl+A` then `D`.

## 4. Stop the Server

To stop the server gracefully:

```bash
minemanage stop
```

Or press `[X] Stop` in the dashboard.

## Next Steps

*   [[Configuration]]: Customize RAM and server properties.
*   [[Mods and Plugins]]: Add content to your server.
*   [[Dashboard Guide]]: Learn to use the TUI.
