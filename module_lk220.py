from typing import cast
from time import sleep
import logging
from pyvisa import ResourceManager
from pyvisa.resources import SerialInstrument
from pyvisa.constants import StopBits, Parity, ControlFlow, BufferOperation


LOG_HEADER = "LK220>>"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LK220():
    def __init__(self, port: str, name: str = "LK220") -> None:
        self.res_man = ResourceManager()
        self.device = cast(SerialInstrument, self.res_man.open_resource(port))

        self.device.baud_rate = 115200
        self.device.data_bits = 8
        self.device.parity = Parity.none
        self.device.stop_bits = StopBits.one
        self.device.flow_control = ControlFlow.none
        self.device.timeout = 5000  # ms
        self.device.read_termination = '\r'
        self.device.write_termination = '\r'
        self.log_header = f"{name}>>"
        sleep(0.1)
        self.test_connection()

    def __del__(self):
        if self.device is not None:
            self.device.close()
            self.device = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if self.device is not None:
            self.device.close()
            self.device = None

    def info(self, message: str, r: bool = False):
        if r:
            logger.info(f"\r{self.log_header} {message}")
        else:
            logger.info(f"{self.log_header} {message}")

    def query(self, command: str, ms_wait: int = 10, verbose: bool = False) -> str:
        assert self.device is not None
        self.device.flush(BufferOperation.discard_read_buffer)
        self.device.write(command)
        sleep(ms_wait / 1000.0)
        lines = []
        while True:
            try:
                line = self.device.read().strip()
                if not line:
                    break
                lines.append(line)
                if line.endswith('>'):
                    break
            except:
                break
        if lines and lines[-1] == '>':
            lines.pop()
        if verbose:
            self.info(f"Query: {command} -> Response: {lines}")
        return '\n'.join(lines).strip()

    def test_connection(self) -> None:
        _ret = self.query("IDN?").rstrip()
        if "LK220" not in _ret:
            raise ValueError(f"Invalid device response: {_ret}")
        self.info(f"Connected to device: {_ret}")

    def get_target_temperature(self) -> float:
        _ret = self.query("TSET?")
        return float(_ret)

    def get_actual_temperature(self) -> float:
        _ret = self.query("TACT?")
        return float(_ret)

    def set_target_temperature(self, temp: float):
        if not (-5.0 <= temp <= 45.0):
            raise ValueError("Temperature out of range (-5.0 to 45.0 °C)")
        n_temp = int(temp * 10)
        self.query(f"TSET={n_temp:d}")

    def get_state_code(self, verbose: bool = False) -> tuple[int, dict]:
        """
        Returns:
        code: 二桁の10進数（十の位=運転状態, 一の位=健全度）
            十の位:
                0: 待機中
                1: 加熱中
                2: 冷却中
                9: 矛盾/不明
            一の位:
                0: 正常
                1: 警告
                2: エラー

        info: 各ビットや解釈を含む辞書
        """
        raw = self.query("ST?").strip()
        # ST? は 8bit値（0..255）を返す想定
        try:
            val = int(raw, 16)
        except ValueError:
            # まれに余計な行が混じる場合は最後の行を採用
            lines = [s for s in raw.splitlines() if s.strip()]
            val = int(lines[-1], 16)

        standby = bool(val & (1 << 0))
        heating = bool(val & (1 << 1))
        cooling = bool(val & (1 << 2))
        warn    = bool(val & (1 << 3))
        error   = bool(val & (1 << 4))

        # 十の位（運転状態）
        main_bits = [standby, heating, cooling]
        if sum(main_bits) == 1:
            if standby: main = 0
            elif heating: main = 1
            else: main = 2
        else:
            main = 9  # 矛盾/不明

        # 一の位（健全度）
        if error:
            health = 2
        elif warn:
            health = 1
        else:
            health = 0

        code = main * 10 + health
        info = {
            "raw": val,
            "standby": standby,
            "heating": heating,
            "cooling": cooling,
            "warning": warn,
            "error": error,
            "main_state": main,   # 0/1/2/9
            "health": health,     # 0/1/2
        }

        if verbose:
            logger.info(f"State code: {code}, Info: {info}")
        return code, info

    def get_running(self) -> int:
        code, _ = self.get_state_code()
        code = code // 10
        if code == 0:
            return 0  # 待機中
        elif code == 9:
            return -1  # 矛盾/不明
        else:
            return 1  # 運転中

    def set_run(self, run: bool, verbose: bool = False) -> None:
        str_run = "1" if run else "0"
        self.query(f"EN={str_run}")
        if verbose:
            self.info(f"{"RUN" if run else "STOP"}")
        sleep(0.5)

    def get_window(self, verbose: bool = False) -> float:
        _ret = self.query("WINDOW?")
        if verbose:
            self.info(f"Window settings: {_ret}")
        return float(_ret)

    def wait_until_steady(self, sec_check_interval: float = 5.0, verbose: bool = False) -> None:
        self.info(f"Waiting for the temperature to become steady...")
        _set = self.get_target_temperature()
        _window = self.get_window()
        if verbose: print("")
        while True:
            code, info = self.get_state_code()
            _act = self.get_actual_temperature()

            if verbose: print(f"\r{self.log_header} ACT/SET: {_act:6.2f}/{_set:5.1f}, CODE: {code}", end="")

            # if not info["warning"]:  # waring based
            #     break
            if _act< _set + _window:  # temp based (fuzzy for cooling)
                break

            sleep(sec_check_interval)
        if verbose: self.info(f"ACT/SET: {_act:6.2f}/{_set:5.1f}, CODE: {code}", r=True)
        self.info(f"The temperature is steady now.")

