#!/bin/bash

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== MineManage Installer ===${NC}"

# Check Dependencies
echo -e "\n${YELLOW}Checking dependencies...${NC}"

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: python3 is not installed.${NC}"
    exit 1
else
    echo -e "${GREEN}✓ python3 found${NC}"
fi

if ! command -v java &> /dev/null; then
    echo -e "${YELLOW}Warning: java is not installed. You will need it to run Minecraft servers.${NC}"
else
    echo -e "${GREEN}✓ java found${NC}"
fi

if ! command -v screen &> /dev/null; then
    echo -e "${YELLOW}Warning: screen is not installed. You will need it for background management.${NC}"
else
    echo -e "${GREEN}✓ screen found${NC}"
fi

# Setup
echo -e "\n${YELLOW}Setting up MineManage...${NC}"

# Configuration
# TODO: Replace this with your actual raw file URL (e.g., GitHub raw)
DOWNLOAD_URL="YOUR_REPO_RAW_URL/manager.py"
INSTALL_DIR="/usr/local/share/minemanage"
SCRIPT_PATH="$INSTALL_DIR/manager.py"
LINK_PATH="/usr/local/bin/minemanage"

# Create Install Directory
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "Creating install directory at $INSTALL_DIR..."
    if [ -w "/usr/local/share" ]; then
        mkdir -p "$INSTALL_DIR"
    else
        echo -e "${YELLOW}Sudo access required to create install directory.${NC}"
        sudo mkdir -p "$INSTALL_DIR"
        sudo chown $USER "$INSTALL_DIR"
    fi
fi

# Download manager.py
echo -e "Downloading manager.py..."
if curl -L -o "$SCRIPT_PATH" "$DOWNLOAD_URL"; then
    echo -e "${GREEN}Download complete.${NC}"
else
    echo -e "${RED}Failed to download manager.py. Check your internet connection or the URL.${NC}"
    # Fallback to local if present for testing
    if [ -f "manager.py" ]; then
        echo -e "${YELLOW}Falling back to local manager.py...${NC}"
        cp manager.py "$SCRIPT_PATH"
    else
        exit 1
    fi
fi

# Make executable
chmod +x "$SCRIPT_PATH"
echo -e "Made manager.py executable."

# Create Symlink
echo -e "Creating symlink at $LINK_PATH..."
if [ -w "/usr/local/bin" ]; then
    ln -sf "$SCRIPT_PATH" "$LINK_PATH"
else
    echo -e "${YELLOW}Sudo access required to create symlink.${NC}"
    sudo ln -sf "$SCRIPT_PATH" "$LINK_PATH"
fi

if [ $? -eq 0 ]; then
    echo -e "\n${GREEN}Success! MineManage installed.${NC}"
    echo -e "You can now run '${GREEN}minemanage dashboard${NC}' from anywhere."
else
    echo -e "\n${RED}Failed to create symlink.${NC}"
    exit 1
fi
