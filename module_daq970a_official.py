from time import time
import datetime
import numpy as np
import pyvisa
from pyvisa.resources import MessageBasedResource
from typing import cast, Optional
import keysight_ktdaq970


def list_of_channels(str_chan: str):
    list_num = str_chan.split(":")
    if len(list_num) == 1:
        return [int(list_num[0]), ]
    if len(list_num) > 2:
        raise ValueError
    list_channel = []
    for _i in range(int(list_num[0]), int(list_num[1]) + 1):
        list_channel.append(_i)
    return list_channel


class Daq970a():
    """DAQ970A
    """
    device: keysight_ktdaq970.KtDAQ970 = None  # type:ignore
    list_resources = []
    res_man = None
    time_scan = datetime.timedelta(1.0)
    max_range = 1000e-3
    # resolution = 0.1e-3
    resolution = 0.1e-6  # 20NPLC
    nplc = 20
    str_chan = "101"
    str_chan_lamp_switch = "204"
    str_chan_lamp_level = "205"

    def __init__(self, debug=False, verbose=True) -> None:
        self.debug = debug
        if debug:
            return

        self.refresh_resources()
        self.connect_device(None, verbose)
        self.device.system.module.reset_all()
        # print(self.device.utility.error_query())
        self.device.scan.clear_scan_list()
        self.configure("101", 10, 5, 1000e-3, 0.1e-3)

    def refresh_resources(self):
        self.res_man = pyvisa.ResourceManager()
        self.list_resources = self.res_man.list_resources()

    def find_device(self, verbose=True):
        if self.res_man is None:
            raise ValueError("Resource Manager is not initialized")
        num_suggest = None
        for _i, _res in enumerate(self.list_resources):
            try:
                if "192.168.11." in _res:
                    # I have no idea that the ip address exists.
                    # 31325 is 192.168.10.xxx...
                    raise pyvisa.errors.VisaIOError(0)
                _dev = cast(MessageBasedResource, self.res_man.open_resource(_res))
                _return = _dev.query("*IDN?")
                _dev.close()
            except pyvisa.errors.VisaIOError:
                _return = ""
                if verbose:
                    print("DAQ970Wrapper>> " + _res + " : Could not connect")
            if "DAQ970A" in _return:
                num_suggest = _i
                # TODO priority: hislip > inst > gpib
                if verbose:
                    print("DAQ970Wrapper>> " + _res + " : DAQ970A Found")
                break
        if num_suggest is None:
            raise FileNotFoundError("DAQ970Wrapper>> DAQ970A is not found")
        return num_suggest

    def connect_device(self, num=None, verbose=True):
        if self.res_man is None:
            raise ValueError("DAQ970Wrapper>> ResourceManager is undefined")
        if self.list_resources is None:
            raise ValueError("DAQ970Wrapper>> Resource List is undefined")

        if num is None:
            num = self.find_device(verbose)

        resource_name = self.list_resources[num]
        id_query = True
        reset = True
        options = ""

        self.device = keysight_ktdaq970.KtDAQ970(resource_name, id_query, reset, options)  # type:ignore

    def configure(self, str_channel=None, sweep_count=None, sec_scan=None, max_range=None, resolution=None, nplc=None):
        """configure
            max_range = 1000e-3
            resolution = 0.1e-3
            nplc = 20
            str_chan = "101"
            nplc: 0.02 | 0.2 | 1 | 2 | 10 | 20 | 100 | 200

            Integration Time Resolution	Digits Bits
            0.02 PLC	<0.0001 x Range	4 1/2 Digits	15
            0.2 PLC	<0.00001 x Range	5 1/2 Digits	18
            1 PLC (Default)	<0.000003 x Range	5 1/2 Digits	20
            2 PLC	<0.0000022 x Range	6 1/2 Digits	21
            10 PLC	<0.000001 x Range	6 1/2 Digits	24
            20 PLC	<0.0000008 x Range	6 1/2 Digits	25
            100 PLC	<0.0000003 x Range	6 1/2 Digits	26
            200 PLC	<0.00000022 x Range	6 1/2 Digits	26

            Sets the measurement range in volts (0.1 | 1 | 10 | 100 | 300)
            on the specified channelList or current scan list if parameter is empty.
        """
        if self.debug:
            return
        if str_channel is not None:
            self.str_chan = str_channel
        if max_range is not None:
            self.max_range = max_range
        if resolution is not None:
            self.resolution = resolution
        if nplc is not None:
            self.nplc = nplc
        # self.device.configure.dc_voltage.configure_auto(self.str_chan)
        self.device.configure.dc_voltage.configure(self.max_range, self.resolution, self.str_chan)
        self.device.configure.dc_voltage.set_nplc(self.nplc, self.str_chan)
        self.device.scan.format.enable_all()
        if sweep_count is not None:
            self.device.scan.sweep_count = sweep_count
        if sec_scan is not None:
            self.time_scan = datetime.timedelta(sec_scan)
        if nplc is not None:
            print("DAQ970Wrapper>> NPLC List>>", self.device.configure.dc_voltage.get_nplc(self.str_chan))

    def measure(self):
        """measure

            usage: mean, std = daq.measure()
        """
        if self.debug:
            return 0, 0
        _scan = self.device.scan.read(self.time_scan)
        if len(_scan) == 1:
            return _scan[0].reading, 0
        list_channel_set = list_of_channels(self.str_chan)
        list_channel = [[] for _i in list_channel_set]
        for _mea in _scan:
            _idx = list_channel_set.index(_mea.channel)
            list_channel[_idx].append(_mea.reading)
        list_mean = []
        list_std = []
        for _list in list_channel:
            list_mean.append(np.mean(_list))
            list_std.append(np.std(_list))
        if len(list_mean) == 1:
            return list_mean[0], list_std[0]
        return list_mean, list_std

    def lamp_configure(self, str_chan_lamp_switch, str_chan_lamp_level):
        self.str_chan_lamp_switch = str_chan_lamp_switch
        self.str_chan_lamp_level = str_chan_lamp_level

    def lamp_switch(self, is_on: Optional[bool] = None):
        if self.device is None:
            return
        if is_on is None:
            return self.device.configure.digital.get_dac_voltage(self.str_chan_lamp_switch)[0] < 1.0
        _voltage = 0.0 if is_on else 5.0
        self.device.configure.digital.set_dac_voltage(_voltage, self.str_chan_lamp_switch)

    def lamp_level(self, voltage: Optional[float] = None):
        if self.device is None:
            return
        if voltage is None:
            return self.device.configure.digital.get_dac_voltage(self.str_chan_lamp_level)[0]
        if voltage > 5.0:
            raise ValueError("Input Voltage is too high. Please set the voltage between 0V and 5V")
        if voltage < 0.0:
            raise ValueError("Input Voltage is too low. Please set the voltage between 0V and 5V")
        self.device.configure.digital.set_dac_voltage(voltage, self.str_chan_lamp_level)

    def close(self):
        self.lamp_level(0.0)
        self.lamp_switch(False)
        if self.device is not None:
            self.device.close()

    def __del__(self):
        self.close()


