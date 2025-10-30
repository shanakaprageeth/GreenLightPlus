import numpy as np
from collections import OrderedDict
import logging

# Set up logging for debugging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')



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

    for key, value in gl_next['x'].items():
        if key is 't':
            gl_aggregated['x'][key] = np.array([gl_previous['x']['t'][0], value[1]])
        if gl_previous['x'].get(key) is None:
            gl_aggregated['x'][key] = value
            logger.info(f"Key '{key}' not in previous data. Added current data directly.")
            continue
        if isinstance(value, dict):
            gl_aggregated['x'][key] = np.array([gl_previous['x'][key][0], value[1]])
        else:
            last_time = np.max(gl_previous['x'][key], axis=0)[0]
            logging.info(f"gl_previous['x'][{key}][0][0]: {gl_previous['x'][key][0][0]}, gl_previous['x'][{key}][0][1]: {gl_previous['x'][key][0][1]}")
            step_size = gl_previous['x'][key][0][0] - gl_previous['x'][key][1][0] if len(gl_previous['x'][key]) > 1 else 1.0
            # add offset to align time
            offset_value = last_time + step_size
            logging.info(f"Aggregating key '{key}': last_time={last_time}, step_size={step_size}, offset_value={offset_value}")
            value[:, 0] += offset_value
            gl_aggregated['x'][key]= np.concatenate((gl_previous['x'][key], value), axis=0)

    logger.info("Aggregation of gl data successful.")
    return gl_aggregated

