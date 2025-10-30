from greenlightadv_shanaka import (
    GreenLightModel,
    GreenhouseGeometry,
    extract_last_value_from_nested_dict,
    calculate_energy_consumption,
    plot_green_light,
    MQTTSimulationManager,
    parse_gl_to_status_dict,
    add_status_values,
)
from greenlightadv_shanaka.service_functions.gl_utils import aggregate_gl_data, aggregate_status_data
import logging
import matplotlib.pyplot as plt
import json

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Set simulation parameters
season_length =   1   # Length of growth cycle (days), can be set as a fraction
season_interval = 1/24  # Time interval for each model run (days), can be set as a fraction, e.g., 1/24/4 represents 15 minutes
first_day = 91  # First day of the growth cycle (day of the year)

# MQTT Configuration
enable_mqtt = True  # Enable MQTT output
mqtt_broker_host = "localhost"
mqtt_broker_port = 1883
greenhouse_id = "greenhouse_01"
real_time_simulation = False  # Set to True for real-time operation
time_step_seconds = season_interval * 24 * 3600  # Convert days to seconds

roof_types = [
    "triangle",
    "half_circle",
    "flat_arch",
    "gothic_arch",
    "sawtooth",
    "sawtooth_arch",
]

for roof_type in roof_types:
    print(f"Creating greenhouse with {roof_type} roof")
    # Set basic greenhouse parameters
    wall_height = 6.5  # Ridge height {m}
    wall_width = 4     # Width of each roof segment {m}
    wall_length = 1.67 # Greenhouse length {m}
    num_segments = 6   # Number of roof segments
    slope = 22         # Roof slope angle {°}
    number_length = 10 # Number of greenhouses in length direction
    number_width = 10  # Number of greenhouses in width direction
    time_step = 60     # Time step (minutes)

    # Create a GreenhouseGeometry instance
    greenhouse_model = GreenhouseGeometry(
        roof_type=roof_type,
        slope=slope,
        wall_height=wall_height,
        wall_width=wall_width,
        wall_length=wall_length,
        num_segments=num_segments,
        time_step=time_step,
        number_width=number_width,
        number_length=number_length,
        max_indoor_temp=60,
        min_indoor_temp=0,
        max_outdoor_temp=60,
        min_outdoor_temp=0,
        max_delta_temp=1,
        max_wind_speed=30,
        start_month=4,
        start_day=1,
        end_month=4,
        end_day=7,
    )
#greenhouse_model.create_houses()
# Create a GreenLight model instance
# Parameter explanation:
# - first_day: Start date of the simulation (day of the year)
# - isMature: Indicates whether the crop is mature
# - epw_path: Path to the weather data file
model = GreenLightModel(first_day=first_day, isMature=True, epw_path="test_data/JPN_Tokyo.Hyakuri.477150_IWEC.epw")

# Initialize cumulative variables
total_yield = 0  # Total yield (kg/m2)
lampIn = 0  # Lighting energy consumption (MJ/m2)
boilIn = 0  # Heating energy consumption (MJ/m2)

# Initialize aggregated data
aggregated_gl = None
aggregated_status = None

# Initialize model state and parameters
init_state = {
    "p": {
        # Greenhouse structure settings
        'psi': 22,  # Average slope of greenhouse cover (degrees)
        'aFlr': 4e4,  # Floor area (m^2)
        'aCov': 4.84e4,  # Cover area, including side walls (m^2)
        'hAir': 6.3,  # Height of main area (m) (ridge height is 6.5m, screen is 20cm below)
        'hGh': 6.905,  # Average greenhouse height (m)
        'aRoof': 0.1169*4e4,  # Maximum roof ventilation area (m^2)
        'hVent': 1.3,  # Vertical dimension of a single ventilation opening (m)
        'cDgh': 0.75,  # Discharge coefficient for ventilation (dimensionless)
        'lPipe': 1.25,  # Length of pipe-rail heating system (m/m^2)
        'phiExtCo2': 7.2e4*4e4/1.4e4,  # CO2 injection capacity for the entire greenhouse (mg/s)
        'pBoil': 300*4e4,  # Boiler capacity for the entire greenhouse (W)

        # Control settings
        'co2SpDay': 1000,  # CO2 setpoint during light period (ppm)
        'tSpNight': 18.5,  # Temperature setpoint during dark period (°C)
        'tSpDay': 19.5,  # Temperature setpoint during light period (°C)
        'rhMax': 87,  # Maximum relative humidity (%)
        'ventHeatPband': 4,  # P-band for ventilation at high temperature (°C)
        'ventRhPband': 50,  # P-band for ventilation at high relative humidity (% humidity)
        'thScrRhPband': 10,  # P-band for screen opening at high relative humidity (% humidity)
        'lampsOn': 0,  # Time to turn on lights (h)
        'lampsOff': 18,  # Time to turn off lights (h)
        'lampsOffSun': 400,  # Global radiation above which lamps are turned off (W/m^2)
        'lampRadSumLimit': 10  # Predicted daily sum of solar radiation below which lamps are used (MJ/m^2/day)
    }
}

