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
REPO="Lionportal1/minemanage"
VERSION="v1.3" # Default fallback

# Parse arguments
if [[ "$1" == "--dev" ]]; then
    echo -e "${YELLOW}Dev mode enabled. Installing from main branch...${NC}"
    VERSION="main"
else
    echo -e "Fetching latest release version..."
    # Try to get latest tag from GitHub API
    LATEST_TAG=$(curl -s "https://api.github.com/repos/$REPO/releases/latest" | grep '"tag_name":' | sed -E 's/.*"([^"]+)".*/\1/')
    
    if [ -n "$LATEST_TAG" ]; then
        VERSION="$LATEST_TAG"
        echo -e "${GREEN}Found latest version: $VERSION${NC}"
    else
        echo -e "${YELLOW}Could not fetch latest version. Falling back to $VERSION.${NC}"
    fi
fi

DOWNLOAD_URL="https://raw.githubusercontent.com/$REPO/$VERSION/manager.py"
INSTALL_DIR="$HOME/.minemanage"
SCRIPT_PATH="$INSTALL_DIR/manager.py"
BIN_DIR="$HOME/.local/bin"
WRAPPER_PATH="$BIN_DIR/minemanage"

# Create Install Directory
if [ ! -d "$INSTALL_DIR" ]; then
    echo -e "Creating install directory at $INSTALL_DIR..."
    mkdir -p "$INSTALL_DIR"
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

# Download and install requirements
REQ_URL="https://raw.githubusercontent.com/$REPO/$VERSION/requirements.txt"
REQ_PATH="$INSTALL_DIR/requirements.txt"
echo -e "Downloading requirements.txt..."
if curl -L -o "$REQ_PATH" "$REQ_URL"; then
    echo -e "Installing dependencies..."
    if pip3 install -r "$REQ_PATH"; then
        echo -e "${GREEN}Dependencies installed.${NC}"
    else
        echo -e "${YELLOW}Warning: Failed to install dependencies. You may need to run 'pip3 install -r $REQ_PATH' manually.${NC}"
    fi
fi

# Make executable
chmod +x "$SCRIPT_PATH"
echo -e "Made manager.py executable."

# Create Wrapper Script
echo -e "Creating wrapper script at $WRAPPER_PATH..."
mkdir -p "$BIN_DIR"

cat > "$WRAPPER_PATH" <<EOF
#!/bin/bash
cd "$INSTALL_DIR"
exec python3 manager.py "\$@"
EOF

chmod +x "$WRAPPER_PATH"

# Check PATH
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "\n${YELLOW}Warning: $BIN_DIR is not in your PATH.${NC}"
    
    SHELL_CFG=""
    case "$SHELL" in
        */zsh) SHELL_CFG="$HOME/.zshrc" ;;
        */bash) SHELL_CFG="$HOME/.bashrc" ;;
        *) SHELL_CFG="$HOME/.bashrc" ;; # Default
    esac

    echo -e "Run this command to add it to your path:"
    echo -e "${GREEN}echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> $SHELL_CFG && source $SHELL_CFG${NC}"
fi

echo -e "\n${GREEN}Success! MineManage installed.${NC}"
echo -e "You can now run '${GREEN}minemanage dashboard${NC}' from anywhere (after updating PATH)."