def oscillo(nmax=100, str_chan="101", nplc=2):
    from matplotlib import pyplot as plt
    global flag_continue
    global flag_autoscale
    global flag_autoscale_0

    daq = Daq970a()
    daq.configure(str_chan, 1, 0.1, 1000e-3, 0.1e-3, nplc)

    test = np.zeros(nmax)
    counts = - np.arange(nmax, 0, -1)
    # times = np.ones(nmax) * - 1e-3
    times = np.ones(nmax) * np.nan
    # times = np.zeros(nmax)

    fig, ax = plt.subplots(1, 1, tight_layout=True)
    lines, = ax.plot(counts, test)
    ax.set_ylabel(
        "Voltage [mV]\n(autoscale once: y, continuous: a or 0)\nAutoscale: Off")
    ax.set_xlabel("time [sec]")
    ax.grid(True)

    def pressed(event):
        global flag_continue
        global flag_autoscale
        global flag_autoscale_0
        if event.key == "y":
            flag_autoscale_0 = False
            flag_autoscale = False
            ax.set_ylim(
                test.min() - 0.1 * (test.max() - test.min()),
                test.max() + 0.1 * (test.max() - test.min()))
            ax.set_ylabel(
                "Voltage [mV]\n(autoscale once: y, continuous: a or 0)\nAutoscale: Off")
            return
        if event.key == "0":
            flag_autoscale_0 = True
            flag_autoscale = False
            ax.set_ylabel(
                "Voltage [mV]\n(autoscale once: y, continuous: a or 0)\nAutoscale: On (Zero)")
            return
        if event.key == "a":
            flag_autoscale_0 = False
            flag_autoscale = True
            ax.set_ylabel(
                "Voltage [mV]\n(autoscale once: y, continuous: a or 0)\nAutoscale: On")
            return
        if event.key == "q":
            flag_continue = False
            return

    fig.canvas.mpl_connect("key_press_event", pressed)
    start = time()
    flag_continue = True
    flag_autoscale = False
    flag_autoscale_0 = False
    while flag_continue:
        times[0:-1] = times[1:]
        times[-1] = time() - start
        test[0:-1] = test[1:]
        test[-1] = 1000 * daq.measure()[0]
        lines.set_data(times, test)
        if flag_autoscale:
            ax.set_ylim(
                test.min() - 0.1 * (test.max() - test.min()),
                test.max() + 0.1 * (test.max() - test.min()))
        if flag_autoscale_0:
            ax.set_ylim(
                0,
                test.max() * 1.1)
        ax.set_xlim(np.nanmin(times), np.nanmax(times[-1]))
        plt.pause(0.001)


