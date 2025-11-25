# Configuration

MineManage uses two levels of configuration: **Global** and **Instance**.

## Global Configuration (`config.json`)

Located in `~/.minemanage/config.json`. Controls settings that apply to the launcher itself.

| Key | Description | Default |
| :--- | :--- | :--- |
| `java_path` | Path to the Java executable. | `java` |
| `current_instance` | The currently active server instance. | `default` |
| `admin_password_hash` | PBKDF2 hash of the admin password (for `kill` command). | `""` |

**CLI Command:**
```bash
minemanage config set java_path /usr/bin/java17
```

## Instance Configuration (`instance.json`)

Located in `~/.minemanage/instances/<name>/instance.json`. Controls settings specific to a server instance.

| Key | Description | Default |
| :--- | :--- | :--- |
| `ram_min` | Minimum RAM allocation (Xms). | `2G` |
| `ram_max` | Maximum RAM allocation (Xmx). | `4G` |
| `server_type` | Loader type (`vanilla`, `paper`, `fabric`, `neoforge`). | `paper` |
| `server_version` | Minecraft version. | `1.20.4` |

**CLI Command:**
To edit instance config, you currently need to edit the file manually or use the `init` command to re-initialize (which updates version/type). RAM settings can be edited in `instance.json`.

## Server Properties (`server.properties`)

Standard Minecraft server settings.

**CLI Command:**
```bash
minemanage config set-prop view-distance 12
```

**Dashboard:**
Use the `[E]dit Properties` menu for an interactive editor.
