import time
from typing import Optional
import numpy as np
import pyvisa
from pyvisa.resources import MessageBasedResource
from typing import cast


"""
A: コマンドで指定したらG:したほうがいい
?:Aで得られる情報はA:で入力した情報となる
G:しないと?:Aで得られる情報と実際の位置が一致しなくなる
"""


class Shrc203():
    def __init__(self, num_device=None, debug=False) -> None:
        self.debug = debug
        if debug:
            return
        self.device: Optional[MessageBasedResource] = None
        self.res_man = pyvisa.ResourceManager()
        num_device_suggest = None

        for _ind, _res in enumerate(self.res_man.list_resources()):
            print("SHRC203Wrapper>> Resource Manager>>", _res, end="", flush=True)
            # Q:コマンド等を使ってSHOT304であることを確認するほうが良い
            # if "ASRL" not in _res and "TCPIP" not in _res and "USB" not in _res and "GPIB" not in _res:
            #     print(" -- not via ASRL or not via TCPIP")
            #     continue
            if "192.168.11." in _res:
                print(" -- Other segment")
                continue
            if "192.168.10.203" in _res:
                print(" -- DAQ970A")
                continue
            try:
                _inst = cast(MessageBasedResource, self.res_man.open_resource(_res))
                if _inst is None:
                    print(_res + "can not be opend")
                    continue
                _idn = _inst.query("*IDN?")
                _inst.close()
            except pyvisa.errors.VisaIOError as e:
                print(" --", e)
                continue
            if "SHRC-203" in _idn:
                num_device_suggest = _ind
                print(" -- Found SHRC-203")
                break
            else:
                print(" -- Other device")

        if num_device is not None:
            self.setup(num_device)
        if num_device_suggest is not None:
            self.setup(num_device_suggest)

        if num_device is None and num_device_suggest is None:
            raise ValueError("Could not find SHRC-203")

    def _exist_device(self):
        return self.device is not None

    def setup(self, num_device):
        self.device = cast(MessageBasedResource, self.res_man.open_resource(
            self.res_man.list_resources()[num_device]
        ))
        self.wait()

    def move_abs(self, list_pulse, show=False):
        if self.device is None:
            raise ValueError("Device is not connected")
        if self.debug:
            time.sleep(0.1)
            return
        self.wait(show=False)
        str_command = "A:W+U{0[0]:.0f}+U{0[1]:.0f}+U{0[2]:.0f}".format(list_pulse)
        self.device.query(str_command)
        self.device.query("G:")
        self.wait(show)

    def wait(self, show=False):
        if self.debug:
            return
        if self.device is None:
            raise ValueError("Device is not connected")
        if show:
            print("")
        while "B" in self.device.query("!:"):
            time.sleep(0.01)
            if show:
                _msg = self.device.query("Q:Su").rstrip()
                for _cut in ("\x00", "\r", "\n", " "):
                    _msg = _msg.replace(_cut, "")
                list_status = _msg.split(",")
                print(
                    "\r>> current position:",
                    list_status[0][1:], "um,",
                    list_status[1][1:], "um,",
                    list_status[2][1:], "um",
                    " " * 20,
                    end="")
            # Timeout process
        if show:
            _msg = self.device.query("Q:Su").rstrip()
            for _cut in ("\x00", "\r", "\n", " "):
                _msg = _msg.replace(_cut, "")
            list_status = _msg.split(",")
            print(
                "\r>> current position:",
                list_status[0][1:], "um,",
                list_status[1][1:], "um,",
                list_status[2][1:], "um",
                " " * 20)

    def status(self):
        if self.device is None:
            raise ValueError("Device is not connected")
        str_ret = self.device.query("Q:Su")
        for old in ("\x00", "\r", "\n", " ", "U"):
            str_ret = str_ret.replace(old, "")
        list_status = str_ret.split(",")
        list_pulse = np.array(list_status[:3], dtype=int).tolist()
        self.wait()
        return list_pulse, list_status[3:]

    def Version(self):
        if self.device is None:
            raise ValueError("Device is not connected")
        return self.device.query("?:V")

    def CurrentAbsolutePulseValue(self):
        if self.device is None:
            raise ValueError("Device is not connected")
        str_ret = self.device.query("?:AW")
        list_ret = np.array(str_ret.split(","), dtype=int).tolist()
        return list_ret

    def TravelPerPulse(self):
        if self.device is None:
            raise ValueError("Device is not connected")
        str_ret = self.device.query("?:PW")
        for old in ("\x00", "\r", "\n", " "):
            str_ret = str_ret.replace(old, "")
        list_ret = np.array(str_ret.split(","), dtype=float).tolist()
        return list_ret

    def NumberOfDivisions(self):
        if self.device is None:
            raise ValueError("Device is not connected")
        str_ret = self.device.query("?:SW")
        for old in ("\x00", "\r", "\n", " "):
            str_ret = str_ret.replace(old, "")
        arr_ret = np.array(str_ret.split(","), dtype=float).tolist()
        return arr_ret

    def set_NumberOfDivisions(self, list_nod: list = [2, 2, 2, 2]):
        if self.device is None:
            raise ValueError("Device is not connected")
        for _i, _num in enumerate(list_nod):
            self.device.query("S:{0}{1}".format(_i + 1, _num))
        self.wait()

    def homeposition(self, show=False):
        if self.debug:
            return
        if self.device is None:
            raise ValueError("Device is not connected")
        self.device.query("H:W")
        self.wait(show)


class Shrc203_dummy():
    def __init__(self, num_device=None) -> None:
        pass

    def _exist_device(self):
        pass

    def setup(self, num_device):
        pass

    def status(self):
        pass

    def wait(self):
        time.sleep(0.1)

    def move_abs(self, list_pulse):
        pass

    def Version(self):
        pass

    def CurrentAbsolutePulseValue(self):
        return [0, 0, 0, 0]

    def TravelPerPulse(self):
        return [1.0, 1.0, 1.0, 1.0]

    def homeposition(self):
        pass


if __name__ == "__main__":
    shrc203 = Shrc203()
    shrc203.homeposition(show=True)
    shrc203.move_abs([50e3, 50e3, 50e3], show=True)
