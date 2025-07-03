import re
import warnings
from typing import Optional, cast, Union, List, Tuple
from time import sleep, time
import numpy as np
import pyvisa
from pyvisa.resources import MessageBasedResource
from pyvisa.errors import VisaIOError, InvalidBinaryFormat
from tqdm.contrib import tenumerate
import logging

MSG = "34980AWrapper>>"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

"""Basic workflow
ROUT:OPEN:ALL
ROUT:SCAN (@1001:1010)
CONF:VOLT:DC: MIN, MIN, (@1001:1010)
TRIG:SOUR TIM
TRIG:TIM 0.1
TRIG:COUN 10
ROUT:SCAN:SIZE?
READ?
"""


class KS34980AError(Exception):
    """Custom exception for KS34980A instrument errors"""
    pass


class KS34980A:
    """Keysight 34980A Multifunction Switch/Measure Unit

    A wrapper class for controlling the Keysight 34980A instrument via SCPI commands.
    Provides methods for voltage DC measurements with trigger control.
    """

    def __init__(self, name: Optional[str] = None, timeout: float = 5000) -> None:
        """Initialize the KS34980A instrument

        Args:
            name: VISA resource name (e.g., 'TCPIP0::192.168.10.201::inst0::INSTR')
            timeout: Communication timeout in milliseconds
        """
        self.device: Optional[MessageBasedResource] = None
        self.list_resources: List[str] = []
        self.res_man: Optional[pyvisa.ResourceManager] = None
        self._is_connected: bool = False
        self._default_timeout: float = timeout

        self.refresh_resources()
        self.connect_device(name)
        if self._is_connected:
            self.write("SYST:BEEP:STAT OFF")

    def __del__(self) -> None:
        """Destructor - properly close the device connection"""
        self.disconnect()

    def __enter__(self):
        """Context manager entry"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        self.disconnect()

    def disconnect(self) -> None:
        """Properly disconnect from the instrument"""
        if self.device is not None:
            try:
                # Reset instrument to default state
                self.write("*RST")
                sleep(0.1)
                # Close the connection
                self.device.close()
                logger.info(f"{MSG} Device disconnected")
            except Exception as e:
                logger.warning(f"{MSG} Error during disconnect: {e}")
            finally:
                self.device = None
                self._is_connected = False

        if self.res_man is not None:
            try:
                self.res_man.close()
            except Exception as e:
                logger.warning(f"{MSG} Error closing ResourceManager: {e}")
            finally:
                self.res_man = None

    def refresh_resources(self) -> None:
        """Refresh the list of available VISA resources"""
        try:
            self.res_man = pyvisa.ResourceManager()
            self.list_resources = list(self.res_man.list_resources())
            logger.info(f"{MSG} Found {len(self.list_resources)} VISA resources")
        except Exception as e:
            logger.error(f"{MSG} Failed to refresh resources: {e}")
            raise KS34980AError(f"Failed to initialize VISA ResourceManager: {e}")

    def connect_device(self, name: Optional[str] = None) -> None:
        """Connect to the specified instrument

        Args:
            name: VISA resource name. If None, will attempt auto-detection
        """
        if self.res_man is None:
            raise KS34980AError("ResourceManager is undefined")

        if name is not None:
            try:
                self.device = cast(MessageBasedResource, self.res_man.open_resource(name))
                self.device.timeout = self._default_timeout
                self.device.write("*RST")
                sleep(0.5)

                # Verify connection
                idn_response = self.query("*IDN?")
                if "34980A" not in idn_response:
                    raise KS34980AError(f"Connected device is not a 34980A: {idn_response}")

                self._is_connected = True
                logger.info(f"{MSG} Connected: {name}, *IDN?: {idn_response.rstrip()}")

            except VisaIOError as e:
                logger.error(f"{MSG} Failed to connect to {name}: {e}")
                raise KS34980AError(f"Failed to connect to {name}: {e}")
        else:
            # TODO: Implement auto-detection
            logger.warning(f"{MSG} Auto-detection not implemented")

    def _check_connection(self) -> None:
        """Check if device is connected, raise exception if not"""
        if not self._is_connected or self.device is None:
            raise KS34980AError("Device is not connected")

    def query(self, command: str, sec_sleep_after: Optional[float] = None, verbose: bool = False) -> str:
        """Send a query command to the instrument

        Args:
            command: SCPI command string
            sec_sleep_after: Optional delay after query
            verbose: Print debug information

        Returns:
            Response string from instrument
        """
        self._check_connection()

        try:
            response = self.device.query(command)
            if sec_sleep_after is not None:
                sleep(sec_sleep_after)
            if verbose:
                logger.info(f"{MSG} SCPI query {command} --> {response.rstrip()}")
            return response
        except VisaIOError as e:
            logger.error(f"{MSG} Query failed for command '{command}': {e}")
            raise KS34980AError(f"Query failed: {e}")

    def write(self, command: str, verbose: bool = False) -> None:
        """Send a write command to the instrument

        Args:
            command: SCPI command string
            verbose: Print debug information
        """
        self._check_connection()

        try:
            self.device.write(command)
            if verbose:
                logger.info(f"{MSG} SCPI write: {command}")
        except VisaIOError as e:
            logger.error(f"{MSG} Write failed for command '{command}': {e}")
            raise KS34980AError(f"Write failed: {e}")

    def check_errors(self) -> List[str]:
        """Check for any instrument errors

        Returns:
            List of error strings
        """
        errors = []
        try:
            while True:
                error_response = self.query("SYST:ERR?")
                if error_response.startswith("+0"):
                    break
                errors.append(error_response.rstrip())
        except Exception as e:
            logger.warning(f"{MSG} Error checking instrument errors: {e}")

        if errors:
            logger.warning(f"{MSG} Instrument errors detected: {errors}")
        return errors

    def configure_volt_dc(
            self,
            volt_range: Union[float, str, None] = None,
            resolution: Union[float, str, None] = None,
            str_channel: Optional[str] = None,
            nplc: Union[float, str, None] = None,
            tup_trig_tim_cnt: Optional[Tuple[float, float]] = None,
            ms_timeout: Union[float, str, None] = None,
            verbose: bool = False
    ) -> Tuple[List[str], List[float], str, float, float]:
        """Configure voltage DC measurement mode

        Args:
            volt_range: Voltage range (0.1~10, "AUTO", "MIN", "MAX", "DEF")
            resolution: Measurement resolution (float, "MIN", "MAX", "DEF")
            str_channel: Channel specification (e.g., "1001", "1001:1010")
            nplc: Number of Power Line Cycles (0.02~200, "MAX", "MIN", "DEF")
            tup_trig_tim_cnt: Tuple of (interval_time[sec], trigger_count)
            ms_timeout: Timeout in milliseconds or "AUTO"
            verbose: Enable verbose output

        Returns:
            Tuple of (configurations, nplc_values, trigger_source, trigger_time, trigger_count)
        """
        self._check_connection()

        try:
            # Reset all channels
            self.write("ROUT:OPEN:ALL")

            # Configure scan channels
            if str_channel is not None:
                self.write(f"ROUT:SCAN (@{str_channel})")

            # Set NPLC
            if nplc is not None:
                ret_nplc = self.nplc(nplc, str_channel)
                list_nplc = [float(x.strip()) for x in ret_nplc.split(',')]
            else:
                ret_nplc = self.nplc(None, str_channel)
                list_nplc = [float(x.strip()) for x in ret_nplc.split(',')]

            # Configure voltage DC measurement
            self.write(f"CONF:VOLT:DC {volt_range},{resolution},(@{str_channel})")

            # Configure trigger
            if tup_trig_tim_cnt is not None:
                self.write("TRIG:SOUR TIM")
                self.write(f"TRIG:TIM {tup_trig_tim_cnt[0]}")
                self.write(f"TRIG:COUN {tup_trig_tim_cnt[1]}")
            else:
                self.write("TRIG:SOUR IMM")

            # Get configuration
            ret_conf = self.query(f"CONF? (@{str_channel})")
            list_conf = [x.strip().replace('"', '') for x in ret_conf.split('","')]

            # Parse configuration
            list_mode, list_range, list_resolution = [], [], []
            for conf in list_conf:
                try:
                    parts = re.split("[, ]", conf)
                    if len(parts) >= 3:
                        list_mode.append(parts[0])
                        list_range.append(float(parts[1]))
                        list_resolution.append(float(parts[2]))
                except (ValueError, IndexError) as e:
                    logger.warning(f"{MSG} Failed to parse configuration: {conf}, error: {e}")

            # Get trigger parameters
            trig_source = self.query("TRIG:SOUR?").rstrip()
            trig_time = float(self.query("TRIG:TIM?"))
            trig_count = float(self.query("TRIG:COUN?"))

            # Set timeout
            if ms_timeout is not None:
                max_nplc = np.max(list_nplc) if list_nplc else 1.0
                max_time = max_nplc / 50.0  # Assuming 50Hz power line

                if ms_timeout == "AUTO":
                    calculated_timeout = 1000 * (trig_time + max_time + 3) * trig_count
                    self.device.timeout = calculated_timeout
                else:
                    self.device.timeout = float(ms_timeout)

            # Verbose output
            if verbose:
                logger.info(f"{MSG} N_channels: {len(list_conf)}, "
                           f"Trigger(src: {trig_source}, time: {trig_time:.3f}s, count: {trig_count:.0f})")
                logger.info(f"{MSG} NPLC: {list_nplc}")
                logger.info(f"{MSG} MODE: {list_mode}")
                logger.info(f"{MSG} RANGE: {list_range}")
                logger.info(f"{MSG} RESOLUTION: {list_resolution}")
                logger.info(f"{MSG} TIMEOUT: {self.device.timeout}")

            # Check for potential timeout issues
            estimated_time = trig_time * trig_count
            if self.device.timeout < estimated_time * 1000:
                warnings.warn(
                    f"Timeout ({self.device.timeout}ms) may be insufficient for "
                    f"estimated measurement time ({estimated_time:.1f}s). "
                    f"Consider setting ms_timeout='AUTO'."
                )

            # Check for instrument errors
            errors = self.check_errors()
            if errors:
                raise KS34980AError(f"Instrument errors during configuration: {errors}")

            return list_conf, list_nplc, trig_source, trig_time, trig_count

        except Exception as e:
            logger.error(f"{MSG} Configuration failed: {e}")
            raise KS34980AError(f"Configuration failed: {e}")

    def nplc(self, value: Union[float, str, None] = None, str_channel: Optional[str] = None) -> str:
        """Set or get NPLC (Number of Power Line Cycles) value

        Args:
            value: NPLC value (float, "MAX", "MIN", "DEF") or None for query only
            str_channel: Channel specification

        Returns:
            Current NPLC value(s) as string
        """
        self._check_connection()

        cmd = "VOLT:DC:NPLC"
        cmd_query = "VOLT:DC:NPLC?"

        if str_channel is not None:
            if value is not None:
                cmd += f" {value},(@{str_channel})"
            else:
                cmd += f" (@{str_channel})"
            cmd_query += f" (@{str_channel})"
        else:
            if value is not None:
                cmd += f" {value}"

        try:
            if value is not None:
                self.write(cmd)

            response = self.query(cmd_query, 0.3)  # NPLC query can be slow
            return response

        except Exception as e:
            logger.error(f"{MSG} NPLC operation failed: {e}")
            raise KS34980AError(f"NPLC operation failed: {e}")

    def measure(self) -> Tuple[List[float], List[float]]:
        """Perform measurement and return mean and standard deviation

        Returns:
            Tuple of (mean_values, std_values) for each channel
        """
        self._check_connection()

        try:
            num_channels = int(self.query("ROUT:SCAN:SIZE?").rstrip())
            num_triggers = int(float(self.query("TRIG:COUN?").rstrip()))

            # Perform measurement
            str_read = self.query("READ?")
            vec_read = np.array(str_read.split(","), dtype=float)

            # Reshape data: triggers x channels, then transpose to channels x triggers
            mat_read = vec_read.reshape((num_triggers, num_channels)).T

            # Calculate statistics for each channel
            list_mean = []
            list_std = []

            for channel_data in mat_read:
                list_mean.append(np.mean(channel_data))
                list_std.append(np.std(channel_data, ddof=1))  # Use sample standard deviation

            return list_mean, list_std

        except Exception as e:
            logger.error(f"{MSG} Measurement failed: {e}")
            raise KS34980AError(f"Measurement failed: {e}")

    def get_raw_data(self) -> List[np.ndarray]:
        """Get raw measurement data for all channels

        Returns:
            List of numpy arrays, one per channel containing all trigger measurements
        """
        self._check_connection()

        try:
            num_channels = int(self.query("ROUT:SCAN:SIZE?").rstrip())
            num_triggers = int(float(self.query("TRIG:COUN?").rstrip()))

            str_read = self.query("READ?")
            vec_read = np.array(str_read.split(","), dtype=float)

            # Reshape and return as list of arrays
            mat_read = vec_read.reshape((num_triggers, num_channels)).T
            return [channel_data.copy() for channel_data in mat_read]

        except Exception as e:
            logger.error(f"{MSG} Raw data acquisition failed: {e}")
            raise KS34980AError(f"Raw data acquisition failed: {e}")


# Test functions (kept for compatibility)
def test_elapsed_time():
    """Test function to measure elapsed time for different configurations"""
    from matplotlib import pyplot as plt

    name_34980a = 'TCPIP0::192.168.10.201::inst0::INSTR'

    with KS34980A(name_34980a) as ks34980a:
        num_counts = np.arange(1, 21)  # Reduced range for faster testing
        num_channels = np.arange(1, 41)
        mat_etime = np.zeros((len(num_counts), len(num_channels)))

        for i, cnt in tenumerate(num_counts):
            for j, chan in tenumerate(num_channels, leave=False):
                start = time()
                try:
                    ks34980a.configure_volt_dc(
                        "AUTO", "DEF", f"1001:{chan + 1000}",
                        nplc=0.02, tup_trig_tim_cnt=(0.01, cnt),
                        ms_timeout="AUTO", verbose=False
                    )
                    mat_etime[i, j] = time() - start
                except Exception as e:
                    logger.error(f"Error at count={cnt}, channel={chan}: {e}")
                    mat_etime[i, j] = np.nan

        # Plot results
        dchan = (num_channels[1] - num_channels[0]) / 2
        dcnt = (num_counts[1] - num_counts[0]) / 2
        extent = (
            num_channels[0] - dchan, num_channels[-1] + dchan,
            num_counts[-1] + dcnt, num_counts[0] - dcnt
        )

        plt.figure(figsize=(10, 6))
        plt.imshow(mat_etime, extent=extent, aspect='auto', origin='lower')
        plt.xlabel("Number of Channels")
        plt.ylabel("Trigger Counts")
        plt.colorbar(label="Elapsed Time [sec]")
        plt.title("Configuration Time vs Channels/Triggers")
        plt.tight_layout()
        plt.show()


def test_all_raw_data():
    """Test function to acquire and visualize raw data"""
    from matplotlib import pyplot as plt

    name_34980a = 'TCPIP0::192.168.10.201::inst0::INSTR'

    with KS34980A(name_34980a) as ks34980a:
        nplc = 1
        time_interval = 0.01

        ks34980a.configure_volt_dc(
            10, "DEF", "1001:1080",
            nplc=nplc, tup_trig_tim_cnt=(time_interval, 20),
            ms_timeout="AUTO", verbose=True
        )

        start = time()
        raw_data = ks34980a.get_raw_data()
        elapsed = time() - start

        logger.info(f"{MSG} Measurement completed in {elapsed:.3f} seconds")

        # Visualize data
        plt.figure(figsize=(12, 8))
        data_matrix = np.stack(raw_data).T * 1000  # Convert to mV

        plt.imshow(data_matrix, aspect='auto', origin='lower')
        plt.xlabel("Channel")
        plt.ylabel("Trigger Count")
        plt.colorbar(label="Response [mV]")
        plt.title(f"Raw Data - NPLC: {nplc}, Interval: {time_interval*1000:.1f}ms")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    name_34980a = 'TCPIP0::192.168.10.201::inst0::INSTR'
    ks34980a = KS34980A(name_34980a)
    ks34980a.configure_volt_dc(
        "AUTO", "DEF", "1001")
    mean_vals, std_vals = ks34980a.measure()
    print(f"Mean: {mean_vals}")
    print(f"Std: {std_vals}")
    # test_elapsed_time()
    # test_all_raw_data()
