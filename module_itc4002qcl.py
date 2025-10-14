import pyvisa
from pyvisa.resources import MessageBasedResource
from typing import Optional, cast, List
from time import sleep
import logging

"""
MEAS:TEMP?
MEAS:CURR?
MEAS:VOLT?
SOUR:CURR 0.45
SOUR2:TEMP 20.0C
OUTP2 ON
OUTP ON
OUTP?
OUTP OFF
OUTP?
OUTP2 OFF
"""
ADDRESS_DEVICE_A = "USB::4883::32842::M01263117"
ADDRESS_DEVICE_B = "USB::4883::32842::M01263118"
ADDRESS_DEVICE_C = "USB::4883::32842::M01262971"

PARAMETER_A = {"temp_set": 25.0, "unit_set": "C", "curr_set": 0.27}
PARAMETER_B = {"temp_set": 25.0, "unit_set": "C", "curr_set": 0.35}
PARAMETER_C = {"temp_set": 20.0, "unit_set": "C", "curr_set": 0.45}

MSG = "ITC4002QCL>>"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ITC4002QCL():
    device: Optional[MessageBasedResource]
    curr_set: Optional[float]
    temp_set: Optional[float]

    def __init__(self, address_device=None, debug=False) -> None:
        self.debug = debug
        if debug:
            return
        if address_device is None:
            raise ValueError("Please specify address_device")

        self.res_man = pyvisa.ResourceManager()
        self.device = cast(MessageBasedResource, self.res_man.open_resource(address_device))
        logger.info(f"{MSG} Connected to {address_device}")
        res_idn = self.query("*IDN?")
        logger.info(f"{MSG} Device ID: {res_idn}")
        self.address = address_device
        self.curr_set = None
        self.temp_set = None

    def __del__(self):
        if self.device is not None:
            self.device.close()
            self.device = None
            logger.info(f"{MSG} Device connection closed: {self.address}")

    def write(self, command: str) -> None:
        if self.debug:
            logger.debug(f"{MSG} Debug mode: write('{command}')")
            return
        if self.device is None:
            raise ValueError("Device not connected")
        self.device.write(command)
        # logger.debug(f"{MSG} write('{command}')")
        logger.debug(f"{MSG} write('{command}')")
        _err_after = self.check_error()
        if len(_err_after) > 0:
            logger.error(f"{MSG} Errors after write('{command}')")

    def query(self, command: str) -> str:
        if self.debug:
            logger.debug(f"{MSG} Debug mode: query('{command}')")
            return ""
        if self.device is None:
            raise ValueError("Device not connected")
        response = self.device.query(command).rstrip()
        logger.debug(f"{MSG} query('{command}') -> '{response}'")
        # no err check for query because error checker calls query
        return response

    def check_error(self) -> List:
        _list_err = []
        while True:
            _err = self.query("SYST:ERR?")
            if _err.startswith("+0"):
                break
            _list_err.append(_err)
        if len(_list_err) > 0:
            logger.error(f"{MSG} Errors: {_list_err}")
        return _list_err

    def meas_temp(self) -> float:
        _temp = float(self.query("MEAS:TEMP?"))
        return _temp

    def meas_curr(self) -> float:
        _curr = float(self.query("MEAS:CURR?"))
        return _curr

    def set_source_temp(self, value: float, unit: str = "C") -> None:
        self.write(f"SOUR2:TEMP {value}{unit}")

    def set_source_curr(self, value: float) -> None:
        self.write(f"SOUR:CURR {value}")

    def tec(self, on: bool = True, percent_threshold: float = 1) -> None:
        _temp_set = self.temp_set
        if _temp_set is None:
            raise ValueError("Temperature setpoint not defined")
        _cmd = "ON" if on else "OFF"
        logger.info(f"{MSG} TEC { _cmd }")
        self.write(f"OUTP2 { _cmd }")

        if not on:
            return
        self.wait_tec(percent_threshold)
        logger.info(f"{MSG} TEC { _cmd } done")

    def ld(self, on: bool = True, threshold = 0.01) -> None:
        _cmd = "ON" if on else "OFF"
        logger.info(f"{MSG} LD { _cmd }")
        self.write(f"OUTP { _cmd }")

        def _cond(curr: float) -> bool:
            return curr >= threshold if on else curr <= threshold
        while not _cond(self.meas_curr()):
            sleep(0.1)
        logger.info(f"{MSG} LD { _cmd } done")
        if on:
            self.wait_tec()
            logger.info(f"{MSG} TEC:stable")

    def wait_tec(self, percent_threshold: float = 1) -> None:
        _temp_set = self.temp_set
        if _temp_set is None:
            raise ValueError("Temperature setpoint not defined")
        def _cond(curr: float) -> bool:
            return abs(curr - _temp_set) / _temp_set <= percent_threshold / 100
        while not _cond(self.meas_temp()):
            sleep(1.0)

    def set_from_lib(self, parameter: dict) -> None:
        if "temp_set" in parameter and "unit_set" in parameter:
            self.set_source_temp(parameter["temp_set"], parameter["unit_set"])
            self.temp_set = parameter["temp_set"]
        if "curr_set" in parameter:
            self.set_source_curr(parameter["curr_set"])
            self.curr_set = parameter["curr_set"]

if __name__ == "__main__":
    itc = ITC4002QCL(ADDRESS_DEVICE_C)
    itc.set_from_lib(PARAMETER_C)

    print("Temperature:", itc.meas_temp())
    print("Current:", itc.meas_curr())
    itc.tec(on=True)
    itc.ld(on=True)
    sleep(3.0)
    itc.ld(on=False)
    itc.tec(on=False)

    itc.check_error()

    print("ITC4002QCL>>", "End of Test")

    # res_man = pyvisa.ResourceManager()
    # device = cast(MessageBasedResource, res_man.open_resource(ADDRESS_DEVICE_C))
    # print(device.query("*IDN?"))
    # device.close()
