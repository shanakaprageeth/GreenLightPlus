import numpy as np
from collections import OrderedDict
import logging

# Set up logging for debugging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_all_available_gl_parameters(gl_data):
    """
    Retrieve a list of all available variable names in the GreenLight (gl) data structure.
    
    Args:
        gl_data (dict): The GreenLight model dictionary after simulation.
    Returns:
        list: A list of variable names and type available in the gl data.
    """
    variable_names = []
    for main_key, main_value in gl_data.items():
        for sub_key in main_value.keys():
            variable_names.append([sub_key, type(main_value[sub_key])])
    return variable_names

def get_all_float_integer_variables_values(gl_data, float_precision=4):
    """
    Retrieve a list of all variable names in the GreenLight (gl) data structure
    that are of type float or integer.
    
    Args:
        gl_data (dict): The GreenLight model dictionary after simulation.
    Returns:
        list: A list of variable names of type float or integer with last values
    """
    parameter_value_list = []
    for main_key, main_value in gl_data.items():
        if isinstance(main_value, dict):
            for sub_key, sub_value in main_value.items():
                if isinstance(sub_value, dict):
                    # If the variable is nested, extract the last value from each sub-variable
                    last_values = {}
                    for sub_key, sub_value in sub_value.items():
                        last_values[sub_key] = round(sub_value[-1, 1], float_precision)  # Assuming second column is the value
                    parameter_value_list.append([sub_key, last_values])
                    continue
                if isinstance(sub_value, np.ndarray):
                    parameter_value_list.append([sub_key, round(sub_value[-1, 1], float_precision)])  # Assuming second column is the value
                else:
                    if isinstance(sub_value, (float, int)):
                        parameter_value_list.append([sub_key, sub_value])
        else:
            if isinstance(sub_value, (float, int)):
                parameter_value_list.append([sub_key, sub_value])
            elif isinstance(sub_value, np.ndarray):
                parameter_value_list.append([sub_key, round(sub_value[-1, 1], float_precision)])  # Assuming second column is the value
            else:
                logger.warning(f"Unexpected main value type for key '{main_key}': {type(main_value)}")
    return parameter_value_list


def get_gl_parameter_last_value(gl_data, parameter_name, float_precision=4):
    """
    Extract the last value of a specified variable from the GreenLight (gl) data structure.
    
    Args:
        gl_data (dict): The GreenLight model dictionary after simulation.
        parameter_name (str): The name of the parameter to extract.
    """
    if parameter_name in ['x', 'd', 'a', 'u', 'p']:
        raise ValueError("parameter_name should be a variable name, not a main key.")
    for main_key, main_value in gl_data.items():
        for sub_key, sub_value in main_value.items():
            if parameter_name == sub_key:
                if isinstance(sub_value, dict):
                    # If the variable is nested, extract the last value from each sub-variable
                    last_values = {}
                    for sub_key, sub_value in sub_value.items():
                        last_values[sub_key] = round(sub_value[-1, 1], float_precision)  # Assuming second column is the value
                    return last_values
                if isinstance(sub_value, np.ndarray):
                    return round(sub_value[-1, 1], float_precision)  # Assuming second column is the value
                else:
                    logger.warning(f"Unexpected data type for variable '{parameter_name}': {type(sub_value)}")
                    return sub_value
    raise KeyError(f"Variable '{parameter_name}' not found in gl data.")

  # Assuming second column is the value

    return find_last_value(gl_data, var_name)

def aggregate_gl_data(gl_previous, gl_next):
    """
    Aggregate two gl structures by adjusting time data in gl_next to match total simulation time.
    Uses the simulation's data structure for aggregation.
    """
    if not gl_previous:
        logger.info("Gl_previous null or empty, returning gl_next.")
        return gl_next
    if 'x' not in gl_previous:
        logger.info("Gl_previous missing 'x' key, returning gl_next.")
        return gl_next
    if 'time' not in gl_previous['x']:
        logger.info("Gl_previous missing 'time' key in 'x', returning gl_next.")
        return gl_next

    gl_aggregated = gl_previous.copy()
    # todo handle 'u ''p' 't'
    for main_key, main_value in gl_next.items():
        if main_key is 't':
            gl_aggregated[main_key] = np.array([gl_previous['t'][0], main_value[1]])
            continue
        if main_key is 'p':
            gl_aggregated[main_key] = main_value
            continue
        for sub_key, sub_value in gl_next[main_key].items():
            if gl_previous[main_key].get(sub_key) is None:
                gl_aggregated[main_key][sub_key] = sub_value
                logger.info(f"Key '{sub_key}' not in previous data. Added current data directly.")
                continue
            else:
                #logger.info(f"Aggregating data for key '{sub_key} {type(sub_value)}'")
                if isinstance(sub_value, dict):
                    logger.info(f"Aggregating nested dictionary for key '{sub_key}'")
                    for internal_key, internal_value in gl_next[main_key][sub_key].items():
                        if gl_previous[main_key][sub_key][internal_key].get(sub_key) is None:
                            gl_aggregated[main_key][sub_key][internal_key] = internal_value
                            logger.info(f"Key '{internal_key}' not in previous data. Added current data directly.")
                            continue
                        else:
                            last_time = np.max(gl_previous[main_key][sub_key][internal_key], axis=0)[0]
                            #logging.info(f"gl_previous[main_key][{sub_key}][{internal_key}][0][0]: {gl_previous[main_key][{sub_key}][{internal_key}][0][0]}, gl_previous[main_key][{sub_key}][{internal_key}][0][1]: {gl_previous[main_key][{sub_key}][{internal_key}][0][1]}")
                            step_size = gl_previous[main_key][sub_key][internal_key][0][0] - gl_previous[main_key][sub_key][internal_key][1][0] if len(gl_previous[main_key][sub_key][internal_key]) > 1 else 1.0
                            # add offset to align time
                            offset_value = last_time + step_size
                            #logging.info(f"Aggregating key '{sub_key}': last_time={last_time}, step_size={step_size}, offset_value={offset_value}")
                            sub_value[:, 0] += offset_value
                            gl_aggregated[main_key][sub_key][internal_key]= np.concatenate((gl_previous[main_key][sub_key][internal_key], internal_value), axis=0)
                else:
                    last_time = np.max(gl_previous[main_key][sub_key], axis=0)[0]
                    #logging.info(f"gl_previous[main_key][{sub_key}][0][0]: {gl_previous[main_key][{sub_key}][0][0]}, gl_previous[main_key][{sub_key}][0][1]: {gl_previous[main_key][{sub_key}][0][1]}")
                    step_size = gl_previous[main_key][sub_key][0][0] - gl_previous[main_key][sub_key][1][0] if len(gl_previous[main_key][sub_key]) > 1 else 1.0
                    # add offset to align time
                    offset_value = last_time + step_size
                    #logging.info(f"Aggregating key '{sub_key}': last_time={last_time}, step_size={step_size}, offset_value={offset_value}")
                    sub_value[:, 0] += offset_value
                    gl_aggregated[main_key][sub_key]= np.concatenate((gl_previous[main_key][sub_key], sub_value), axis=0)

    logger.info("Aggregation of gl data successful.")
    return gl_aggregated

