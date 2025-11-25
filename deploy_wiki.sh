#!/bin/bash

# Configuration
WIKI_DIR="wiki"
WIKI_REPO_DIR=".wiki_temp"
GITHUB_USER="Lionportal1"
REPO_NAME="minemanage"
WIKI_URL="https://github.com/$GITHUB_USER/$REPO_NAME.wiki.git"

# Check if wiki directory exists
if [ ! -d "$WIKI_DIR" ]; then
    echo "Error: Local wiki directory '$WIKI_DIR' not found."
    exit 1
fi

# Clone or Pull Wiki Repo
if [ -d "$WIKI_REPO_DIR" ]; then
    echo "Updating wiki repository..."
    cd "$WIKI_REPO_DIR"
    git pull
    cd ..
else
    echo "Cloning wiki repository..."
    git clone "$WIKI_URL" "$WIKI_REPO_DIR"
    if [ $? -ne 0 ]; then
        echo "Error: Failed to clone wiki. Have you initialized the Wiki on GitHub yet?"
        exit 1
    fi
fi

# Sync files
echo "Syncing files..."
cp "$WIKI_DIR"/*.md "$WIKI_REPO_DIR/"

# Commit and Push
cd "$WIKI_REPO_DIR"
if [ -n "$(git status --porcelain)" ]; then
    git add .
    git commit -m "Docs: Update wiki content from main repo"
    git push
    echo "Wiki deployed successfully!"
else
    echo "No changes to deploy."
fi

# Cleanup (Optional, keeping it for caching speed)
# rm -rf "$WIKI_REPO_DIR"
