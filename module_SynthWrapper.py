from typing import Optional, Tuple
import time
import serial.tools.list_ports
from windfreak import SynthHD


class Synth_Wrapper():
    def __init__(self, str_port: Optional[str] = None, num_port: Optional[int] = None, debug: bool = False) -> None:
        """Synth_Wrapper(str_port: str = None, num_port: int = 0, debug=False)

        Args:
            str_port: str, this has priority over num_port (ex. "COM3")
            num_port: int, this is based on list(serial.tools.list_ports.comports())
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
            for _i in range(len(list_port)):
                # print(_i, list_port[_i].name)
                if num_port is None:
                    try:
                        print("SynthHDWrapper>> Connect --", list_port[_i].name, ">> ", end="", flush=True)
                        _synth = SynthHD(list_port[_i].name)
                    except:  # noqa
                        print("Could not be connected")
                    else:
                        print("Successfully connected")
                        _synth.close()
                        num_port = _i
                        break
            if num_port is None:
                raise ValueError("Valid port not found")
            str_port = list_port[num_port].name
        self.synth = SynthHD(str_port)
        self.synth[0].enable = False
        self.synth[0].power = 15
        self.synth[0].frequency = 8.0e9
        print("SynthHDWrapper>> Connect to", str_port)

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

    def on(self, power: Optional[float] = None, frequency: Optional[float] = None) -> Tuple[float, float, bool]:
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
        if power is None:
            power = self.synth[0].power
        else:
            self.synth[0].power = float(power)
        if frequency is not None:
            self.synth[0].frequency = float(frequency)
        self.synth[0].enable = True
        is_calibrated = self.synth[0].calibrated
        step_power = 0.5
        if power is None:
            raise ValueError("Power value is invalid")
        _sign = (power >= 0) * 2 - 1
        while not is_calibrated:
            self.synth[0].power -= step_power * _sign
            time.sleep(0.1)  # for signal rise time
            is_calibrated = self.synth[0].calibrated
        time.sleep(0.01)  # for signal rise time
        return self.status()


if __name__ == "__main__":
    # synth = Synth_Wrapper("COM3")
    synth = Synth_Wrapper("COM3")
    synth.on(15, 8e9)
    synth.off()

    # import numpy as np
    # while True:
    #     for _freq in np.arange(1, 23.5, 0.1):
    #         # for _pow in np.arange(0, 15.1, 0.5):
    #         for _pow in np.arange(15, 15.1, 0.5):
    #             start = time.time()
    #             synth.on(_pow, _freq * 1e9)
    #             print(
    #                 "\r {0:3.1f} GHz, {1:3.1f} dB, {2:5.1f} [msec]".format(
    #                     _freq, _pow, 1000 * (time.time() - start)),
    #                 end="")
    #             time.sleep(0.5)
    #             synth.off()

    import numpy as np
    from matplotlib import pyplot as plt
    from tqdm import tqdm
    power = np.arange(-40, +18, 0.5)
    freq = np.arange(1, 24, 0.5) * 1e9
    mat_power = np.zeros((len(power), len(freq)))
    mat_freq = np.zeros((len(power), len(freq)))
    mat_cali = np.zeros((len(power), len(freq)))
    mat_time = np.zeros((len(power), len(freq)))
    for _i_f, _f in tqdm(enumerate(freq), total=len(freq)):
        for _i_p, _p in tqdm(enumerate(power), total=len(power), leave=False):
            _start = time.perf_counter()
            # _pow, _freq, _cali = synth.on_feedback(_p, _f)
            _pow, _freq, _cali = synth.on(_p, _f)
            _time = time.perf_counter() - _start
            synth.off()
            mat_power[_i_p, _i_f] = _pow
            mat_freq[_i_p, _i_f] = _freq * 1e-9
            mat_cali[_i_p, _i_f] = 1.0 if _cali else 0.0
            mat_time[_i_p, _i_f] = _time
    _df = (freq[1] - freq[0]) / 2
    _dp = (power[1] - power[0]) / 2
    _extent = ((freq[0] - _df) * 1e-9, (freq[-1] + _df) * 1e-9, power[0] - _dp, power[-1] + _dp)
    plt.figure()
    plt.imshow(mat_power, extent=_extent, aspect="auto", origin='lower')
    plt.xlabel("Frequency [GHz]")
    plt.ylabel("Power [dBm]")
    plt.colorbar(label="Power")
    plt.tight_layout()
    plt.figure()
    plt.imshow(mat_freq, extent=_extent, aspect="auto", origin='lower')
    plt.xlabel("Frequency [GHz]")
    plt.ylabel("Power [dBm]")
    plt.colorbar(label="Frequency")
    plt.tight_layout()
    plt.figure()
    plt.imshow(mat_cali, extent=_extent, aspect="auto", origin='lower')
    plt.xlabel("Frequency [GHz]")
    plt.ylabel("Power [dBm]")
    plt.colorbar(label="Calibrated")
    plt.tight_layout()
    plt.figure()
    plt.imshow(mat_time, extent=_extent, aspect="auto", origin='lower')
    plt.xlabel("Frequency [GHz]")
    plt.ylabel("Power [dBm]")
    plt.colorbar(label="Time")
    plt.tight_layout()
    plt.show()
