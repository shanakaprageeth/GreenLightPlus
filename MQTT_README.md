# MQTT Integration for GreenLightPlus

This document describes the MQTT integration added to GreenLightPlus for real-time greenhouse simulation data exchange.

## Overview

The MQTT integration allows the GreenLight greenhouse simulation to:
- Publish real-time simulation data to MQTT topics
- Subscribe to physical system data for hybrid simulation
- Support configurable time steps and real-time synchronization
- Provide meaningful topic structure and variable names

## Features

### 🔄 Real-time Data Publishing
- Publishes comprehensive greenhouse data every simulation step
- Organized topic hierarchy with meaningful names
- JSON formatted messages with units and metadata

### 📡 Physical System Integration
- Subscribes to physical sensor data
- Supports bidirectional data flow
- Configurable topic patterns for different systems

### ⏱️ Time Synchronization
- Configurable simulation time steps
- Real-time mode for live operation
- Synchronization with system clock

### 🧪 Comprehensive Testing
- Unit tests for all components
- Integration tests with mosquitto broker
- System tests for end-to-end functionality

## MQTT Topic Structure

All topics follow the pattern: `greenlight/{greenhouse_id}/{category}/{variable}`

### Climate Data (`/climate`)
- `air_temperature` - Air temperature (°C)
- `air_humidity` - Relative humidity (%)
- `air_co2` - CO2 concentration (ppm)
- `vapor_pressure` - Vapor pressure (Pa)
- `canopy_temperature` - Canopy temperature (°C)

### Energy Data (`/energy`)
- `heating_power` - Heating system power (W)
- `lighting_power` - Lighting system power (W)
- `pipe_temperature` - Heating pipe temperature (°C)
- `total_energy` - Total energy consumption (MJ)

### Crop Data (`/crop`)
- `leaf_area_index` - Leaf area index (m²/m²)
- `dry_weight` - Dry weight of crop (kg/m²)
- `fresh_weight` - Fresh weight of crop (kg/m²)
- `fruit_harvest` - Harvested fruit weight (kg/m²)

### Soil Data (`/soil`)
- `soil_temp_layer1` to `soil_temp_layer5` - Soil temperatures by layer (°C)

### Environment Data (`/environment`)
- `outdoor_temperature` - Outdoor temperature (°C)
- `outdoor_humidity` - Outdoor humidity (%)
- `wind_speed` - Wind speed (m/s)
- `solar_radiation` - Solar radiation (W/m²)
- `sky_temperature` - Sky temperature (°C)

### Control Data (`/control`)
- `ventilation_rate` - Ventilation rate (m³/s)
- `heating_valve` - Heating valve position (%)
- `lighting_control` - Lighting intensity (%)
- `co2_injection` - CO2 injection rate (mg/s)

### Simulation Metadata (`/simulation`)
- `step_number` - Current step number
- `simulation_time` - Simulation time since start (days)
- `real_time` - Real system timestamp (s)
- `time_step` - Current simulation time step (s)

## Quick Start

### 1. Install Dependencies

```bash
pip install paho-mqtt
```

### 2. Start MQTT Broker

```bash
# Install mosquitto
sudo apt-get install mosquitto mosquitto-clients

# Start broker
mosquitto -c mosquitto.conf
```

### 3. Run Simulation with MQTT

```python
from greenlightadv_shanaka import GreenLightModel, MQTTSimulationManager

# Create simulation model
model = GreenLightModel(
    first_day=91, 
    isMature=True, 
    epw_path="test_data/JPN_Tokyo.Hyakuri.477150_IWEC.epw"
)

# Create MQTT manager
mqtt_manager = MQTTSimulationManager(
    broker_host="localhost",
    broker_port=1883,
    greenhouse_id="greenhouse_01",
    real_time=False,
    time_step_seconds=900  # 15 minutes
)

# Start MQTT manager
mqtt_manager.start()

# Run simulation with MQTT output
for step in range(100):
    gl = model.run_model(...)
    mqtt_manager.publish_simulation_data(gl, step)
    mqtt_manager.wait_for_next_step(step)

# Clean up
mqtt_manager.stop()
```

