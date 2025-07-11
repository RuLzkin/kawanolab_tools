from pathlib import Path
from typing import Optional, Tuple
import time
import logging
import serial.tools.list_ports
import pickle
from tqdm.contrib import tenumerate
from windfreak import SynthHD

MSG = "SynthHDWrapper>>"
MODULE_DIR = Path(__file__).parent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Synth_Wrapper():

    list_lim_freq = []
    list_lim_pow = []

    def __init__(self, str_port: Optional[str] = None, debug: bool = False) -> None:
        """Synth_Wrapper(str_port: str = None, num_port: int = 0, debug=False)

        Args:
            str_port: str, this has priority over num_port (ex. "COM3")
            debug: debug mode (dummy mode)

        Returns:
            Synth_Wrapper: instance

        Examples:
            >>> synth = Synth_Wrapper("COM3")
            >>> synth.on(15, 18e9)
            >>> time.sleep(5.0)
            >>> synth.off()
        """
        self.debug = debug
        if debug:
            return
        if str_port is None:
            list_port = list(serial.tools.list_ports.comports())
            for _port in list_port:
                try:
                    _synth = SynthHD(_port.name)
                except:  # noqa
                    logger.info(f"{MSG} Connect -- {_port.name} >> Could not be connected")
                else:
                    logger.info(f"{MSG} Connect -- {_port.name} >> Successfully connected")
                    _synth.close()
                    str_port = _port.name
                    break
            if str_port is None:
                raise ValueError("Valid port not found")
        self.synth = SynthHD(str_port)
        self.synth[0].enable = False
        self.synth[0].power = 15
        self.synth[0].frequency = 8.0e9
        logger.info(f"{MSG} Connect to {str_port}")
        try:
            self.input_limit()
        except FileNotFoundError:
            logger.warning(f"{MSG} limit list not found")
            self.measure_limit([float(_i) * 1e9 for _i in range(5, 25, 1)])
            self.output_limit()
        else:
            logger.info(f"{MSG} load limit list")

    def on_no_feedback(self, power: Optional[float] = None, frequency: Optional[float] = None) -> Tuple[float, float, bool]:
        """on(power: float | None, frequency: float | None)

        If input args are omitted, the previous values are applied

        Args:
            power (float, None): [dBm] -40 ~ 0.01 ~ +18
            frequency (float, None): [Hz] 0.01e9 ~ 0.1 ~ 24e9

        Returns:
            self.status() (power, frequency, calibrated)

        Examples:
            >>> synth.on()
            >>> synth.on(15, 16e9)
            >>> synth.on(frequency=7.5e9)
        """
        if self.debug:
            return self.status()
        if power is not None:
            self.synth[0].power = float(power)
        if frequency is not None:
            self.synth[0].frequency = float(frequency)
        self.synth[0].enable = True
        time.sleep(0.125)  # for signal rise time
        return self.status()

    def off(self) -> None:
        """off()

        that's it

        Args:
            None

        Returns:
            None

        Examples:
            >>> synth.off()

        """
        if self.debug:
            return
        self.synth[0].enable = False

    def status(self, flag_ghz=False) -> Tuple[float, float, bool]:
        """status()

        return the current power and frequency.
        it works whether the device is switched ON or OFF

        Args:
            flag_ghz (bool, Optional): the unit of the output frequency. False=Hz, True=GHz

        Returns:
            power (float): [dBm]
            frequency (float): [Hz] or [GHz] (default: [Hz])
            calibrated (float): True(OK) or False(NG)

        Examples:
            >>> synth.status()
        """
        if self.debug:
            return 0, 10e9, True
        _pow = self.synth[0].power
        _freq = self.synth[0].frequency
        _cali = self.synth[0].calibrated
        if flag_ghz:
            _freq = _freq * 1e-9
        return _pow, _freq, _cali

    def on(self, power: Optional[float] = None, frequency: Optional[float] = None, use_limit: bool = True) -> Tuple[float, float, bool]:
        """on(power: float | None, frequency: float | None)

        If input args are omitted, the previous values are applied

        Args:
            power (float, None): [dBm] -40 ~ 0.01 ~ +18
            frequency (float, None): [Hz] 0.01e9 ~ 0.1 ~ 24e9
            use_limit (bool)

        Returns:
            self.status() (power, frequency, calibrated)

        Examples:
            >>> synth.on()
            >>> synth.on(15, 16e9)
            >>> synth.on(frequency=7.5e9)
        """
        if self.debug:
            return self.status()
        if frequency is not None:
            self.synth[0].frequency = float(frequency)
        if power is None:
            power = self.synth[0].power
        else:
            if use_limit and frequency is not None:
                try:
                    pow_lim = self.limited_power(frequency)
                    # print("Power limit:", pow_lim)
                except ValueError:
                    # print("Power limit not found")
                    pow_lim = 15
                power = min(power, pow_lim)
            self.synth[0].power = float(power)
        self.synth[0].enable = True
        is_calibrated = self.synth[0].calibrated
        step_power = 0.1
        if power is None:
            raise ValueError("Power value is invalid")
        _sign = (power >= 0) * 2 - 1
        while not is_calibrated:
            self.synth[0].power -= step_power * _sign
            # print("not calibrated:", self.synth[0].power)
            time.sleep(0.1)  # for signal rise time
            is_calibrated = self.synth[0].calibrated
        time.sleep(0.01)  # for signal rise time
        return self.status()

    def output_limit(self):
        with open(MODULE_DIR / "lib_synthhd_power.wf", "wb") as f:
            pickle.dump([self.list_lim_freq, self.list_lim_pow], f)

    def input_limit(self):
        with open(MODULE_DIR / "lib_synthhd_power.wf", "rb") as f:
            _list_load = pickle.load(f)
        self.list_lim_freq, self.list_lim_pow = _list_load

    def measure_limit(self, list_hz_freq: list):
        """measure_limit
        """
        self.list_lim_freq = []
        self.list_lim_pow = []
        for _i, _freq in tenumerate(list_hz_freq):
            _pow, _, _ = self.on(15, _freq, use_limit=False)
            time.sleep(0.1)
            self.off()
            self.list_lim_freq.append(_freq)
            self.list_lim_pow.append(_pow)

    def limited_power(self, frequency: float, verbose=False):
        if verbose:
            logger.info(f"{MSG} limiter>>> input freq: {frequency}")
        if len(self.list_lim_freq) == 0:
            raise ValueError("Invalid limit list")
        if frequency > self.list_lim_freq[-1] or frequency < self.list_lim_freq[0]:
            raise ValueError(f"{frequency} is out of list")
        try:
            index_exact = self.list_lim_freq.index(frequency)
            pow_lim = self.list_lim_pow[index_exact]
            return pow_lim
        except ValueError:
            pass

        for _i in range(len(self.list_lim_freq) - 1):
            _a, _b = self.list_lim_freq[_i], self.list_lim_freq[_i + 1]
            if _a < frequency < _b:
                pow_lim = ((frequency - _a) * self.list_lim_pow[_i] + (_b - frequency) * self.list_lim_pow[_i + 1]) / (_b - _a)
                return pow_lim

        raise ValueError("Unexpected error occured")


if __name__ == "__main__":
    synth = Synth_Wrapper("COM3")
    synth.on(15, 8e9)
    synth.off()

    """Limiter"""
    # vec_freq = np.arange(4.5, 24.001, 0.1) * 1e9
    # synth.measure_limit(vec_freq.tolist())
    # synth.output_limit()

    """Limiter Check"""
    from matplotlib import pyplot as plt
    plt.figure()
    plt.plot(synth.list_lim_freq, synth.list_lim_pow)
    plt.show()
