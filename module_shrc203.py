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
    DEGREES_TO_PULSE_RATIO = 289 / 360

    def __init__(self, num_device=None, debug=False) -> None:
        self.debug = debug
        self._device: Optional[MessageBasedResource] = None
        self.res_man = pyvisa.ResourceManager()
        num_device_suggest = None

        if debug:
            return

        for _ind, _res in enumerate(self.res_man.list_resources()):
            print("SHRC203Wrapper>> Resource Manager>>", _res, end="", flush=True)
            # TODO: Q:コマンド等を使ってSHRC203であることを確認するほうが良い
            # if "ASRL" not in _res and "TCPIP" not in _res and "USB" not in _res and "GPIB" not in _res:
            #     print(" -- not via ASRL or not via TCPIP")
            #     continue
            # _inst = self.res_man.open_resource(_res)
            # if _inst is None:
            #     print(_res + "can not be opend")
            #     continue

            try:
                with cast(MessageBasedResource, self.res_man.open_resource(_res)) as _inst:
                    _idn = _inst.query("*IDN?")
                    if "SHRC-203" in _idn:
                        num_device_suggest = _ind
                        print(" -- Found SHRC-203")
                        break
            except pyvisa.errors.VisaIOError as e:
                print(f" -- Failed to connect: {e}")
                continue
            except Exception as e:
                print(f" -- Unexpected error with: {e}")
                continue
            print(" -- Other device")
        target_device = num_device if num_device is not None else num_device_suggest
        if target_device is not None:
            self.setup(target_device)
        else:
            raise ValueError("Could not find SHRC-203")

    def __del__(self):
        self._cleanup()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._cleanup()
        # 例外を再発生させる場合はFalseを返す
        return False

    def _cleanup(self):
        """リソースをクリーンアップ"""
        if hasattr(self, '_device') and self._device:
            try:
                self._device.close()
            except Exception:
                pass
            self._device = None

        if hasattr(self, 'res_man') and self.res_man:
            try:
                self.res_man.close()
            except Exception:
                pass
            self.res_man = None

    @property
    def device(self) -> MessageBasedResource:
        if self._device is None:
            raise ValueError("Device is not connected")
        return self._device

    @property
    def is_connected(self) -> bool:
        return self._device is not None

    def _exist_device(self):
        return self.device is not None

    def setup(self, num_device):
        if self.res_man is None:
            raise ValueError("ReourceManager does not exist")
        self._device = cast(MessageBasedResource, self.res_man.open_resource(
            self.res_man.list_resources()[num_device]
        ))
        self.wait()

    def close(self):
        """明示的にリソースを閉じる"""
        self._cleanup()

    def move_abs(self, list_pulse, list_unit=["U", "U", "U"], show=False, show_cmd=False):
        if self.debug:
            time.sleep(0.1)
            return

        for _i in range(3):
            if list_unit[_i] == "D":
                list_pulse[_i] = list_pulse[_i] * self.DEGREES_TO_PULSE_RATIO

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

    def _clean_response(self, response: str) -> str:
        """レスポンス文字列をクリーンアップ"""
        for char in ("\x00", "\r", "\n", " "):
            response = response.replace(char, "")
        return response

    def status(self):
        str_ret = self.device.query("Q:Su")
        str_ret = self._clean_response(str_ret).replace("U", "")
        list_status = str_ret.split(",")
        list_pulse = [int(x) for x in list_status[:3]]
        self.wait()
        return list_pulse, list_status[3:]

    def Version(self):
        return self.device.query("?:V")

    def CurrentAbsolutePulseValue(self):
        str_ret = self.device.query("?:AW")
        list_ret = np.array(str_ret.split(","), dtype=int).tolist()
        return list_ret

    def TravelPerPulse(self):
        str_ret = self.device.query("?:PW")
        str_ret = self._clean_response(str_ret)
        list_ret = np.array(str_ret.split(","), dtype=float).tolist()
        return list_ret

    def NumberOfDivisions(self):
        str_ret = self.device.query("?:SW")
        str_ret = self._clean_response(str_ret)
        arr_ret = np.array(str_ret.split(","), dtype=float).tolist()
        return arr_ret

    def set_NumberOfDivisions(self, list_nod: list = [2, 2, 2, 2]):
        for _i, _num in enumerate(list_nod):
            self.device.query("S:{0}{1}".format(_i + 1, _num))
        self.wait()

    def homeposition(self, show=False):
        if self.debug:
            return
        self.device.query("H:W")
        self.wait(show)

    def set_memory_switch(self):
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