if __name__ == "__main__":

    """Basic Usage"""
    # daq = Daq970a()
    # daq.configure("101", 1, 0.1, 1000e-3, 0.1e-3, 2)
    # print(daq.measure())

    """App: Oscillo"""
    oscillo()

    """Test"""
    # from matplotlib import pyplot as plt
    # _max, _min = 0, 1000
    # start_global = time()
    # last_time = 0
    # list_time = []
    # _list_elapse = []
    # list_data_mean = []
    # list_data_std = []
    # plt.ion()
    # fig, ax1 = plt.subplots(1, 1, tight_layout=True)
    # sc = ax1.scatter(0, 0)
    # line_top, = ax1.plot(0, 0, "gray", alpha=0.3)
    # line_bot, = ax1.plot(0, 0, "gray", alpha=0.3)
    # ax1.set_xlabel("Cumulative elapsed time [min]")
    # ax1.set_ylabel("Time taken to measure [sec]")
    # ax1.grid(True)
    # try:
    #     while True:
    #         start = time()
    #         _mean, _ = daq.measure()
    #         elapse = time() - start
    #         if _max < elapse:
    #             _max = elapse
    #         if _min > elapse:
    #             _min = elapse
    #         min_now = (time() - start_global) / 60
    #         # print("\rglobal time: {0:5.1f} min | elapse: {1:3.4f} sec | max: {2:3.4f} sec | min: {3:3.4f} sec".format(min_now, elapse, _max, _min), end="")
    #         ax1.set_title("now: {0:5.1f} min | elapse: {1:3.4f} sec\nmax: {2:3.4f} sec | min: {3:3.4f} sec".format(min_now, elapse, _max, _min))
    #         _list_elapse.append(elapse)
    #         if min_now > last_time + 1:
    #             last_time = min_now
    #             list_time.append(min_now)
    #             list_data_mean.append(np.mean(_list_elapse))
    #             list_data_std.append(np.std(_list_elapse))
    #             sc.set_offsets(np.c_[list_time, list_data_mean])
    #             line_top.set_xdata(list_time)
    #             line_top.set_ydata(np.array(list_data_mean) + np.array(list_data_std))
    #             line_bot.set_xdata(list_time)
    #             line_bot.set_ydata(np.array(list_data_mean) - np.array(list_data_std))
    #             ax1.set_xlim(0, min_now + 1)
    #             # ax.set_ylim(_min, _max * 1.1)
    #             ax1.set_ylim(0, _max * 1.1)
    #             _list_elapse = []
    #         plt.pause(0.1)
    # except KeyboardInterrupt:
    #     pass
    # plt.ioff()
    # plt.show()
