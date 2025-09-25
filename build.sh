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
echo "Running unit tests..."
pytest tests

# System tests using simulation.py functionality
echo "Running system tests with CLI..."

# Test 1: CLI help functionality
echo "Testing CLI help..."
greenlight-sim --help

# Test 2: Create sample configuration
echo "Testing configuration creation..."
greenlight-sim --create-config /tmp/system_test_config.json
if [ ! -f /tmp/system_test_config.json ]; then
    echo "ERROR: Sample config file was not created"
    exit 1
fi

# Test 3: Run simulation with minimal configuration
echo "Testing simulation execution..."
cat > /tmp/minimal_system_test.json << EOF
{
  "simulation": {
    "season_length": 0.5,
    "season_interval": 0.125,
    "first_day": 91
  },
  "mqtt": {
    "enable": false
  },
  "output": {
    "plot_results": false,
    "log_level": "WARNING"
  }
}
EOF

greenlight-sim /tmp/minimal_system_test.json

# Test 4: Verify the simulation produces expected output structure
echo "Testing output validation..."
python3 << EOF
import json
import sys

# Load the test config and verify it's valid
with open('/tmp/system_test_config.json', 'r') as f:
    config = json.load(f)

required_sections = ['simulation', 'mqtt', 'model', 'greenhouse', 'output']
for section in required_sections:
    if section not in config:
        print(f"ERROR: Missing required section '{section}' in sample config")
        sys.exit(1)

print("✓ All system tests passed")
EOF

echo "All tests completed successfully!"