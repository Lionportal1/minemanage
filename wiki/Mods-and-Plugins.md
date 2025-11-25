# Mods and Plugins

MineManage integrates directly with **Modrinth** to let you search and install content easily.

## Mods

**Note**: Mods require a **Fabric** or **NeoForge** server type.

### Search
```bash
minemanage mods search "sodium"
```

### Install
You can install by Slug (ID) or URL.
```bash
minemanage mods install sodium
```

### Remove
```bash
minemanage mods remove sodium
```
(Use Tab for autocompletion!)

## Plugins

**Note**: Plugins require a **Paper** (or Spigot/Bukkit) server type.

### Search
```bash
minemanage plugins search "essentials"
```

### Install
```bash
minemanage plugins install essentialsx
```

### Remove
```bash
minemanage plugins remove essentialsx-2.20.1.jar
```

## Modpacks

You can install entire modpacks from Modrinth or local files.

### Search Modpacks
```bash
minemanage modpacks search "optimized"
```

### Install from Modrinth
```bash
minemanage modpacks install fabulously-optimized
```

### Install from File
```bash
minemanage modpacks install my-custom-pack.mrpack
```

This will create a **new instance** with the modpack's name, install the correct loader, and download all mods.
