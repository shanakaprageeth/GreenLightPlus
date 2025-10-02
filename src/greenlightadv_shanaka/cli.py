"""
CLI module for GreenLight Plus simulation tool.

This module provides command-line interface for running greenhouse simulations
with configuration file support.
"""
import argparse
import json
import yaml
import sys
import os
import subprocess
from pathlib import Path
from typing import Dict, Any, Optional

from greenlightadv_shanaka import (
    GreenLightModel,
    extract_last_value_from_nested_dict,
    calculate_energy_consumption,
    plot_green_light,
    MQTTSimulationManager,
    convert_epw2csv
)
import logging


def setup_logging(level: str = "INFO") -> None:
    """Set up logging configuration."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from JSON or YAML file.
    
    Args:
        config_path: Path to configuration file
        
    Returns:
        Configuration dictionary
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file format is invalid
    """
    config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    try:
        with open(config_path, 'r') as f:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                config = yaml.safe_load(f)
            elif config_path.suffix.lower() == '.json':
                config = json.load(f)
            else:
                raise ValueError(f"Unsupported config file format: {config_path.suffix}")
        
        return config or {}
    
    except (yaml.YAMLError, json.JSONDecodeError) as e:
        raise ValueError(f"Invalid configuration file format: {e}")


def convert_epw_to_csv(epw_path: str, time_step: int) -> str:
    """
    Convert EPW file to CSV format using convert_epw2csv function and return CSV path.
    Args:
        epw_path: Path to EPW file
        time_step: Simulation time step in minutes
    Returns:
        Path to generated CSV file
    """
    # Use default out_folder as in the function signature
    csv_path = convert_epw2csv(epw_path, time_step)
    return csv_path


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate and normalize configuration.
    
    Args:
        config: Raw configuration dictionary
        
    Returns:
        Validated and normalized configuration
        
    Raises:
        ValueError: If configuration is invalid
    """
    # Default configuration
    default_config = {
        "simulation": {
            "season_length": 10,
            "season_interval": 1/24/4,  # 15 minutes
            "first_day": 91,
            "csv_path": "test_data/JPN_Tokyo.Hyakuri.477150_IWEC.csv"
        },
        "mqtt": {
            "enable": True,
            "broker_host": "localhost",
            "broker_port": 1883,
            "greenhouse_id": "greenhouse_01",
            "real_time_simulation": False
        },
        "model": {
            "is_mature": True,
            "lamp_type": "led"
        },
        "greenhouse": {
            "structure": {
                "psi": 22,
                "aFlr": 4e4,
                "aCov": 4.84e4,
                "hAir": 6.3,
                "hGh": 6.905,
                "aRoof": 0.1169*4e4,
                "hVent": 1.3,
                "cDgh": 0.75,
                "lPipe": 1.25,
                "phiExtCo2": 7.2e4*4e4/1.4e4,
                "pBoil": 300*4e4
            },
            "control": {
                "co2SpDay": 1000,
                "tSpNight": 18.5,
                "tSpDay": 19.5,
                "rhMax": 87,
                "ventHeatPband": 4,
                "ventRhPband": 50,
                "thScrRhPband": 10,
                "lampsOn": 0,
                "lampsOff": 18,
                "lampsOffSun": 400,
                "lampRadSumLimit": 10
            }
        },
        "output": {
            "log_level": "INFO",
            "plot_results": True
        }
    }
    
    # Merge with defaults (deep merge)
    def deep_merge(default: Dict, override: Dict) -> Dict:
        result = default.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    validated_config = deep_merge(default_config, config)
    
    # Validate critical parameters
    sim_config = validated_config["simulation"]
    # Ensure epw_path and csv_path keys exist for all configs
    epw_path = sim_config.get("epw_path", None)
    csv_path = sim_config.get("csv_path", None)
    sim_config["epw_path"] = epw_path
    sim_config["csv_path"] = csv_path

    if sim_config["season_length"] <= 0:
        raise ValueError("season_length must be positive")
    if sim_config["season_interval"] <= 0:
        raise ValueError("season_interval must be positive")
    if not (1 <= sim_config["first_day"] <= 365):
        raise ValueError("first_day must be between 1 and 365")
    
    # Validate file paths
    if epw_path and not Path(epw_path).exists():
        logging.warning(f"Weather file not found: {epw_path}. Will use artificial weather data.")
    if csv_path and not Path(csv_path).exists():
        logging.warning(f"CSV weather file not found: {csv_path}. Will use artificial weather data.")
    
    mqtt_config = validated_config["mqtt"]
    if not (1 <= mqtt_config["broker_port"] <= 65535):
        raise ValueError("MQTT broker_port must be between 1 and 65535")
    
    return validated_config


def run_simulation(config: Dict[str, Any]) -> None:
    """
    Run greenhouse simulation with given configuration.
    
    Args:
        config: Validated configuration dictionary
    """
    # Import heavy dependencies only when simulation is actually needed
    from greenlightadv_shanaka import (
        GreenLightModel,
        extract_last_value_from_nested_dict,
        calculate_energy_consumption,
        plot_green_light,
        MQTTSimulationManager,
    )
    
    sim_config = config["simulation"]
    mqtt_config = config["mqtt"]
    model_config = config["model"]
    greenhouse_config = config["greenhouse"]
    output_config = config["output"]

    setup_logging(output_config["log_level"])
    logger = logging.getLogger(__name__)

    # Calculate time step in seconds
    time_step_seconds = sim_config["season_interval"] * 24 * 3600

    # Convert EPW to CSV if epw_path is provided and exists
    epw_path = sim_config.get("epw_path")
    csv_path = sim_config.get("csv_path")
    weather_path = None
    if epw_path and Path(epw_path).exists():
        # Convert and use new CSV path
        season_interval = sim_config.get("season_interval", 1/24/4)
        time_step_minutes = int(season_interval * 24 * 60)
        new_csv_path = convert_epw2csv(epw_path, time_step_minutes)
        sim_config["csv_path"] = new_csv_path
        weather_path = new_csv_path
        logger.info(f"EPW file converted to CSV: {new_csv_path}")
    elif csv_path and Path(csv_path).exists():
        weather_path = csv_path
    else:
        weather_path = epw_path  # fallback, may be None

    # Create GreenLight model instance
    logger.info("Initializing GreenLight model...")
    model = GreenLightModel(
        first_day=sim_config["first_day"],
        isMature=model_config["is_mature"],
        csv_path=weather_path,
        lampType=model_config["lamp_type"]
    )
    
    # Initialize cumulative variables
    total_yield = 0  # Total yield (kg/m2)
    lampIn = 0  # Lighting energy consumption (MJ/m2)
    boilIn = 0  # Heating energy consumption (MJ/m2)
    
    # Initialize model state and parameters
    init_state = {
        "p": {
            **greenhouse_config["structure"],
            **greenhouse_config["control"]
        }
    }
    
    # Initialize MQTT simulation manager if enabled
    mqtt_manager = None
    if mqtt_config["enable"]:
        try:
            mqtt_manager = MQTTSimulationManager(
                broker_host=mqtt_config["broker_host"],
                broker_port=mqtt_config["broker_port"],
                greenhouse_id=mqtt_config["greenhouse_id"],
                real_time=mqtt_config["real_time_simulation"],
                time_step_seconds=time_step_seconds,
                sync_with_real_time=mqtt_config["real_time_simulation"]
            )
            
            if mqtt_manager.start():
                logger.info(f"MQTT manager started successfully for {mqtt_config['greenhouse_id']}")
                logger.info(f"Publishing to broker: {mqtt_config['broker_host']}:{mqtt_config['broker_port']}")
            else:
                logger.warning("Failed to start MQTT manager, continuing without MQTT")
                mqtt_manager = None
        except Exception as e:
            logger.error(f"Error initializing MQTT manager: {e}")
            mqtt_manager = None
    
    # Run the simulation
    logger.info("Starting simulation...")
    try:
        num_steps = int(sim_config["season_length"] // sim_config["season_interval"])
        logger.info(f"Running {num_steps} simulation steps")
        
        for current_step in range(num_steps):
            # Wait for next step if using real-time simulation
            if mqtt_manager and not mqtt_manager.wait_for_next_step(current_step):
                break
                
            # Run the model and get results
            gl = model.run_model(
                gl_params=init_state,
                season_length=sim_config["season_length"],
                season_interval=sim_config["season_interval"],
                step=current_step
            )
            init_state = gl
            dmc = 0.06  # Dry matter content
            logger.debug(f'Running step {current_step}')
            
            # Publish MQTT data if manager is available
            if mqtt_manager:
                success = mqtt_manager.publish_simulation_data(gl, current_step)
                if success:
                    logger.debug(f"Published MQTT data for step {current_step}")
                else:
                    logger.warning(f"Failed to publish MQTT data for step {current_step}")
                
                # Get physical system data if available
                physical_data = mqtt_manager.get_physical_system_data()
                if physical_data:
                    logger.debug(f"Received physical data: {len(physical_data)} topics")
                    # TODO: Integrate physical data into simulation model
            
            # Calculate and accumulate results
            current_yield = 1e-6 * calculate_energy_consumption(gl, 'mcFruitHar') / dmc
            logger.debug(f"Current yield: {current_yield:.2f} kg/m2")
            
            total_yield += current_yield
            lampIn += 1e-6 * calculate_energy_consumption(gl, "qLampIn", "qIntLampIn")
            boilIn += 1e-6 * calculate_energy_consumption(gl, "hBoilPipe", "hBoilGroPipe")
    
    finally:
        # Clean up MQTT manager
        if mqtt_manager:
            logger.info("Stopping MQTT manager...")
            mqtt_manager.stop()
            logger.info("MQTT manager stopped")
    
    # Print final results
    logger.info("Simulation completed!")
    logger.info(f"Total yield: {total_yield:.2f} kg/m2")
    logger.info(f"Lighting energy consumption: {lampIn:.2f} MJ/m2")
    logger.info(f"Heating energy consumption: {boilIn:.2f} MJ/m2")
    if total_yield > 0:
        logger.info(f"Energy consumption per unit: {(lampIn + boilIn)/total_yield:.2f} MJ/kg")
    
    # Plot results if requested
    if output_config["plot_results"]:
        try:
            plot_green_light(gl)
            logger.info("Results plotted successfully")
        except Exception as e:
            logger.error(f"Error plotting results: {e}")


def create_sample_config(output_path: str) -> None:
    """
    Create a sample configuration file.
    
    Args:
        output_path: Path where to save the sample config
    """
    sample_config = {
        "simulation": {
            "season_length": 10,
            "season_interval": 0.010417,  # 15 minutes as fraction of day
            "first_day": 91,
            "cav_path": "test_data/JPN_Tokyo.Hyakuri.477150_IWEC.csv"
        },
        "mqtt": {
            "enable": True,
            "broker_host": "localhost",
            "broker_port": 1883,
            "greenhouse_id": "greenhouse_01",
            "real_time_simulation": False
        },
        "model": {
            "is_mature": True,
            "lamp_type": "led"
        },
        "greenhouse": {
            "structure": {
                "psi": 22,
                "aFlr": 40000,
                "aCov": 48400,
                "hAir": 6.3,
                "hGh": 6.905,
                "aRoof": 4676,
                "hVent": 1.3,
                "cDgh": 0.75,
                "lPipe": 1.25,
                "phiExtCo2": 206857.0,
                "pBoil": 12000000
            },
            "control": {
                "co2SpDay": 1000,
                "tSpNight": 18.5,
                "tSpDay": 19.5,
                "rhMax": 87,
                "ventHeatPband": 4,
                "ventRhPband": 50,
                "thScrRhPband": 10,
                "lampsOn": 0,
                "lampsOff": 18,
                "lampsOffSun": 400,
                "lampRadSumLimit": 10
            }
        },
        "output": {
            "log_level": "INFO",
            "plot_results": True
        }
    }
    
    output_path = Path(output_path)
    with open(output_path, 'w') as f:
        if output_path.suffix.lower() in ['.yaml', '.yml']:
            yaml.dump(sample_config, f, default_flow_style=False, indent=2)
        else:
            json.dump(sample_config, f, indent=2)
    
    print(f"Sample configuration created: {output_path}")


def find_encoding_error_line(filepath):
    """
    Find the line in a file that causes a UnicodeDecodeError.
    Prints the line number and content that fails decoding.
    """
    with open(filepath, "rb") as f:
        for i, line in enumerate(f, 1):
            try:
                line.decode("utf-8")
            except UnicodeDecodeError as e:
                print(f"Encoding error at line {i}: {e}")
                print(f"Raw bytes: {line}")
                return i
    print("No encoding errors found.")
    return None

def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        description="GreenLight Plus - Greenhouse Simulation Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  greenlight-sim config.json              # Run simulation with JSON config
  greenlight-sim config.yaml              # Run simulation with YAML config
  greenlight-sim --create-config sample.json  # Create sample config file
        """
    )
    
    parser.add_argument(
        'config',
        nargs='?',
        help='Path to configuration file (JSON or YAML)'
    )
    
    parser.add_argument(
        '--create-config',
        metavar='PATH',
        help='Create a sample configuration file at the specified path'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version='GreenLight Plus 2.5'
    )
    
    args = parser.parse_args()
    
    try:
        if args.create_config:
            create_sample_config(args.create_config)
            return
        
        if not args.config:
            parser.error("Configuration file is required unless using --create-config")
        
        # Load and validate configuration
        config = load_config(args.config)
        validated_config = validate_config(config)
        
        # Run simulation
        run_simulation(validated_config)
    
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nSimulation interrupted by user", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()