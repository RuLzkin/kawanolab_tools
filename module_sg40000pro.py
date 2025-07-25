from typing import Optional, Tuple, List
from serial import SerialException, Serial
from serial.tools import list_ports
import time
import logging

MSG = "SG40000proWrapper>>"
BADCOMMANDRESPONSE = b"[BADCOMMAND]\r\n"

# Configure logging
# logging.basicConfig(level=logging.DEBUG)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def flush_current_logger():
    # グローバルのloggerを直接使用
    for handler in logger.handlers:
        handler.flush()

    # 親ロガーも
    if logger.propagate:
        for handler in logging.getLogger().handlers:
            handler.flush()


class SG40000pro():
    """Signal Generator SG40000PRO Controller

    A Python interface for controlling the SG40000PRO signal generator via serial communication.
    Provides methods to connect, configure frequency/power, and control output state.
    """

    device: Optional[Serial] = None

    def __init__(self, str_port: Optional[str] = None, hardreset: bool = False) -> None:
        """Initialize SG40000PRO controller

        Args:
            str_port: Serial port name (e.g., 'COM3', '/dev/ttyUSB0').
                     If None, automatically searches for available device.
        """
        if str_port is None:
            str_port = self.find_port()
        self.connect(str_port)

        if hardreset:
            logger.info(f"{MSG} Reset the unit")
            self.write("*RST")
            self.wait(timeout=10.0)
        logger.info(f"{MSG} Turn off buzzers")
        self.write("*BUZZER OFF")

        self.status(True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        """Destructor - ensure serial connection is closed"""
        try:
            self.close()
        except:
            pass  # __del__では例外を発生させない

    def find_port(self) -> str:
        """Automatically find SG40000PRO device port

        Searches through available serial ports and tests connection
        by sending *IDN? command to identify the SG40000PRO device.

        Returns:
            str: Port name where SG40000PRO device is found

        Raises:
            SerialException: If no SG40000PRO device is found on any port
        """
        list_port = list(list_ports.comports())
        for _port in list_port:
            try:
                with Serial(_port.name, 115200, timeout=1) as device:
                    device.write(b"*IDN?\n")
                    time.sleep(0.1)
                    response = device.readline().decode().rstrip()
                    if response.find("SG40000PRO") == -1:
                        raise SerialException
                    logger.info(f"{MSG} Connect -- {_port.name} >> Successfully connected")
                    return _port.name
            except SerialException:
                logger.info(f"{MSG} Connect -- {_port.name} >> Could not be connected")

        raise FileNotFoundError

    def connect(self, str_port: str) -> None:
        """Connect to specified serial port

        Args:
            str_port: Serial port name to connect to

        Communication settings:
            - Baud rate: 115200
            - Timeout: 1 second
        """
        self.device = Serial(str_port, 115200, timeout=10)
        self.wait()

    def wait_for_response(self, timeout: float = 5.0) -> bytes:
        """レスポンスが来るまで待つ"""
        assert self.device is not None
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.device.in_waiting > 0:
                return self.device.readline()
            time.sleep(0.01)
        raise TimeoutError("Timeout")

    def write(self, str_command: str) -> None:
        assert self.device is not None
        self.device.reset_input_buffer()
        self.wait()
        self.device.write(str_command.encode() + b"\n")

    def query(self, str_command: str, timeout: float = 5.0) -> str:
        """Send command and receive response

        Args:
            str_command: SCPI command string to send

        Returns:
            str: Response from device (stripped of whitespace)

        Note:
            Automatically appends newline character to command
        """
        assert self.device is not None
        self.write(str_command)
        try:
            response = self.wait_for_response(timeout)
        except TimeoutError as e:
            logger.error(f"{MSG} Timeout occured (cmd: {str_command})")
            raise e
        return response.decode().rstrip()

    def wait(self, timeout=5.0) -> None:
        assert self.device is not None
        logger.debug(f"{MSG} waiting...")
        while True:
            self.device.write(b"*OPC?\n")
            _response = self.wait_for_response(timeout=timeout)
            if b"+1" in _response:
                break

        self.device.flush()
        self.device.reset_input_buffer()
        logger.debug(f"{MSG} ready.")

    def close(self) -> None:
        """Close serial connection"""
        if self.device is not None:
            try:
                logger.info(f"{MSG} Output turned OFF before closing")
                self.off()
            except Exception as e:
                logger.warning(f"{MSG} Could not turn off output: {e}")
            try:
                logger.info(f"{MSG} Close serial connection")
                self.device.close()
            except Exception as e:
                logger.warning(f"{MSG} Error closing serial connection: {e}")
            finally:
                self.device = None

    def on(self, db_power: float, hz_freq: float) -> None:
        """Turn on signal generator with specified parameters

        Args:
            db_power (float): Output power in dBm
            hz_freq (float): Frequency in Hz

        Raises:
            TypeError: If power or frequency is not a float

        Example:
            sg.on(15.0, 22e9)  # 15 dBm at 22 GHz
        """
        if not isinstance(db_power, float):
            raise TypeError("Power should be a float number")
        if not isinstance(hz_freq, float):
            raise TypeError("Frequency should be a float number")
        self.write("POWER {0:f}".format(db_power))
        self.write("FREQ:CW {0:f}GHZ".format(hz_freq * 1e-9))
        self.write("OUTP:STAT ON")

    def off(self):
        """Turn off signal generator output

        Disables the RF output while maintaining other settings.
        """
        self.write("OUTP:STAT OFF")

    def is_on(self):
        """Check if signal generator output is enabled

        Returns:
            bool: True if output is ON, False if OFF

        Raises:
            ValueError: If unexpected response received from device
        """
        _res = self.query("OUTP:STAT?")
        if _res.find("ON") >= 0:
            return True
        elif _res.find("OFF") >= 0:
            return False
        else:
            raise ValueError(_res)

    def get_freq(self) -> Tuple[float, float, float]:
        """Get frequency information

        Returns:
            tuple: (current_freq, max_freq, min_freq) in Hz

        Example:
            curr, max_f, min_f = sg.get_freq()
            print(f"Current: {curr/1e9:.1f} GHz")
            print(f"Range: {min_f/1e9:.1f} - {max_f/1e9:.1f} GHz")
        """
        _res_max = self.query("FREQ:MAX?")
        _res_min = self.query("FREQ:MIN?")
        _res_cur = self.query("FREQ:CW?")
        _max = float(_res_max.replace("HZ", ""))
        _min = float(_res_min.replace("HZ", ""))
        _curr = float(_res_cur.replace("HZ", ""))
        return _curr, _max, _min

    def status(self, verbose: bool = False) -> List[str]:
        list_status = []
        list_status.append(["Identity", self.query("*IDN?")])
        list_status.append(["Revision", self.query("*REV?")])
        list_status.append(["USB Input Voltage", self.query("*SYSVOLTS?"), "[V]"])
        list_status.append(["System Temperature", self.query("*TEMPC?"), "[degC]"])
        list_status.append(["Output", self.query("OUTP:STAT?")])
        list_status.append(["Current Power", self.query("POWER?")])
        list_status.append(["Current Frequency", self.query("FREQ:CW?")])
        list_status.append(["Error log", self.query("SYST:ERR?")])
        if verbose:
            for _st in list_status:
                _msg = f"{MSG} {_st[0]:<23} -- {_st[1]}"
                if len(_st) > 2:
                    _msg += f" {_st[2]}"
                logger.info(_msg)
        flush_current_logger()
        return list_status



if __name__ == "__main__":
    sg = SG40000pro(hardreset=True)
    power = 15.0
    freq = 22e9
    sg.on(power, freq)
    sg.off()

    # print("FREQ, MAX, MIN: {0[0]:.1f} Hz, {0[1]:.1f} Hz, {0[2]:.1f} Hz".format(sg.get_freq()))
