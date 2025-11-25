# Release Notes

## v1.2 "The Security & Modpack Update"
*Released: 2025-11-25*

This major update brings robust security improvements, full modpack support, and comprehensive documentation.

### 🔒 Security Enhancements
*   **Strong Password Hashing**: Replaced SHA-256 with **PBKDF2-HMAC-SHA256** for admin passwords.
    *   *Note*: Existing passwords will still work but trigger a warning. We recommend resetting your password via `config set-password`.
*   **Rootless Installation**: The installer now installs to `~/.minemanage` and `~/.local/bin` by default, removing the need for `sudo`.
*   **Security Policy**: Added `SECURITY.md` with vulnerability reporting guidelines.

### 📦 Modpack Support
*   **Import `.mrpack`**: You can now install modpacks directly from `.mrpack` files!
    *   `minemanage modpacks install my-pack.mrpack`
*   **Modrinth Modpacks**: Search and install modpacks directly from Modrinth.
    *   `minemanage modpacks search "optimized"`
    *   `minemanage modpacks install fabulously-optimized`
*   **Automatic Setup**: Installing a modpack automatically creates a new instance, installs the correct loader (Fabric/NeoForge), and downloads all mods.

### 📚 Documentation
*   **GitHub Wiki**: Launched a comprehensive [Wiki](https://github.com/Lionportal1/minemanage/wiki) covering everything from installation to troubleshooting.
*   **Community Standards**: Added Code of Conduct, Issue Templates, and Pull Request Templates.

### 🛠 Fixes & Improvements
*   **Gitignore**: Fixed an issue where `.mrpack` files were accidentally committed.
*   **Wiki Deployment**: Added `deploy_wiki.sh` for easy documentation updates.

---

## v1.1.0 "The Neo-Dashboard Update"
*Released: 2025-11-21*

*   **New Dashboard**: Completely redesigned TUI with categorized submenus (Server Control, Content, Config, etc.).
*   **NeoForge Support**: Added support for NeoForge mod loader.
*   **Tab Autocompletion**: Added smart autocompletion for mods, plugins, and instances.
*   **Plugin Search**: Integrated Modrinth/Hangar search for plugins.
*   **Refined User Manager**: Simplified whitelist and op management.

## v1.0.0 "Initial Release"
*Released: 2025-11-21*

*   Initial public release.
*   Basic server management (start, stop, kill, logs).
*   Instance management.
*   Mod support (Fabric).
*   Backup/Restore system.
