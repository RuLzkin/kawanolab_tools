import time
import serial.tools.list_ports
from windfreak import SynthHD


class Synth_Wrapper():
    def __init__(self, str_port: str = None) -> None:
        if str_port is None:
            list_port = list(serial.tools.list_ports.comports())
            str_port = list_port[0].name
        self.synth = SynthHD(str_port)
        self.synth[0].enable = False
        self.synth[0].power = 15
        self.synth[0].frequency = 8.0e9

    def on(self, power=None, frequency=None):
        if power is not None:
            self.synth[0].power = power
        if frequency is not None:
            self.synth[0].frequency = frequency
        self.synth[0].enable = True
        time.sleep(0.1)

    def off(self):
        self.synth[0].enable = False


class Synth_Dummy():
    def __init__(self, *args, **kwargs) -> None:
        print("debug: synth dummy [generated]")

    def on(self, *args, **kwargs):
        pass

    def off(self, *args, **kwargs):
        pass


if __name__ == "__main__":
    synth = Synth_Wrapper(None)
    synth.on(15, 8e9)
    synth.off()
