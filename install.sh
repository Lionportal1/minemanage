#!/bin/bash

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== MineManage Installer ===${NC}"

# Check for Root
if [ "$EUID" -eq 0 ]; then
    # Check for override flag
    ALLOW_ROOT=false
    for arg in "$@"; do
        if [ "$arg" == "--allow-root" ]; then
            ALLOW_ROOT=true
            break
        fi
    done

    if [ "$ALLOW_ROOT" = true ]; then
        echo -e "${YELLOW}Warning: Running as root. Proceeding due to --allow-root flag.${NC}"
    else
        echo -e "${YELLOW}Warning: You are running this script as root.${NC}"
        echo -e "MineManage is designed to run as a standard user. Running as root may cause permission issues."
        read -p "Are you sure you want to continue? (y/N) " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo -e "${RED}Aborting.${NC}"
            exit 1
        fi
    fi
fi

# Check Dependencies & OS Detection
echo -e "\n${YELLOW}Checking dependencies...${NC}"

DEPENDENCIES="python3 python3-venv python3-pip screen"
MISSING_DEPS=""

# Detect Package Manager
PKG_MANAGER=""
INSTALL_CMD=""

if command -v apt-get &> /dev/null; then
    PKG_MANAGER="apt"
    INSTALL_CMD="sudo apt-get install -y"
    # Check for Java (default-jre)
    if ! command -v java &> /dev/null; then
        MISSING_DEPS="$MISSING_DEPS default-jre"
    fi
elif command -v dnf &> /dev/null; then
    PKG_MANAGER="dnf"
    INSTALL_CMD="sudo dnf install -y"
    if ! command -v java &> /dev/null; then
        MISSING_DEPS="$MISSING_DEPS java-latest-openjdk"
    fi
elif command -v pacman &> /dev/null; then
    PKG_MANAGER="pacman"
    INSTALL_CMD="sudo pacman -S --noconfirm"
    if ! command -v java &> /dev/null; then
        MISSING_DEPS="$MISSING_DEPS jre-openjdk"
    fi
fi

# Check core tools
for dep in $DEPENDENCIES; do
    if ! command -v $dep &> /dev/null; then
         # Special handling for python3-venv which is often a separate package on Debian/Ubuntu
         if [[ "$dep" == "python3-venv" ]]; then
            # Check if venv module is available
            if ! python3 -c "import venv" &> /dev/null; then
                 MISSING_DEPS="$MISSING_DEPS python3-venv"
            fi
         elif [[ "$dep" == "python3-pip" ]]; then
             # Check if pip module is available (sometimes command is pip3)
             if ! python3 -m pip --version &> /dev/null; then
                 MISSING_DEPS="$MISSING_DEPS python3-pip"
             fi
         else
            MISSING_DEPS="$MISSING_DEPS $dep"
         fi
    fi
done

if [ -n "$MISSING_DEPS" ]; then
    echo -e "${YELLOW}Missing dependencies: $MISSING_DEPS${NC}"
    if [ -n "$PKG_MANAGER" ]; then
        read -p "Install missing dependencies with $PKG_MANAGER? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo -e "Running: $INSTALL_CMD $MISSING_DEPS"
            $INSTALL_CMD $MISSING_DEPS
        else
            echo -e "${RED}Aborting. Please install dependencies manually.${NC}"
            exit 1
        fi
    else
        echo -e "${RED}Could not detect package manager. Please install: $MISSING_DEPS${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✓ All dependencies found${NC}"
fi

# Setup
echo -e "\n${YELLOW}Setting up MineManage...${NC}"

# Configuration
REPO="Lionportal1/minemanage"
VERSION="v1.6" # Default fallback

# Parse arguments
if [[ "$1" == "--dev" ]]; then
    echo -e "${YELLOW}Dev mode enabled. Installing from main branch...${NC}"
    VERSION="main"
    # Create dev mode marker
    mkdir -p "$HOME/.minemanage"
    touch "$HOME/.minemanage/.dev_mode"
else
    # Remove dev mode marker if it exists (switching back to stable)
    rm -f "$HOME/.minemanage/.dev_mode"
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

DOWNLOAD_URL="https://raw.githubusercontent.com/$REPO/$VERSION/manager.py?t=$(date +%s)"
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

# Create Virtual Environment
VENV_DIR="$INSTALL_DIR/venv"
echo -e "Setting up Python virtual environment..."
if [ ! -d "$VENV_DIR" ]; then
    if python3 -m venv "$VENV_DIR"; then
        echo -e "${GREEN}Virtual environment created.${NC}"
    else
        echo -e "${RED}Failed to create virtual environment. Please ensure python3-venv is installed correctly.${NC}"
        exit 1
    fi
fi

# Check if pip exists in venv (or pip3)
if [ ! -f "$VENV_DIR/bin/pip" ] && [ ! -f "$VENV_DIR/bin/pip3" ]; then
    echo -e "${YELLOW}pip not found in venv. Attempting to install ensurepip...${NC}"
    if "$VENV_DIR/bin/python3" -m ensurepip; then
         echo -e "${GREEN}pip installed via ensurepip.${NC}"
    else
         echo -e "${RED}Failed to install pip in venv. Please install python3-pip on your system.${NC}"
         exit 1
    fi
fi

# Download and install requirements
REQ_URL="https://raw.githubusercontent.com/$REPO/$VERSION/requirements.txt"
REQ_PATH="$INSTALL_DIR/requirements.txt"
echo -e "Downloading requirements.txt..."
if curl -L -o "$REQ_PATH" "$REQ_URL"; then
    echo -e "Installing dependencies into venv..."
    # Install into venv using python -m pip (safer than calling pip directly)
    if "$VENV_DIR/bin/python3" -m pip install -r "$REQ_PATH"; then
        echo -e "${GREEN}Dependencies installed.${NC}"
    else
        echo -e "${RED}Failed to install dependencies.${NC}"
        exit 1
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
exec "$VENV_DIR/bin/python3" manager.py "\$@"
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