# Initialize MQTT simulation manager if enabled
mqtt_manager = None
if enable_mqtt:
    try:
        mqtt_manager = MQTTSimulationManager(
            broker_host=mqtt_broker_host,
            broker_port=mqtt_broker_port,
            greenhouse_id=greenhouse_id,
            real_time=real_time_simulation,
            time_step_seconds=time_step_seconds,
            sync_with_real_time=real_time_simulation
        )
        
        if mqtt_manager.start():
            print(f"MQTT manager started successfully for {greenhouse_id}")
            print(f"Publishing to broker: {mqtt_broker_host}:{mqtt_broker_port}")
        else:
            print("Failed to start MQTT manager, continuing without MQTT")
            mqtt_manager = None
    except Exception as e:
        print(f"Error initializing MQTT manager: {e}")
        mqtt_manager = None

# Track simulation states for plotting
states_history = []

# Run the model based on growth cycle and time interval
print("start simulation")
try:
    for current_step in range(int(season_length // season_interval)):
        # Wait for next step if using real-time simulation
        if mqtt_manager and not mqtt_manager.wait_for_next_step(current_step):
            break
            
        # Run the model and get results
        gl = model.run_model(gl_params=init_state, season_length=season_length,
                             season_interval=season_interval, step=current_step)
        init_state = gl

        # Track state for plotting
        states_history.append(gl.copy() if hasattr(gl, 'copy') else gl)

        dmc = 0.06  # Dry matter content
        print(f'running step {current_step}')
        
        # Publish MQTT data if manager is available
        if mqtt_manager:
            success = mqtt_manager.publish_simulation_data(gl, current_step)
            if success:
                print(f"Published MQTT data for step {current_step}")
            else:
                print(f"Failed to publish MQTT data for step {current_step}")
            
            # Get physical system data if available
            physical_data = mqtt_manager.get_physical_system_data()
            if physical_data:
                print(f"Received physical data: {len(physical_data)} topics")
                # TODO: Integrate physical data into simulation model
        
        # Calculate and print current yield (kg/m2)
        current_yield = 1e-6 * calculate_energy_consumption(gl, 'mcFruitHar') / dmc
        print(f"Current yield: {current_yield:.2f} kg/m2")

        # Accumulate fruit yield (kg/m2)
        total_yield += current_yield
        #print("================================")
        #print(gl)
        #print("================================")

        # Aggregate gl data
        if aggregated_gl is None:
            aggregated_gl = gl
        else:
            aggregated_gl = aggregate_gl_data(aggregated_gl, gl)

        # Parse gl into a status->variable->time->value mapping (makes extracting time series easy)
        try:
            status = parse_gl_to_status_dict(gl)
            if aggregated_status is None:
                aggregated_status = status
            else:
                aggregated_status = aggregate_status_data(aggregated_status, status)

            # Write status to file
            #with open('gl_status.txt', 'a') as f:
            #    f.write(f"Step: {current_step}\n")
            #    f.write(json.dumps(aggregated_status, indent=2, default=str))
            with open('gl_raw.txt', 'a') as f:
                f.write(f"Step: {current_step}\n")
                f.write(aggregated_gl.__str__())
            
            # Example: create a new series that is co2Air(t) + co2Air(t+1) within 'x' (if available)
            if 'x' in status and 'co2Air' in status['x']:
                try:
                    add_status_values(status, 'x', 'co2Air', 'co2Air', offset_steps=1, new_var_name='co2Air_plus_next')
                except Exception:
                    # ignore combination errors for the example
                    pass
        except Exception:
            # parsing should not break the simulation flow
            pass

        # Calculate and accumulate energy consumption from lighting and heating (MJ/m2)
        lampIn += 1e-6 * calculate_energy_consumption(gl, "qLampIn", "qIntLampIn")
        boilIn += 1e-6 * calculate_energy_consumption(gl, "hBoilPipe", "hBoilGroPipe")

finally:
    # Clean up MQTT manager
    if mqtt_manager:
        print("Stopping MQTT manager...")
        mqtt_manager.stop()
        print("MQTT manager stopped")

# Print final results
print(f"Total yield: {total_yield:.2f} kg/m2")
print(f"Lighting energy consumption: {lampIn:.2f} MJ/m2")
print(f"Heating energy consumption: {boilIn:.2f} MJ/m2")
print(f"Energy consumption per unit: {(lampIn + boilIn)/total_yield:.2f} MJ/kg")

# Plot model results
plot_green_light(gl, filename="sim_plot.png")
