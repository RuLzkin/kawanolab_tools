from time import time
import datetime
import numpy as np
import pyvisa
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
    device: keysight_ktdaq970.KtDAQ970 = None
    list_resources = []
    res_man = None
    time_scan = datetime.timedelta(1.0)
    max_range = 1000e-3
    resolution = 0.1e-3
    nplc = 20
    str_chan = "101"

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
        num_suggest = None
        for _i, _res in enumerate(self.list_resources):
            try:
                if "192.168.11." in _res:
                    # I have no idea that the ip address exists.
                    # 31325 is 192.168.10.xxx...
                    raise pyvisa.errors.VisaIOError(0)
                _dev = self.res_man.open_resource(_res)
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

        self.device = keysight_ktdaq970.KtDAQ970(resource_name, id_query, reset, options)

    def configure(self, str_channel=None, sweep_count=None, sec_scan=None, max_range=None, resolution=None, nplc=None):
        """configure

            nplc: 0.02 | 0.2 | 1 | 2 | 10 | 20 | 100 | 200
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
        print("DAQ970Wrapper>> NPLC List>>", self.device.configure.dc_voltage.get_nplc(self.str_chan))

    def measure(self):
        """measure

            usage: mean, std = daq.measure()
        """
        if self.debug:
            return 0, 0
        _scan = self.device.scan.read(self.time_scan)
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

    def close(self):
        if self.device is not None:
            self.device.close()

    def __del__(self):
        self.close()


def oscillo(nmax=100, str_chan="101"):
    from matplotlib import pyplot as plt
    global flag_continue
    global flag_autoscale

    daq = Daq970a()
    daq.configure(str_chan, 5, 1.0, 1000e-3, 0.1e-3)

    test = np.zeros(nmax)
    counts = - np.arange(nmax, 0, -1)
    times = np.ones(nmax) * - 1e-3
    # times = np.zeros(nmax)

    fig, ax = plt.subplots(1, 1, tight_layout=True)
    lines, = ax.plot(counts, test)
    ax.set_ylabel("Voltage [mV]\n(autoscale once: y, continuous: a)")
    ax.set_xlabel("time [sec]")
    ax.grid(True)

    def pressed(event):
        global flag_continue
        global flag_autoscale
        if event.key == "y":
            ax.set_ylim(
                test.min() - 0.1 * (test.max() - test.min()),
                test.max() + 0.1 * (test.max() - test.min()))
            return
        if event.key == "a":
            flag_autoscale = not flag_autoscale
            print("Autoscale:", "On" if flag_autoscale else "Off")
        if event.key == "q":
            flag_continue = False
            return

    fig.canvas.mpl_connect("key_press_event", pressed)
    start = time()
    flag_continue = True
    flag_autoscale = False
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
        ax.set_xlim(times[0], times[-1])
        plt.pause(0.001)


if __name__ == "__main__":

    """Basic Usage"""
    # daq = Daq970a()
    # daq.configure("101", 100, 5.0, 1, 1.0e-3)
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
