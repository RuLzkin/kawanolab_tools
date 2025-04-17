import re
import warnings
from time import sleep, time
from typing import Union
import numpy as np
import pyvisa
from tqdm.contrib import tenumerate


MSG = "34980AWrapper>>"

"""Basic workflow
ROUT:OPEN:ALL
ROUT:SCAN (@1001:1010)
CONF:VOLT:DC: MIN, MIN, (@1001:1010)
TRIG:SOUR TIM
TRIG:TIM 0.1
TRIG:COUN 10
ROUT:SCAN:SIZE?
READ?
"""


class KS34980A():
    """Keysight 34980A
    """

    device = None
    list_resources = []
    res_man = None

    def __init__(self, name: str = None) -> None:
        self.refresh_resources()
        self.connect_device(name)
        self.write("SYST:BEEP:STAT OFF")

    def refresh_resources(self) -> None:
        self.res_man = pyvisa.ResourceManager()
        self.list_resources = self.res_man.list_resources()

    def connect_device(self, name: str = None) -> None:
        if self.res_man is None:
            raise ValueError(MSG + "ResourceManager is undefined")
        if self.list_resources is None:
            raise ValueError(MSG + "Resource list is undefined")

        if name is not None:
            self.device = self.res_man.open_resource(name)
            self.device.write("*RST")
            sleep(0.5)
            _ret_idn = self.query("*IDN?")
            print(MSG, f"Connected: {name}, *IDN?: {_ret_idn.rstrip()}")
        else:
            pass
        # TODO automatically find and connect a device

    def query(self, command: str, sec_sleep_after: float = None, verbose: bool = False) -> str:
        _ret = self.device.query(command)
        if sec_sleep_after is not None:
            sleep(sec_sleep_after)
        if verbose:
            print(MSG, "SCPI query", command, "-->", _ret)
        return _ret

    def write(self, command: str, verbose=False) -> None:
        self.device.write(command)
        if verbose:
            print(MSG, "SCIP write:", command)

    def configure_volt_dc(
            self, volt_range: Union[float, str] = None, resolution: Union[float, str] = None,
            str_channel: str = None, nplc: Union[float, str] = None, tup_trig_tim_cnt: tuple[float, float] = None,
            ms_timeout: Union[float, str] = None, verbose: bool = False
    ) -> tuple[list[float], list[float], str, float, float]:
        """configure volt DC mode
        Input Args.
            volt_range: 0.1 ~ 10 | "AUTO" | "MIN" | "MAX" | "DEF"
            resolution: {float} | MIN | MAX | DEF
            str_channel: ex) "1001", "1001:1010"
            nplc: 0.02 ~ 200 | MAX | MIN | DEF
            tup_trig_tim_cnt: (interval time [sec], counts)
            ms_timeout: default:5000(?) [millisecond] | "AUTO"

        Output Args.
            list_conf: str, list of the configure of each channel
            list_nplc: float, list of the nplc value of each channel
            Trigger source: str
            Trigger interval time: float
            Trigger counts: float

        About Trigger:
            Apparently, not the
            for _ch in channels:
                for _trig in trigger_counts:
                    measure(_ch, _trig)
            way but the
            for _trig in trigger_counts:
                for _ch in channels:
                    measure(_ch, _trig)
            way they measure.
            If we want to extend the life of the relay,
            it would be better not to use trigger and channels simultaneously.
            In this implementation, the form of the output is reversed,
            as it seems easier to use if the channel is in the list first.
        """

        # ALL CHANNEL DISABLED
        self.write("ROUT:OPEN:ALL")
        # SELECTED CHANNEL ENABLED
        self.write(f"ROUT:SCAN (@{str_channel})")
        # NPLC SET
        _ret_nplc = self.nplc(nplc, str_channel)
        list_nplc = [float(x.strip()) for x in _ret_nplc.split(',')]
        # MODE: DC VOLTAGE, RANGE and RESOLUTION SET
        self.write(f"CONF:VOLT:DC {volt_range} {resolution} (@{str_channel})")
        # TRIGGER SET
        if tup_trig_tim_cnt is not None:
            self.write("TRIG:SOUR TIM")
            self.write(f"TRIG:TIM {tup_trig_tim_cnt[0]}")
            self.write(f"TRIG:COUN {tup_trig_tim_cnt[1]}")
        else:
            self.write("TRIG:SOUR IMM")
        # Applied properties listed
        _ret_conf = self.query(f"CONF? (@{str_channel})")
        list_conf = [x.strip() for x in _ret_conf.split('","')]
        list_mode, list_range, list_resolution = [], [], []
        for _conf in list_conf:
            _mod, _ran, _res = re.split("[, ]", _conf.replace('"', ""))
            list_mode.append(_mod)
            list_range.append(float(_ran))
            list_resolution.append(float(_res))

        # Get Parameters
        _ret_trig_source: str = self.query("TRIG:SOUR?")
        _ret_trig_time: str = self.query("TRIG:TIM?")
        _ret_trig_count: str = self.query("TRIG:COUN?")
        _trig_src = _ret_trig_source.rstrip()
        _tirg_tim = float(_ret_trig_time)
        _trig_cnt = float(_ret_trig_count)
        # TIMEOUT SET
        if ms_timeout is not None:
            # NPLC setting is here to implement AUTO MODE
            _max_time = np.max(list_nplc) / 50 * 50
            self.device.timeout = 1e3 * (_tirg_tim + _max_time + 3) * _trig_cnt if ms_timeout == "AUTO" else ms_timeout
            # Regarding to some experiments, Trigger counts doesn't take much time.
            # Furthermore, measurement time is less than 500ms without outliers(up to 80 channels).
        # VERBOSE
        if verbose:
            print(MSG, f"N_channel:{len(list_conf)}, Trigger(src:{_trig_src}, time:{_tirg_tim:.3f}sec, cnt:{_trig_cnt:.0f})")
            print(MSG, "NPLC      :", list_nplc)
            print(MSG, "MODE      :", list_mode)
            print(MSG, "RANGE     :", list_range)
            print(MSG, "RESOLUTION:", list_resolution)
            print(MSG, "TIMEOUT   :", self.device.timeout)

        if self.device.timeout < _tirg_tim * _trig_cnt:
            warnings.warn(
                "Warning: Timeout duration is less than the estimated measurement time. "
                "Please increase the timeout value or set ms_timeout='AUTO'.")
        return list_conf, list_nplc, _trig_src, _tirg_tim, _trig_cnt

    def nplc(self, value: float = None, str_channel: str = None):
        """nplc setter and getter
        ks34980a.nplc(0.2)
        ks34980a.nplc(0.2, "1001:1010")
        ks34980a.nplc("MAX")
        ks34980a.nplc("MIN")

        I know I didn't have to make this function...
        """
        _cmd = f"VOLT:DC:NPLC {value}"
        _cmd_ret = "VOLT:DC:NPLC?"

        if str_channel is not None:
            if value is not None:
                _cmd += ","
            _cmd += " (@" + str_channel + ")"
            _cmd_ret += " (@" + str_channel + ")"

        if value is not None:
            self.write(_cmd)
        _ret = self.query(_cmd_ret, 0.3)
        # VOLT:DC:NPLC? がどうやら重たいらしいので遅延措置

        return _ret

    def measure(self):
        """measurement

        output: [channel_1, channel_2, channel_3, ...]
            channel_*: np.array([trigger_1, trigger_2, trigger_3, ...])

        ex1) channel:1, count:1
            [array([-0.011979])]
        ex2) channel:2, count:1
            [array([-0.011287]),
             array([-0.008403])]
        ex3) channel:1, count:3
            [array([-0.011282,  0.004047,  0.004213])]
        ex4) channel:2, count:3
            [array([-0.010274, -0.0016  , -0.007252]),
             array([-0.014409,  0.005541, -0.00031 ])]
        """
        num_channel = int(self.query("ROUT:SCAN:SIZE?").rstrip())
        num_trigger = float(self.query("TRIG:COUN?").rstrip())

        str_read = ks34980a.query("READ?")
        vec_read = np.array(str_read.split(","), dtype=float)
        # mat_read = vec_read.reshape((num_channel, int(num_trigger)))
        mat_read = vec_read.reshape((int(num_trigger), num_channel)).T
        list_output = [_row for _row in mat_read]
        return list_output


