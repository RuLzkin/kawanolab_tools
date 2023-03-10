from time import sleep
# from typing import Optional
import numpy as np
import pyvisa
from tqdm import tqdm


class Daq970a():
    """DAQ970A
    """
    device = None
    list_resources = []
    res_man = None

    def __init__(self, ) -> None:
        self.refresh_resources()
        self.connect_device()

        self.device.write("*CLS")
        self.device.write("*RST")

        self.flag_scan_ready = False

    def refresh_resources(self):
        self.res_man = pyvisa.ResourceManager()
        self.list_resources = self.res_man.list_resources()
        # print(self.list_resources)

    def find_device(self):
        num_suggest = None
        for _i, _res in enumerate(self.list_resources):
            try:
                _dev = self.res_man.open_resource(_res)
                _return = _dev.query("*IDN?")
                _dev.close()
            except pyvisa.errors.VisaIOError:
                _return = ""
                print("Could not connect: " + _res)
            if "DAQ970A" in _return:
                num_suggest = _i
        if num_suggest is None:
            raise FileNotFoundError("DAQ970A is not found")
        return num_suggest

    def connect_device(self, num=None):
        if self.res_man is None:
            raise ValueError("ResourceManager is undefined")
        if self.list_resources is None:
            raise ValueError("Resource List is undefined")

        if num is None:
            num = self.find_device()

        self.device = self.res_man.open_resource(self.list_resources[num])

    def query(self, arg):
        _ret = self.device.query(arg)
        return _ret

    def write(self, arg: str):
        self.device.write(arg)

    def set_channel_volt_dc(self, list_channel: list):
        self.list_channel = list_channel
        str_chan = ""
        for _chan in list_channel:
            str_chan += str(_chan) + ","
        self.write("CONF:VOLT:DC (@{0})".format(str_chan[:-1]))
        self.write("ROUTE:SCAN (@{0})".format(str_chan[:-1]))

    def setup_scan(self, count=50, interval=0.1):
        self.scan_count = count
        self.scan_interval = interval
        self.write("FORMAT:READING:CHAN ON")
        self.write("FORMAT:READING:TIME ON")
        self.write("TRIG:COUNT {0}".format(count))
        self.flag_scan_ready = True

    def scan_single_chan(self, verbose=False):
        """scan_single_chan
        return time: ndarray, val: ndarray"""
        if not self.flag_scan_ready:
            return None, None
        self.write("INIT;:SYSTEM:TIME:SCAN?")
        _ret = self.device.read().rstrip()
        if verbose:
            print("SCAN:", _ret)
        points = 0
        points_prev = 0
        with tqdm(total=self.scan_count, leave=False, desc="[SCAN]") as pbar:
            while points < self.scan_count:
                sleep(0.01)
                points = int(self.query("DATA:POINTS?"))
                if points - points_prev > 0:
                    pbar.update(points - points_prev)
                    points_prev = points
        ret = self.query("DATA:REMOVE? {0}".format(self.scan_count)).rstrip()
        if verbose:
            print(ret)
        mat = np.array(ret.split(sep=","), dtype=float).reshape((-1, 3))
        return mat[:, 1], mat[:, 0]  # _t, _val

    def scan_multi_chan(self, verbose=False):
        """scan_single_chan
        return time: ndarray, val: ndarray"""
        if not self.flag_scan_ready:
            return None, None
        self.write("INIT;:SYSTEM:TIME:SCAN?")
        _ret = self.device.read().rstrip()
        if verbose:
            print("SCAN:", _ret)

        self.write("ROUTE:SCAN:SIZE?")
        numberChannels = int(self.query("ROUTE:SCAN:SIZE?"))
        points = 0
        points_prev = 0
        with tqdm(total=self.scan_count * numberChannels, leave=False, desc="[SCAN]") as pbar:
            while points < self.scan_count * numberChannels:
                sleep(0.01)
                points = int(self.query("DATA:POINTS?"))
                # print(points)
                if points - points_prev > 0:
                    pbar.update(points - points_prev)
                    points_prev = points
        ret = self.query("DATA:REMOVE? {0}".format(self.scan_count * numberChannels)).rstrip()
        if verbose:
            print(ret)
        mat = np.array(ret.split(sep=","), dtype=float).reshape((-1, 3))

        list_data = []
        for _chan in range(numberChannels):
            list_data.append([])
        for _i in range(mat.shape[0]):
            for _i_chan, _chan in enumerate(self.list_channel):
                if mat[_i, 2] == _chan:
                    list_data[_i_chan].append([mat[_i, 1], mat[_i, 0]])

        list_mat = []
        for _data in list_data:
            list_mat.append(np.array(_data))

        return list_mat

    def scan_mean_std(self, verbose=False):
        _t, _val = self.scan_single_chan(verbose)
        if _t is None:
            return None, None
        mean = np.mean(_val)
        std = np.std(_val)
        return mean, std

    def close(self):
        if self.device is not None:
            self.device.close()

    def __del__(self):
        self.close()


if __name__ == "__main__":
    from matplotlib import pyplot as plt
    daq = Daq970a()

    print(daq.list_resources)
    # print("*IDN?:", daq.query("*IDN?"))

    list_channel = [_i for _i in range(102, 111)]

    daq.set_channel_volt_dc(list_channel)
    daq.setup_scan(20, 0.1)
    ret = daq.scan_multi_chan()

    plt.figure()
    for _i, _chan in enumerate(list_channel):
        plt.plot(ret[_i][:, 0], ret[_i][:, 1], label="{0}".format(_chan))
    plt.grid()
    plt.legend()
    plt.show()
