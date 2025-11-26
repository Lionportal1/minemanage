# Troubleshooting

Common issues and how to resolve them.

## Command Not Found

**Issue**: `minemanage: command not found`
**Solution**: Your `~/.local/bin` directory is not in your PATH.
Run this command to add it (for Bash/Zsh):
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```
(Replace `.zshrc` with `.bashrc` if you use Bash).

## Server Won't Start

**Issue**: `minemanage start` says "Server started" but it stops immediately.
**Solution**:
1.  Check the logs: `minemanage logs`
2.  Common causes:
    *   **Java Version**: You might need Java 17 or 21. Check `java -version`.
    *   **EULA**: Check `eula.txt` (MineManage should handle this, but verify).
    *   **RAM**: You might have allocated too much RAM (more than available) or too little. Check `instance.json`.

## Permission Denied

**Issue**: `Permission denied` errors.
**Solution**: MineManage is designed to run as your user, NOT root.
*   Do **NOT** run with `sudo`.
*   If you previously ran with sudo, fix permissions:
    ```bash
    sudo chown -R $USER:$USER ~/.minemanage
    ```

## Screen Session Not Found

**Issue**: `Server is not running` even though it is.
**Solution**:
*   MineManage uses `screen` to manage sessions. If you started the server manually with `java -jar`, MineManage won't see it.
*   Kill the manual process and start with `minemanage start`.

## Migration Issues

**Issue**: My old server files are missing after update.
**Solution**:
*   Run `minemanage migrate` to move legacy server files to the new instance structure.
*   Check the `instances/default` directory.

## Getting Help

If you're still stuck, please [open an issue](https://github.com/Lionportal1/minemanage/issues) on GitHub.
Include:
*   Your OS.
*   MineManage version.
*   Logs or error messages.
