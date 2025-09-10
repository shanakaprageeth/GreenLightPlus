from greenlightadv_shanaka import (
    GreenLightModel,
    extract_last_value_from_nested_dict,
    calculate_energy_consumption,
    plot_green_light,
)

# Set simulation parameters
season_length = 10  # Length of growth cycle (days), can be set as a fraction
season_interval = 1/24/4  # Time interval for each model run (days), can be set as a fraction, e.g., 1/24/4 represents 15 minutes
first_day = 91  # First day of the growth cycle (day of the year)

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

# Run the model based on growth cycle and time interval
print("start simulation")
for current_step in range(int(season_length // season_interval)):
    # Run the model and get results
    gl = model.run_model(gl_params=init_state, season_length=season_length,
                         season_interval=season_interval, step=current_step)
    init_state = gl
    dmc = 0.06  # Dry matter content
    print(f'running step {current_step}')
    print(f'Green house state {gl}')
    # TODO output MQTT states here
    # TODO read MQTT phy states here and update the model greenlightadv_shanaka/create_light_model/
    # Calculate and print current yield (kg/m2)
    current_yield = 1e-6 * calculate_energy_consumption(gl, 'mcFruitHar') / dmc
    print(f"Current yield: {current_yield:.2f} kg/m2")

    # Accumulate fruit yield (kg/m2)
    total_yield += current_yield

    # Calculate and accumulate energy consumption from lighting and heating (MJ/m2)
    lampIn += 1e-6 * calculate_energy_consumption(gl, "qLampIn", "qIntLampIn")
    boilIn += 1e-6 * calculate_energy_consumption(gl, "hBoilPipe", "hBoilGroPipe")

# Print final results
print(f"Total yield: {total_yield:.2f} kg/m2")
print(f"Lighting energy consumption: {lampIn:.2f} MJ/m2")
print(f"Heating energy consumption: {boilIn:.2f} MJ/m2")
print(f"Energy consumption per unit: {(lampIn + boilIn)/total_yield:.2f} MJ/kg")

# Plot model results
plot_green_light(gl)