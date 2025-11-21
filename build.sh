#!/bin/bash

# Install dependencies
python3 -m pip install -r requirements-dev.txt

# Clean previous builds
rm -rf build/ dist/ *.spec

# Build standalone executable
# --onefile: Create a single executable file
# --name: Name of the executable
# --clean: Clean PyInstaller cache
python3 -m PyInstaller --onefile --name minemanage --clean manager.py

echo "Build complete! Executable is in dist/minemanage"
