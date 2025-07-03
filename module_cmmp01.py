from typing import Optional
import serial
import threading
import time
import numpy as np
from matplotlib import pyplot as plt
from matplotlib.animation import FuncAnimation
from tqdm import trange


class CMMP01():
    device: Optional[serial.Serial] = None
    delay_measure = 0.11  # [sec]

    def __init__(self, str_port: Optional[str] = None) -> None:
        if str_port is None:
            return
        self.connect(str_port)
        self.interval()

        self.measuring = False
        self.raw_data_list = []  # for loop measure
        self.timestamps = []  # for loop measure
        self.frame_count = 0  # for loop measure
        self.max_frames = 10000

    def __del__(self):
        self.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def connect(self, str_port: str):
        self.device = serial.Serial(str_port, 115200, timeout=1)

    def query(self, str_command: str, timeout: float = 1.0):
        if self.device is None:
            raise ValueError("Device is not connected")
        try:
            self.device.write(str_command.encode() + b"\n")
            time.sleep(0.01)
            start_time = time.time()
            while self.device.in_waiting == 0:
                if time.time() - start_time > timeout:
                    raise TimeoutError(f"Query timeout: {str_command}")
                time.sleep(0.001)
            response = self.device.readline()
            return response.decode().rstrip()
        except serial.SerialException as e:
            raise RuntimeError(f"Serial communication error: {e}")

    def close(self):
        if self.device is not None:
            self.device.close()

    def interval(self):
        # You can set the interval time via the hardware switch
        _int = float(self.query("INT?"))
        self.delay_measure = 110 * _int * 1e-6
        return _int

    def datatype(self, str_type: Optional[str] = None):
        if str_type is not None:
            _ret = self.query(f"DATA:Type {str_type}")
            if "OK" not in _ret:
                raise SyntaxError(f"input [{str_type}] is invalid for DATATYPE (, or the connection is invalid)")
        _dt = self.query("DATA:Type?")
        return _dt

    def measure(self):
        try:
            self.query("MEAS")
            time.sleep(self.delay_measure)
            _dat = self.query("DATA?")
            dat = np.array([float(x) for x in _dat[1:-1].split(",")])
            return dat.reshape((10, 10))
        except (ValueError, IndexError) as e:
            raise RuntimeError(f"Measurement failed: {e}")

    def start_measure_loop(self):
        self.raw_data_list.clear()
        self.timestamps.clear()
        self.frame_count = 0
        input("Press Enter key to start measurement")

        self.measuring = True
        self.measurement_thread = threading.Thread(target=self.measure_loop)
        self.measurement_thread.daemon = True
        self.measurement_thread.start()

        self.keyboard_thread = threading.Thread(target=self.wait_for_enter_key)
        self.keyboard_thread.daemon = True
        self.keyboard_thread.start()

        if self.measurement_thread:
            self.measurement_thread.join()

        if hasattr(self, 'keyboard_thread'):
            self.keyboard_thread.join(timeout=1.0)

        return self.process_raw_data()

    def measure_loop(self):
        self.start_time = time.time()
        self.frame_count = 0

        print("Measurement start. Press Enter key to stop")

        last_status_time = time.time()
        status_interval = 1.0

        while self.measuring:
            try:
                current_time = time.time() - self.start_time

                self.query("MEAS")
                time.sleep(self.delay_measure)
                raw_data = self.query("DATA?")

                self.raw_data_list.append(raw_data)
                self.timestamps.append(current_time)
                self.frame_count += 1

                if time.time() - last_status_time > status_interval:
                    print(f"Measuring... Frame: {self.frame_count}, elapsed time: {current_time:.2f} [sec]", end="\r")
                    last_status_time = time.time()

                if self.frame_count >= self.max_frames:
                    print(f"Reached maximum frames {self.max_frames}. Measurement stopped")
                    self.measuring = False
                    break

            except Exception as e:
                print(f"\nMeasurement error: {e}")
                self.measuring = False
                break

    def wait_for_enter_key(self):
        input("")
        self.measuring = False
        print("\nMeasurement stopped")

    def process_raw_data(self) -> tuple[np.ndarray, np.ndarray]:
        frame_count = len(self.raw_data_list)
        data = np.zeros((10, 10, frame_count))

        for _i, raw_data in enumerate(self.raw_data_list):
            _dat = np.array([float(x) for x in raw_data[1:-1].split(",")])
            data[:, :, _i] = _dat.reshape((10, 10))

        return np.array(self.timestamps), data


class RealtimePreview:
    def __init__(self, cmmp_device):
        self.cmmp = cmmp_device
        self.cbar = None

    def start_preview(self):
        _int = self.cmmp.interval()
        print("DATATYPE:", self.cmmp.datatype("Voltage"), "[mV]")
        print("Interval:", _int, "[usec]")

        mat_data = self.cmmp.measure()
        self.fig, self.ax = plt.subplots(figsize=(6, 9))
        plt.tight_layout()

        self.im = self.ax.imshow(mat_data, cmap="viridis", interpolation="nearest", aspect=2.0)
        self.cbar = self.fig.colorbar(self.im, ax=self.ax)
        self.ax.set_title("Realtime measurement")

        def update(frame):
            try:
                mat_data = self.cmmp.measure()
                self.im.set_array(mat_data)
                self.im.set_clim(mat_data.min(), mat_data.max())
                if self.cbar:
                    self.cbar.remove()
                self.cbar = self.fig.colorbar(self.im, ax=self.ax)
                return [self.im]
            except Exception as e:
                print(f"Preview update error: {e}")
                return [self.im]

        _ = FuncAnimation(self.fig, update, interval=_int * 0.2, blit=False)
        plt.show()


def realtime_preview():
    cmmp = CMMP01("COM4")
    preview = RealtimePreview(cmmp)
    preview.start_preview()


def loop_measurement():
    cmmp = CMMP01("COM4")

    _int = cmmp.interval()
    print("DATATYPE:", cmmp.datatype("Voltage"), "[mV]")
    print("Interval:", _int, "[usec]")
    vec_time, data = cmmp.start_measure_loop()
    for _i in trange(len(vec_time)):
        fig, ax = plt.subplots(figsize=(6, 9))
        im = ax.imshow(data[..., _i], vmin=data.min(), vmax=data.max() * 0.7, aspect=2.0)
        _ = fig.colorbar(im, ax=ax)
        ax.set_title(f"Time: {vec_time[_i]:.3f} sec")
        plt.tight_layout()
        fig.savefig(f"data_{_i:04d}.png")
        plt.clf()
        plt.close()


if __name__ == "__main__":

    """normal use"""
    # sg = CMMP01("COM4")
    # _int = sg.interval()
    # print("DATATYPE:", sg.datatype("Voltage"), "[mV]")
    # print("Interval (Each pixel):", _int, "[usec]")
    # mat_data = sg.measure()
    # plt.figure()
    # plt.imshow(mat_data)
    # plt.colorbar()
    # plt.show()

    """Real time preview"""
    realtime_preview()

    """Loop Measurement"""
    # loop_measurement()