def test_control_temperature(port: str):
        import numpy as np
        from matplotlib import pyplot as plt
        from time import time

        target_temp = 15.0
        list_time = []
        list_temp = []
        list_standby = []
        list_heating = []
        list_cooling = []
        list_warning = []


        with LK220(port) as lk220:
            target_temp_old = lk220.get_target_temperature()
            try:
                lk220.set_target_temperature(target_temp)
                lk220.set_run(True)
                _start = time()
                _end = -1
                _flag = False
                while True:
                    list_time.append(time() - _start)
                    list_temp.append(lk220.get_actual_temperature())
                    _, _info = lk220.get_state_code()
                    list_standby.append(1 if _info["standby"] else 0)
                    list_heating.append(1 if _info["heating"] else 0)
                    list_cooling.append(1 if _info["cooling"] else 0)
                    list_warning.append(1 if _info["warning"] else 0)
                    if not _flag and list_temp[-1] < target_temp + 0.5:
                        _end = time()
                        _flag = True
                        print("Reached target temperature. Starting 10s timer...")
                    if _flag and time() > _end + 10:
                        print("!!")
                        break
                    print(f"\r{list_temp[-1]:6.2f}, {time() - _start:7.2f}", end="")
                    sleep(2.0)
            finally:
                lk220.set_run(False)
                lk220.set_target_temperature(target_temp_old)

        vec_time = np.array(list_time)
        vec_temp = np.array(list_temp)
        vec_standby = np.array(list_standby)
        vec_heating = np.array(list_heating)
        vec_cooling = np.array(list_cooling)
        vec_warning = np.array(list_warning)
        plt.figure()
        plt.plot(vec_time, vec_temp, label="Act.Temp.")
        plt.plot(vec_time, vec_standby * (vec_temp.max() - vec_temp.min() + 1) + vec_temp.min() - 1, label="Standby")
        plt.plot(vec_time, vec_heating * (vec_temp.max() - vec_temp.min() + 1) + vec_temp.min() - 1, label="Heating")
        plt.plot(vec_time, vec_cooling * (vec_temp.max() - vec_temp.min() + 1) + vec_temp.min() - 1, label="Cooling")
        plt.plot(vec_time, vec_warning * (vec_temp.max() - vec_temp.min() + 1) + vec_temp.min() - 1, label="Warning")
        plt.legend()
        plt.grid()
        plt.show()


if __name__ == "__main__":

    # test_control_temperature("COM10")

    # with LK220("COM10") as lk220:
    #     target_temp = lk220.get_target_temperature()
    #     actual_temp = lk220.get_actual_temperature()
    #     print(f"Temperature -- Target: {target_temp:6.2f} degC, Actual: {actual_temp:5.1f} degC")
    #     lk220.get_state_code(verbose=True)

    with (
        LK220("COM12") as lk220A,
        LK220("COM11") as lk220B,
        LK220("COM10") as lk220C,
    ):
        lk220A.get_state_code(verbose=True)
        _tar = lk220A.get_target_temperature()
        _act = lk220A.get_actual_temperature()
        print(f"{_tar} degC (target), {_act} degC (actual)")
        lk220B.get_state_code(verbose=True)
        _tar = lk220B.get_target_temperature()
        _act = lk220B.get_actual_temperature()
        print(f"{_tar} degC (target), {_act} degC (actual)")
        lk220C.get_state_code(verbose=True)
        _tar = lk220C.get_target_temperature()
        _act = lk220C.get_actual_temperature()
        print(f"{_tar} degC (target), {_act} degC (actual)")
