# Release Notes

## v1.3.0 "The Stability & Polish Update"
*Released: 2025-11-25*

This update focuses on hardening the application's security, improving reliability, and polishing the user experience.

### 🛡️ Security & Stability
*   **Full Backups**: The `backup` command now correctly archives the **entire instance directory** (plugins, mods, configs), ensuring no data is left behind.
*   **Reliable Process Detection**: Replaced fragile `pgrep` logic with robust `screen -ls` parsing. MineManage now reliably detects the correct server process even with multiple instances running.
*   **Input Sanitization**: Added strict validation for instance names, filenames, and console commands to prevent injection attacks.
*   **Login Delay**: Added a configurable `login_delay` (default 1s) to mitigate brute-force attacks on the admin password.
*   **Download Integrity**: All downloads now verify checksums (SHA1/SHA512) to ensure file integrity.
*   **Legacy Cleanup**: Removed support for insecure legacy SHA-256 password hashes.

### 🛠 Refinements
*   **Manual Migration**: The `migrate` logic is now a dedicated command (`minemanage migrate`) and no longer runs automatically on every start, improving performance.
*   **Install Script**: The installer now automatically handles dependencies via `requirements.txt`.
*   **Code Quality**: Extensive refactoring, docstrings, and removal of legacy code.

### 📚 Documentation
*   **Wiki Updates**: Updated Installation, Configuration, and Troubleshooting guides.
*   **Dashboard Guide**: Updated to reflect the latest menu layout.

---

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
