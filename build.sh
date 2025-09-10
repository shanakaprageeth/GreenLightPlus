#!/bin/bash
set -e
rm -rf dist/
python3 -m venv .venv || true
source .venv/bin/activate
# Uninstall old version if exists
echo "Uninstalling old greenlightadv_shanaka if present..."
pip3 uninstall -y GreenLightPlus || true
pip3 uninstall -y greenlightadv || true

# Build the package
python3 -m pip install --upgrade build
python3 -m pip install -r requirnments.txt
python3 -m build

# Install the new package
echo "Installing new greenlightadv..."
pip3 install dist/greenlightadv*.whl

# Testing
pytest tests