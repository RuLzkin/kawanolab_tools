import time
from typing import Optional
import numpy as np
import pyvisa

"""
A: コマンドで指定したらG:したほうがいい
?:Aで得られる情報はA:で入力した情報となる
G:しないと?:Aで得られる情報と実際の位置が一致しなくなる
X: 50000 pulse -> 100 mm
Y: 85000 pulse ->  85 mm
Z: 85000 pulse ->  85 mm
"""


class Shot304gs():
    def __init__(self, num_device=None) -> None:
        self.device: Optional[pyvisa.resources.Resource] = None
        self.res_man = pyvisa.ResourceManager()
        num_device_suggest = 0
        for _ind, _res in enumerate(self.res_man.list_resources()):
            print("Resource Manager>", _res)
            # Q:コマンド等を使ってSHOT304であることを確認するほうが良い
            if "GPIB" in _res:
                num_device_suggest = _ind

        if num_device is not None:
            self.setup(num_device)
        else:
            self.setup(num_device_suggest)

    def _exist_device(self):
        return self.device is not None

    def setup(self, num_device):
        self.device = self.res_man.open_resource(
            self.res_man.list_resources()[num_device]
        )
        self.wait()
        self.set_NumberOfDivisions([4, 2, 2, 2])
        print("Travel Per Pulse:", self.TravelPerPulse())

    def move_abs(self, list_pulse, show=False):
        str_command = "A:W+P{0[0]}+P{0[1]}+P{0[2]}+P{0[3]}".format(list_pulse)
        self.device.query(str_command)
        self.device.query("G:")
        self.wait(show)

    def wait(self, show=False):
        if not self._exist_device():
            return None
        # _start = time.perf_counter()
        if show:
            print("")
        while "B" in self.device.query("!:"):
            if show:
                print("\r>> current position:", self.device.query("Q:").rstrip(), end="")
            time.sleep(0.01)
            # Timeout process
        if show:
            print("")

    def status(self):
        if not self._exist_device():
            return None
        str_ret = self.device.query("Q:")
        # print(str_ret)
        # print(type(str_ret))
        for old in ("\x00", "\r", "\n", " "):
            str_ret = str_ret.replace(old, "")
        list_status = str_ret.split(",")
        # print(list_status)
        list_pulse = np.array(list_status[:4], dtype=int).tolist()
        self.wait()
        return list_pulse, list_status[4:]

    def Version(self):
        if not self._exist_device():
            return None
        return self.device.query("?:V")

    def CurrentAbsolutePulseValue(self):
        if not self._exist_device():
            return None
        str_ret = self.device.query("?:AW")
        list_ret = np.array(str_ret.split(","), dtype=int).tolist()
        return list_ret

    def TravelPerPulse(self):
        if not self._exist_device():
            return None
        str_ret = self.device.query("?:PW")
        # print(str_ret)
        for old in ("\x00", "\r", "\n", " "):
            str_ret = str_ret.replace(old, "")
        list_ret = np.array(str_ret.split(","), dtype=float).tolist()
        return list_ret

    def NumberOfDivisions(self):
        if not self._exist_device():
            return None
        str_ret = self.device.query("?:SW")
        # print(str_ret)
        for old in ("\x00", "\r", "\n", " "):
            str_ret = str_ret.replace(old, "")
        arr_ret = np.array(str_ret.split(","), dtype=float).tolist()
        return arr_ret

    def set_NumberOfDivisions(self, list_nod: list = [2, 2, 2, 2]):
        if not self._exist_device():
            return None
        for _i, _num in enumerate(list_nod):
            self.device.query("S:{0}{1}".format(_i + 1, _num))

    def homeposition(self):
        self.device.query("H:W")
        self.wait()


class Shot_304gs_dummy():
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
    shot304 = Shot304gs()
    shot304.wait()
    shot304.homeposition()
    # shot304.move_abs([10000, 10000, 10000, 0], show=True)
    # shot304.move_abs([100000, 80000, 80000, 0], show=True)
    # shot304.move_abs([25000, 40000, 0, 0], show=True)
    # shot304.move_abs([50000, 20000, 48000, 0], show=True)
    # shot304.move_abs([25000, 40000, 68000, 0], show=True)
    # shot304.move_abs([25000, 40000, 80000, 0], show=True)
    # shot304.move_abs([25000, 40000, 0, 0], show=True)
    # shot304.move_abs([25000, 40000, 70000, 0], show=True)
    shot304.set_NumberOfDivisions([2, 2, 2, 2])
