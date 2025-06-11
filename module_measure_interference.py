from ctypes import windll
import serial.tools.list_ports
from pathlib import Path
import numpy as np
from tqdm import tqdm, trange
import nidaqmx
# import datetime
import matplotlib.pyplot as plt

from module_SynthWrapper import Synth_Wrapper
from module_shot304gs import Shot304gs, Shot_304gs_dummy
# import pandas as pd
# import glob
# import os

SEC_TIMEOUT = 1000

windll.winmm.timeBeginPeriod(1)
LIST_PORTS = list(serial.tools.list_ports.comports())

system = nidaqmx.system.System.local()  # type:ignore
print(system.driver_version)
print("Devices:")
if len(system.devices) == 0:
    print("--- Nothing")
for device in system.devices:
    print("---", device)

print("Ports:")
# print(ports)
for p in LIST_PORTS:
    print("├─port", p)
    print("│ ├─device:       ", p.device)
    print("│ ├─name:         ", p.name)
    print("│ ├─description:  ", p.description)
    print("│ ├─hwid:         ", p.hwid)
    print("│ ├─vid:          ", p.vid)
    print("│ ├─pid:          ", p.pid)
    print("│ ├─serial_number:", p.serial_number)
    print("│ ├─location:     ", p.location)
    print("│ ├─manufacturer: ", p.manufacturer)
    print("│ ├─product:      ", p.product)
    print("│ └─interface:    ", p.interface)


def main_3d(filepath, freq_start, freq_end, freq_tick, dim_step, height_start, height_end, height_tick, number_of_samples, pulse_origin, is_dummy=False):

    if is_dummy:
        synth = Synth_Wrapper(debug=True)
        shot304 = Shot_304gs_dummy()
    else:
        # synth = Synth_Dummy()
        synth = Synth_Wrapper(LIST_PORTS[0].name)
        shot304 = Shot304gs()

    vec_height1 = np.arange(height_start[0], height_end[0] + 1e-3, height_tick[0]).astype(int)
    vec_height2 = np.arange(height_start[1], height_end[1] + 1e-3, height_tick[1]).astype(int)
    vec_height3 = np.arange(height_start[2], height_end[2] + 1e-3, height_tick[2]).astype(int)

    list_height = [vec_height1, vec_height2, vec_height3]
    vec_freq = np.arange(freq_start, freq_end + 1e-3, freq_tick)

    shot304.homeposition()

    list_pulse = pulse_origin
    list_pulse[dim_step[0]] = vec_height1[0]
    list_pulse[dim_step[1]] = vec_height2[0]
    list_pulse[dim_step[2]] = vec_height3[0]
    shot304.wait()
    shot304.move_abs(list_pulse)

    list_index = []
    list_step = []
    _list_index1 = [i for i in range(len(vec_height1))]
    _list_index2 = [i for i in range(len(vec_height2))]
    _list_index3 = [i for i in range(len(vec_height3))]
    _rev_2 = False
    _rev_3 = False

    for _ind_1, _step_1 in zip(_list_index1, vec_height1):
        _list2_ind = reversed(_list_index2) if _rev_2 else _list_index2
        _list2_hei = reversed(vec_height2) if _rev_2 else vec_height2
        _rev_2 = not _rev_2
        for _ind_2, _step_2 in zip(_list2_ind, _list2_hei):
            _list3_ind = reversed(_list_index3) if _rev_3 else _list_index3
            _list3_hei = reversed(vec_height3) if _rev_3 else vec_height3
            _rev_3 = not _rev_3
            for _ind_3, _step_3 in zip(_list3_ind, _list3_hei):
                list_step.append([_step_1, _step_2, _step_3])
                list_index.append([_ind_1, _ind_2, _ind_3])

    shape_data = (len(vec_height1), len(vec_height2), len(vec_height3), len(vec_freq))
    data: np.ndarray = np.zeros(shape_data, dtype=float)

    data[:] = np.nan

    cnt_save = 0
    thres_save = 100

    plt.ion()
    fig, ax = plt.subplots(1, 1)
    img = ax.imshow(np.zeros((len(vec_height1), len(vec_height2))))
    cbar = fig.colorbar(img)
    for _index in trange(len(list_index)):
        list_pulse = pulse_origin
        list_pulse[dim_step[0]] = list_step[_index][0]
        list_pulse[dim_step[1]] = list_step[_index][1]
        list_pulse[dim_step[2]] = list_step[_index][2]

        shot304.wait()
        shot304.move_abs(list_pulse)

        for _i_freq, _freq in enumerate(tqdm(vec_freq, leave=False)):
            synth.on(power=15, frequency=_freq)
            if is_dummy:
                _voltage = np.random.rand(number_of_samples)
            else:
                with nidaqmx.Task() as task:
                    task.ai_channels.add_ai_voltage_chan("Dev1/ai0")
                    _voltage = task.read(number_of_samples_per_channel=number_of_samples)
            data[list_index[_index][0], list_index[_index][1], list_index[_index][2], _i_freq] = np.mean(_voltage)

            plt.pause(0.001)

            synth.off()
        plt.cla()
        cbar.remove()
        _data = data.squeeze()
        while True:
            if len(_data.shape) < 3:
                break
            _data = np.nanmean(_data, axis=-1)
        img = ax.imshow(_data.squeeze())
        cbar = fig.colorbar(img)
        if cnt_save > thres_save / len(vec_freq):
            np.savez(
                filepath,
                height=np.array(list_height, dtype=object),
                freq=vec_freq,
                data=data,
                dim_step=dim_step,
                number_of_samples=number_of_samples)
            cnt_save = 0
        else:
            cnt_save += 1
    plt.ioff()
    shot304.homeposition()
    shot304.set_NumberOfDivisions([2, 2, 2, 2])

    np.savez(
        Path(filepath).as_posix() + "_complete",
        height=np.array(list_height, dtype=object),
        freq=vec_freq,
        data=data,
        dim_step=dim_step,
        number_of_samples=number_of_samples
    )
    fig.savefig(Path(filepath).as_posix() + ".png")
    return list_height, vec_freq, data


if __name__ == "__main__":
    # これでいい感じに見れた↓
    # freq_start = 7.5e9
    # freq_end = 24.0e9
    # freq_tick = 100e6  # 10e6
    # height_start = 0
    # height_end = 85000
    # height_tick = 1000
    freq_start = 7.5e9
    freq_end = 24.0e9
    freq_tick = 100e6  # 10e6

    height_start = (0, 30000)
    height_end = (80000, 50000)
    height_tick = (10000, 2500)

    dim_step = (1, 2)

    number_of_samples = 200

    pulse_origin = [17500, 40000, 40000, 0]
    # height, freq, mat_data = main_2d(
    #     "data_20220706_focus_SD_2_1",
    #     freq_start, freq_end, freq_tick, dim_step,
    #     height_start, height_end, height_tick,
    #     number_of_samples, pulse_origin)

    # plt.figure()
    # plt.imshow(mat_data)
    # plt.colorbar()
    # plt.show()