def test_elapsed_time():
    from matplotlib import pyplot as plt
    num_counts = np.arange(1, 51)
    num_channels = np.arange(1, 81)
    mat_etime = np.zeros((len(num_counts), len(num_channels)))
    for _i, _cnt in tenumerate(num_counts):
        for _j, _chan in tenumerate(num_channels, leave=False):
            start = time()
            ks34980a.configure_volt_dc(
                "AUTO", "DEF", f"1001:{_chan + 1000}",
                nplc=0.02, tup_trig_tim_cnt=(0.01, _cnt), ms_timeout="AUTO", verbose=False)
            mat_etime[_i, _j] = time() - start
    _dchan = (num_channels[1] - num_channels[0]) / 2
    _dcnt = (num_counts[1] - num_counts[0]) / 2
    _extent = [num_channels[0] - _dchan, num_channels[-1] + _dchan, num_counts[-1] + _dcnt, num_counts[0] - _dcnt]
    plt.figure()
    plt.imshow(mat_etime, extent=_extent, aspect=len(num_channels) / len(num_counts))
    plt.xlabel("Number of Channels")
    plt.ylabel("Trigger counts")
    plt.colorbar(label="Elapsed Time [sec]")
    plt.tight_layout()
    plt.show()


def test_all_raw_data():
    from matplotlib import pyplot as plt
    nplc = 1
    time_interval = 0.01

    ks34980a.configure_volt_dc(
        10, "DEF", "1001:1080",
        nplc=nplc, tup_trig_tim_cnt=(time_interval, 20), ms_timeout="AUTO", verbose=True)
    start = time()
    _read = ks34980a.measure()
    # print(MSG, "output:", _read)
    print(MSG, "Elapsed time:", time() - start, "[sec]")

    plt.figure()
    plt.imshow(np.stack(_read).T * 1e3, aspect=2)
    plt.xlabel("Channel")
    plt.ylabel("Triger Counts")
    plt.colorbar(label="Response [mV]")
    plt.title(f"NPLC:{nplc}, Interval:{time_interval * 1e3}[ms]")
    plt.show()


if __name__ == "__main__":
    name_34980a = 'TCPIP0::192.168.10.201::inst0::INSTR'
    ks34980a = KS34980A(name_34980a)
    ks34980a.configure_volt_dc(
        "AUTO", "DEF", "1001")
    _read = ks34980a.measure()
    print(_read)

    # test_elapsed_time()
    # test_all_raw_data()
