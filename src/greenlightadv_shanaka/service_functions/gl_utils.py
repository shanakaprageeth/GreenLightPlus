import numpy as np
from collections import OrderedDict
import logging

# Set up logging for debugging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def _as_time_map(arr):
    """
    Convert a 2-column array-like to an OrderedDict of time->value.
    Accepts numpy arrays or list-of-lists where each row is [time, value].
    """
    a = np.asarray(arr)
    if a.ndim == 1 and a.size == 2:
        return OrderedDict([(float(a[0]), float(a[1]))])
    if a.ndim == 2 and a.shape[1] >= 2:
        times = a[:, 0].astype(float)
        vals = a[:, 1]
        return OrderedDict((float(t), float(v)) for t, v in zip(times.tolist(), vals.tolist()))
    # fallback: try flatten
    try:
        flat = a.flatten()
        if flat.size >= 2:
            return OrderedDict([(float(flat[0]), float(flat[1]))])
    except Exception:
        pass
    return OrderedDict()


def parse_gl_to_status_dict(gl):
    """
    Parse a 'gl' (simulation state) into a dict:
      status_key -> variable_name -> { time: value, ... }
    Handles:
      - numpy arrays shaped (N,2) -> treated as time,value pairs
      - Python lists/tuples similar to array
      - nested dicts (one level deep) are preserved under the variable key as nested maps
      - scalar values are returned as {0.0: scalar}
    """
    status = {}
    for s_key, s_val in gl.items():
        # only parse dict-like top-level entries (x, d, p, a, u, t, ...)
        if not isinstance(s_val, dict):
            # if it's a simple array like 't', try to convert into times map
            try:
                status[s_key] = {}
                if hasattr(s_val, "shape") or isinstance(s_val, (list, tuple, np.ndarray)):
                    status[s_key]['__self'] = _as_time_map(s_val)
                else:
                    status[s_key]['__self'] = OrderedDict([(0.0, float(s_val))])
            except Exception:
                status[s_key] = {'__self': OrderedDict()}
            continue

        status[s_key] = {}
        for var_name, var_val in s_val.items():
            # numpy arrays or lists of pairs
            if isinstance(var_val, np.ndarray) or isinstance(var_val, (list, tuple)):
                try:
                    tm = _as_time_map(var_val)
                    if tm:
                        status[s_key][var_name] = tm
                        continue
                except Exception:
                    pass
                # fallback: store scalar-like or list as index->value mapping
                try:
                    arr = np.asarray(var_val)
                    if arr.size == 1:
                        status[s_key][var_name] = OrderedDict([(0.0, float(arr.item()))])
                    else:
                        # store as index->value if can't interpret as (time,value)
                        status[s_key][var_name] = OrderedDict((float(i), float(v)) for i, v in enumerate(arr.tolist()))
                except Exception:
                    status[s_key][var_name] = OrderedDict()
            elif isinstance(var_val, dict):
                # nested dict: recursively convert if possible
                nested = {}
                for nk, nv in var_val.items():
                    if isinstance(nv, (list, tuple, np.ndarray)):
                        nested[nk] = _as_time_map(nv)
                    else:
                        try:
                            nested[nk] = OrderedDict([(0.0, float(nv))])
                        except Exception:
                            nested[nk] = OrderedDict()
                status[s_key][var_name] = nested
            else:
                # scalar
                try:
                    status[s_key][var_name] = OrderedDict([(0.0, float(var_val))])
                except Exception:
                    status[s_key][var_name] = OrderedDict()
    return status