### 4. Monitor MQTT Data

```bash
# Subscribe to all greenhouse data
mosquitto_sub -h localhost -t "greenlight/greenhouse_01/+"

# Subscribe to specific category
mosquitto_sub -h localhost -t "greenlight/greenhouse_01/climate"

# Use the provided monitor script
python mqtt_monitor.py greenhouse_01
```

## Configuration

### MQTT Settings

```python
# Basic configuration
mqtt_manager = MQTTSimulationManager(
    broker_host="localhost",      # MQTT broker host
    broker_port=1883,            # MQTT broker port
    greenhouse_id="gh_01",       # Unique greenhouse identifier
    username=None,               # Optional authentication
    password=None,               # Optional authentication
    real_time=True,              # Enable real-time mode
    time_step_seconds=900,       # Time step (15 minutes)
    sync_with_real_time=True     # Sync with system clock
)
```

### Simulation Parameters

```python
# In simulation.py
enable_mqtt = True               # Enable/disable MQTT
mqtt_broker_host = "localhost"   # Broker hostname
mqtt_broker_port = 1883         # Broker port
greenhouse_id = "greenhouse_01"  # Unique ID
real_time_simulation = False     # Real-time mode
```

## Physical System Integration

### Subscribing to Physical Data

The system automatically subscribes to physical system topics:
- `physical/{greenhouse_id}/sensors/+`
- `physical/{greenhouse_id}/actuators/+`
- `physical/{greenhouse_id}/environment/+`
- `physical/{greenhouse_id}/control/+`

### Publishing Physical Data

Physical systems can publish data to these topics:

```bash
# Temperature sensor
mosquitto_pub -h localhost -t "physical/greenhouse_01/sensors/temperature" \
  -m '{"value": 22.5, "unit": "°C", "timestamp": 1640995200}'

# Actuator status
mosquitto_pub -h localhost -t "physical/greenhouse_01/actuators/heating_valve" \
  -m '{"position": 75, "unit": "%", "timestamp": 1640995200}'
```

## Testing

### Run Unit Tests

```bash
python -m pytest tests/mqtt/test_topic_manager.py -v
```

### Run Integration Tests

```bash
# Requires mosquitto broker running
python -m pytest tests/mqtt/test_mqtt_integration.py -v
```

### Run System Tests

```bash
python -m pytest tests/mqtt/test_mqtt_system.py -v
```

## Message Format

All MQTT messages are JSON formatted with the following structure:

```json
{
  "air_temperature": 21.5,
  "air_humidity": 65.2,
  "air_co2": 850,
  "vapor_pressure": 1600,
  "canopy_temperature": 20.8,
  "timestamp": 1640995200.123,
  "simulation_elapsed_seconds": 3600,
  "real_time_factor": 1.0,
  "unit_info": {
    "air_temperature": {"unit": "°C", "description": "Air temperature"},
    "air_humidity": {"unit": "%", "description": "Relative humidity"},
    ...
  }
}
```

## Error Handling

The MQTT integration includes robust error handling:
- Automatic reconnection on connection loss
- Graceful degradation if MQTT is unavailable
- Comprehensive logging for debugging
- Statistics tracking for monitoring

## Performance Considerations

- Default QoS level 0 for maximum throughput
- Configurable message retention
- Bulk publishing for efficiency
- Optimized data structures to minimize payload size

## Examples

See the `tests/mqtt/` directory for comprehensive examples of:
- Basic MQTT publishing and subscribing
- Integration with simulation data
- Real-time monitoring
- Physical system simulation

## Troubleshooting

### Connection Issues
1. Verify mosquitto broker is running
2. Check firewall settings
3. Verify broker host/port configuration

### Data Issues
1. Check topic subscriptions with `mosquitto_sub`
2. Verify JSON message format
3. Check simulation data structure

### Performance Issues
1. Monitor message rates
2. Check network latency
3. Consider QoS settings adjustment

## License

This MQTT integration is part of GreenLightPlus and follows the same GPL-3.0 license.