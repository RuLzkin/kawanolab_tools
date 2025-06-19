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
            # Q:コマンド等を使ってSHRC203であることを確認するほうが良い
            # if "ASRL" not in _res and "TCPIP" not in _res and "USB" not in _res and "GPIB" not in _res:
            #     print(" -- not via ASRL or not via TCPIP")
            #     continue
            # _inst = self.res_man.open_resource(_res)
            # if _inst is None:
            #     print(_res + "can not be opend")
            #     continue
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

    def move_abs(self, list_pulse, list_unit=["U", "U", "U"], show=False, show_cmd=False):
        if self.device is None:
            raise ValueError("Device is not connected")
        if self.debug:
            time.sleep(0.1)
            return

        for _i in range(3):
            if list_unit[_i] == "D":
                list_pulse[_i] = list_pulse[_i] / 360 * 289

        list_sign = ["+", "+", "+"]
        for _i in range(len(list_pulse)):
            if list_pulse[_i] < 0:
                list_sign[_i] = "-"
                list_pulse[_i] *= -1
        self.wait(show=False)
        str_command = "A:W{0[0]}{1[0]}{2[0]:.2f}{0[1]}{1[1]}{2[1]:.2f}{0[2]}{1[2]}{2[2]:.2f}".format(list_sign, list_unit, list_pulse)
        if show_cmd:
            print(str_command)
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
                    "\rSHRC203Wrapper>> current position:",
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
                "\rSHRC203Wrapper>> current position:",
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

    def set_memory_switch(self):
        if self.device is None:
            raise ValueError("Device is not connected")
        self.device.query("MS:ON")
        self.device.query("MS:SET,6,9,2000")
        self.device.query("MS:SET,6,12,2000")
        self.device.query("MS:SET,6,15,2000")
        self.device.query("MS:OFF")
        self.wait()


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
    # shrc203.set_memory_switch()
    shrc203.homeposition(show=True)
    shrc203.move_abs([50e3, 50e3, 50e3], show=True, show_cmd=True)
