import time
from typing import Optional
import numpy as np
from pyvisa import ResourceManager
from pyvisa.resources import SerialInstrument
from pyvisa.constants import StopBits, Parity, VI_ASRL_FLOW_RTS_CTS
from typing import cast
import logging

MSG = "SHOT702H>>"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Shot702h():
    def __init__(self, port: str, debug=False) -> None:
        self.debug = debug
        if debug:
            return
        self.device: Optional[SerialInstrument] = None
        self.res_man = ResourceManager()

        self.device = cast(SerialInstrument, self.res_man.open_resource(port))
        self.setup_serial(self.device)
        self.wait()
        logger.info(f"{MSG} Connected: {port}")
        _idn = self.device.query("?:N")
        logger.info(f"{MSG} IDN Response: {_idn}")

        self.tpp = self.TravelPerPulse()

    def setup_serial(self, instrument: SerialInstrument):
        instrument.baud_rate = 38400
        instrument.data_bits = 8
        instrument.parity = Parity.none
        instrument.stop_bits = StopBits.one
        instrument.flow_control = VI_ASRL_FLOW_RTS_CTS  # RTS/CTS # type: ignore
        instrument.timeout = 5000  # ms

        instrument.read_termination = '\r\n'
        instrument.write_termination = '\r\n'
        time.sleep(0.1)

    def __del__(self):
        if self.device is not None:
            self.device.close()
            self.device = None
            logger.info(f"{MSG} Device connection closed")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.device is not None:
            self.device.close()
            self.device = None
            logger.info(f"{MSG} Device connection closed")

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

        list_sign = ["+", "+"]
        for _i in range(len(list_value_deg)):
            list_value_deg[_i] = list_value_deg[_i] % 360
            if list_value_deg[_i] > 350:
                raise ValueError("350~359deg causes unexpected error")
            list_value_deg[_i] = int((list_value_deg[_i]) / self.tpp[_i] * 100)

        self.wait(show=False)
        str_command = "A:W{0[0]}P{1[0]}{0[1]}P{1[1]}".format(list_sign, list_value_deg)
        if show_cmd:
            # print(str_command)
            logger.info(f"{MSG} move_abs command: {str_command}")
        _ret_a = self.device.query(str_command)
        self.wait(show=False, rotate=True)
        _ret_g = self.device.query("G:")
        self.wait(show, rotate=True)

    def wait(self, show=False, rotate=False):
        if self.debug:
            return
        if self.device is None:
            raise ValueError("Device is not connected")
        # if show:
        #     print("")
        while "R" not in self.device.query("!:", 0.01):
            time.sleep(0.01)
            if show and "B" in self.device.query("!:", 0.01):
                _tpp = self.tpp
                _msg = self.device.query("Q:").rstrip()
                for _cut in ("\x00", "\r", "\n", " "):
                    _msg = _msg.replace(_cut, "")
                list_status = _msg.split(",")
                if rotate:
                    print(f"\r{MSG} current position:{float(list_status[0]) * _tpp[0] / 100:7.2f} deg, {float(list_status[1]) * _tpp[1] / 100:7.2f} deg", end="")
                else:
                    print(f"\r{MSG} current position:{float(list_status[0]) * _tpp[0]:9.1f} um, {float(list_status[1]) * _tpp[1]:9.1f} um", end="")
            # Timeout process
        if show:
            print('\r\033[K', end='', flush=True)
            _tpp = self.tpp
            _msg = self.device.query("Q:").rstrip()
            for _cut in ("\x00", "\r", "\n", " "):
                _msg = _msg.replace(_cut, "")
            list_status = _msg.split(",")
            if rotate:
                logger.info(f"{MSG} current position: { float(list_status[0]) * _tpp[0] / 100:7.2f} deg, {float(list_status[1]) * _tpp[1] / 100:7.2f} deg")
            else:
                logger.info(f"{MSG} current position: { float(list_status[0]) * _tpp[0]:9.1f} um, {float(list_status[1]) * _tpp[1]:9.1f} um")

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
        logger.info(f"{MSG} return to the homeposition")
        self.device.query("H:W")
        self.wait(show, rotate)
        logger.info(f"{MSG} reset the axis data")

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
    shot702 = Shot702h(port="ASRL3::INSTR")
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
