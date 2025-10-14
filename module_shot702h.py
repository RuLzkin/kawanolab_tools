import platform
import time
from typing import Optional
import numpy as np
import pyvisa
from pyvisa import ResourceManager
from pyvisa.resources import SerialInstrument
from pyvisa.constants import StopBits, Parity, VI_ASRL_FLOW_RTS_CTS
from typing import cast
import logging
from module_usbtmc import USBTMCResourceManager

MSG = "SHOT702H>>"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Shot702h():
    def __init__(self, name: Optional[str] = None, debug=False) -> None:
        self.debug = debug
        if debug:
            return
        self.device: Optional[SerialInstrument] = None
        self.res_man = ResourceManager() if platform.system() == 'Windows' else USBTMCResourceManager()
        num_device_suggest = None

        for _ind, _res in enumerate(self.res_man.list_resources()):
            print(f"{MSG} Resource Manager>>", _res, end="", flush=True)
            # Q:コマンド等を使ってSHOT702Hであることを確認するほうが良い
            # if "ASRL" not in _res and "TCPIP" not in _res and "USB" not in _res and "GPIB" not in _res:
            #     print(" -- not via ASRL or not via TCPIP")
            #     continue
            # _inst = self.res_man.open_resource(_res)
            # if _inst is None:
            #     print(_res + "can not be opend")
            #     continue
            if "ASRL" not in _res:
                print('\r\033[K', end='', flush=True)
                logger.info(f"{MSG} Resource Manager>> {_res} -- not via ASRL")
                continue
            try:
                _inst = cast(SerialInstrument, self.res_man.open_resource(_res))
                if _inst is None:
                    # print(_res + "can not be opend")
                    print('\r\033[K', end='', flush=True)
                    logger.info(f"{MSG} Resource Manager>> {_res} -- could not be opened")
                    continue
                self.setup_serial(_inst)
                while True:
                    _idn = _inst.query("?:N")
                    if _idn not in "NG":
                        break
                    time.sleep(1.0)
                _inst.close()
            except pyvisa.errors.VisaIOError as e:
                print(" --", e)
                continue
            if "SHOT-702H" in _idn:
                num_device_suggest = _ind
                # print(" -- Found SHOT-702H")
                print('\r\033[K', end='', flush=True)
                logger.info(f"{MSG} Resource Manager>> {_res} -- Found SHOT-702H")
                break
            else:
                # print(" -- Other device")
                logger.info(f"{MSG} Resource Manager>> {_res} -- Other device")

        if num_device_suggest is not None:
            self.setup(num_device_suggest)

        if num_device_suggest is None:
            raise ValueError("Could not find SHOT-702H")

    def setup_serial(self, instrument: SerialInstrument):
        instrument.baud_rate = 38400
        instrument.data_bits = 8
        instrument.parity = Parity.none
        instrument.stop_bits = StopBits.one
        instrument.flow_control = VI_ASRL_FLOW_RTS_CTS  # RTS/CTS # type: ignore
        instrument.timeout = 5000  # ms

        instrument.read_termination = '\r\n'
        instrument.write_termination = '\r\n'
        time.sleep(0.5)

    def _exist_device(self):
        return self.device is not None

    def setup(self, num_device):
        self.device = cast(SerialInstrument, self.res_man.open_resource(
            self.res_man.list_resources()[num_device]
        ))
        self.setup_serial(self.device)

        self.wait()

    def move_abs(self, list_value, show=False, show_cmd=False):
        if self.device is None:
            raise ValueError("Device is not connected")
        if self.debug:
            time.sleep(0.1)
            return

        list_tpp = self.TravelPerPulse()

        list_sign = ["+", "+"]
        for _i in range(len(list_value)):
            list_value[_i] = int(list_value[_i] / list_tpp[_i])
            if list_value[_i] < 0:
                list_sign[_i] = "-"
                list_value[_i] *= -1
        self.wait(show=False)
        str_command = "A:W{0[0]}P{1[0]}{0[1]}P{1[1]}".format(list_sign, list_value)
        if show_cmd:
            # print(str_command)
            logger.info(f"{MSG} move_abs command: {str_command}")
        _ret_a = self.device.query(str_command)
        self.wait(show=False)
        _ret_g = self.device.query("G:")
        self.wait(show)

    def rotate_abs(self, list_value_deg, show=False, show_cmd=False):
        if self.device is None:
            raise ValueError("Device is not connected")
        if self.debug:
            time.sleep(0.1)
            return

        list_tpp = self.TravelPerPulse()

        list_sign = ["+", "+"]
        for _i in range(len(list_value_deg)):
            list_value_deg[_i] = int(list_value_deg[_i] / list_tpp[_i] * 100)
            if list_value_deg[_i] < 0:
                list_sign[_i] = "-"
                list_value_deg[_i] *= -1
        self.wait(show=False)
        str_command = "A:W{0[0]}P{1[0]}{0[1]}P{1[1]}".format(list_sign, list_value_deg)
        if show_cmd:
            # print(str_command)
            logger.info(f"{MSG} move_abs command: {str_command}")
        _ret_a = self.device.query(str_command)
        self.wait(show=False)
        _ret_g = self.device.query("G:")
        self.wait(show, rotate=True)

    def wait(self, show=False, rotate=False):
        if self.debug:
            return
        if self.device is None:
            raise ValueError("Device is not connected")
        # if show:
        #     print("")
        while "B" in self.device.query("!:"):
            time.sleep(0.01)
            if show:
                _tpp = self.TravelPerPulse()
                _msg = self.device.query("Q:").rstrip()
                for _cut in ("\x00", "\r", "\n", " "):
                    _msg = _msg.replace(_cut, "")
                list_status = _msg.split(",")
                if rotate:
                    print(
                        f"\r{MSG} current position:{float(list_status[0]) * _tpp[0] / 100: 4.2f} deg, {float(list_status[1]) * _tpp[1] / 100: 4.2f} deg", end="")
                else:
                    print(
                        f"\r{MSG} current position:",
                        float(list_status[0]) * _tpp[0], "um,",
                        float(list_status[1]) * _tpp[1], "um,",
                        end="")
            # Timeout process
        if show:
            print('\r\033[K', end='', flush=True)
            _tpp = self.TravelPerPulse()
            _msg = self.device.query("Q:").rstrip()
            for _cut in ("\x00", "\r", "\n", " "):
                _msg = _msg.replace(_cut, "")
            list_status = _msg.split(",")
            if rotate:
                logger.info(f"{MSG} current position: { float(list_status[0]) * _tpp[0] / 100: 4.2f} deg, {float(list_status[1]) * _tpp[1] / 100: 4.2f} deg")
            else:
                logger.info(f"{MSG} current position: { float(list_status[0]) * _tpp[0]} um, {float(list_status[1]) * _tpp[0]} um")

    def status(self):
        if self.device is None:
            raise ValueError("Device is not connected")
        str_ret = self.device.query("Q:")
        for old in ("\x00", "\r", "\n", " ", "U"):
            str_ret = str_ret.replace(old, "")
        list_status = str_ret.split(",")
        list_pulse = np.array(list_status[:2], dtype=int).tolist()
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

    def homeposition(self, show=False, rotate=False):
        if self.debug:
            return
        if self.device is None:
            raise ValueError("Device is not connected")
        self.device.query("H:W")
        self.wait(show, rotate)

    def set_memory_switch(self):
        if self.device is None:
            raise ValueError("Device is not connected")
        self.device.query("MS:ON")
        # self.device.query("MS:SET,6,9,2000")
        # self.device.query("MS:SET,6,12,2000")
        # self.device.query("MS:SET,6,15,2000")
        self.device.query("MS:OFF")
        self.wait()


if __name__ == "__main__":
    shot702 = Shot702h()
    # SHOT702H.set_memory_switch()
    # shot702.homeposition(show=True)
    shot702.homeposition(show=True, rotate=True)
    # print(SHOT702H.TravelPerPulse())
    # print(SHOT702H.status()[0])
    # shot702.move_abs([10e3, 10e3], show=True, show_cmd=True)
    # shot702.move_abs([0e3, 0e3], show=True, show_cmd=True)
    shot702.rotate_abs([180, 180], show=True, show_cmd=True)
    # print(SHOT702H.status()[0])
    print(shot702.status()[0])