def add_status_values(status_dict, status_key, var1, var2, offset_steps=1, new_var_name=None):
    """
    Create a new variable in status_dict[status_key] by adding var1(t) + var2(t+offset_steps).
    The function aligns entries by index (sorted order). It stores the resulting time->value map
    under new_var_name (or f"{var1}_plus_{var2}_off{offset_steps}" if None) and returns it.
    """
    if status_key not in status_dict:
        raise KeyError(f"status '{status_key}' not found in status_dict")

    s = status_dict[status_key]
    if var1 not in s or var2 not in s:
        raise KeyError(f"variables '{var1}' and/or '{var2}' not found under status '{status_key}'")

    map1 = s[var1]
    map2 = s[var2]

    times1 = list(map1.keys())
    vals1 = list(map1.values())
    times2 = list(map2.keys())
    vals2 = list(map2.values())

    if offset_steps < 0:
        raise ValueError("offset_steps must be >= 0")

    # Determine how many pairs can be formed
    max_pairs = min(len(vals1), max(0, len(vals2) - offset_steps))
    result = OrderedDict()
    for i in range(max_pairs):
        t = times1[i]
        v1 = vals1[i]
        v2 = vals2[i + offset_steps]
        # safe numeric addition
        try:
            result[float(t)] = float(v1) + float(v2)
        except Exception:
            # non-numeric: store as tuple
            result[float(t)] = (v1, v2)

    if new_var_name is None:
        new_var_name = f"{var1}_plus_{var2}_off{offset_steps}"
    status_dict[status_key][new_var_name] = result
    return result


def aggregate_gl_data(gl_previous, gl_next):
    """
    Aggregate two gl structures by adjusting time data in gl_next to match total simulation time.
    Uses the simulation's data structure for aggregation.
    """
    if not gl_previous or 'x' not in gl_previous or 'time' not in gl_previous['x']:
        logger.info("No previous data to aggregate. Using current step data.")
        return gl_next

    gl_aggregated = gl_previous.copy()
    try:
        max_time_previous = np.max(gl_previous['x']['time'], axis=0)[0]  # Last time value in gl_previous
        logger.info(f"Aggregating gl data. Previous max time: {max_time_previous}")
    except Exception as e:
        logger.error(f"Error accessing previous time data: {e}")
        return gl_next

    for key, value in gl_next.items():
        try:
            if isinstance(value, dict):
                gl_aggregated[key] = aggregate_gl_data(gl_previous.get(key, {}), value)
            elif isinstance(value, OrderedDict):
                # Adjust time values in gl_next to start after gl_previous
                adjusted_data = OrderedDict(
                    (t + max_time_previous, v) for t, v in value.items()
                )
                gl_aggregated[key] = OrderedDict(
                    list(gl_previous.get(key, {}).items()) + list(adjusted_data.items())
                )
            else:
                gl_aggregated[key] = value
        except Exception as e:
            logger.error(f"Error aggregating key '{key}': {e}")

    logger.info("Aggregation of gl data successful.")
    return gl_aggregated


def aggregate_status_data(status_previous, status_next):
    """
    Aggregate two status structures by adjusting time data in status_next to match total simulation time.
    Uses the simulation's data structure for aggregation.
    """
    if not status_previous:
        print(status_previous)  # Debugging: print the previous status structure
        logger.info("No previous status data to aggregate. Using current step data.")
        return status_next

    status_aggregated = status_previous.copy()
    try:
        max_time_previous = np.max(status_previous['x']['time'], axis=0)[0]  # Last time value in status_previous
        logger.info(f"Aggregating status data. Previous max time: {max_time_previous}")
    except Exception as e:
        logger.error(f"Error accessing previous time data: {e}")
        return status_next

    for key, value in status_next.items():
        try:
            if isinstance(value, dict):
                status_aggregated[key] = aggregate_status_data(status_previous.get(key, {}), value)
            elif isinstance(value, OrderedDict):
                # Adjust time values in status_next to start after status_previous
                adjusted_data = OrderedDict(
                    (t + max_time_previous, v) for t, v in value.items()
                )
                status_aggregated[key] = OrderedDict(
                    list(status_previous.get(key, {}).items()) + list(adjusted_data.items())
                )
            else:
                status_aggregated[key] = value
        except Exception as e:
            logger.error(f"Error aggregating key '{key}': {e}")

    logger.info("Aggregation of status data successful.")
    return status_aggregated
