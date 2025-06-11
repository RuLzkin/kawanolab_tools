import time
from typing import Optional
import serial.tools.list_ports
from windfreak import SynthHD


class Synth_Wrapper():
    def __init__(self, str_port: Optional[str] = None, num_port: Optional[int] = None, debug=False) -> None:
        """Synth_Wrapper(str_port: str = None, num_port: int = 0, debug=False)

        input:
            str_port: str, this has priority over num_port (ex. "COM3")
            num_port: int, this is based on list(serial.tools.list_ports.comports())
            debug: debug mode (dummy mode)
        usage:
            synth = Synth_Wrapper("COM3")
            synth.on(15, 18e9)
            time.sleep(5.0)
            synth.off()
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
                raise ValueError("Device not found")
            str_port = list_port[num_port].name
        self.synth = SynthHD(str_port)
        self.synth[0].enable = False
        self.synth[0].power = 15
        self.synth[0].frequency = 8.0e9
        print("SynthHDWrapper>> Connect to", str_port)

    def on(self, power: Optional[float] = None, frequency: Optional[float] = None):
        """on(power: float | None, frequency: float | None)

        input:
            power: float [dBm] -40 ~ 0.01 ~ +18
            frequency: float [Hz] 0.01e9 ~ 0.1 ~ 24e9
        usage:
            synth.on()
        """
        if self.debug:
            return
        if power is not None:
            self.synth[0].power = power
        if frequency is not None:
            self.synth[0].frequency = frequency
        self.synth[0].enable = True
        time.sleep(0.125)  # for signal rise time

    def off(self):
        """off()

        that's it
        """
        if self.debug:
            return
        self.synth[0].enable = False


if __name__ == "__main__":
    synth = Synth_Wrapper(None)
    synth.on(15, 8e9)
    synth.off()
