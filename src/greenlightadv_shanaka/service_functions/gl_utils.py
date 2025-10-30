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
                logger.info(f"Aggregating data for key '{sub_key} {type(sub_value)}'")
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

