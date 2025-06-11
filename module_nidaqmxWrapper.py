import numpy as np
import nidaqmx

system = nidaqmx.system.System.local()  # type:ignore
print(system.driver_version)
print("Devices:")
if len(system.devices) == 0:
    print("--- Nothing")
for device in system.devices:
    print("---", device)


def read_simple(chan="Dev1/ai0", number_of_samples=100, dummy=False):
    if dummy:
        return np.random.rand(number_of_samples)
    with nidaqmx.Task() as task:
        task.ai_channels.add_ai_voltage_chan(chan)
        return task.read(number_of_samples_per_channel=number_of_samples)


class nidaqWrapper():
    def __init__(self, chan="Dev1/ai0", dummy=False) -> None:
        self.dummy = dummy
        if dummy:
            return
        self.task = nidaqmx.Task()
        self.task.ai_channels.add_ai_voltage_chan(chan)

    def start(self):
        if self.dummy:
            return
        self.task.start()

    def stop(self):
        if self.dummy:
            return
        self.task.stop()

    def read(self, number_of_samples):
        if self.dummy:
            return np.random.rand(number_of_samples)
        return self.task.read(number_of_samples_per_channel=number_of_samples)

    def __del__(self):
        if self.dummy:
            return
        self.task.stop()
        self.task.close()


if __name__ == "__main__":
    task = nidaqWrapper(dummy=True)
    # read_simple(dummy=True)
