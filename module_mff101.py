from typing import List, Union
import warnings
import random
from pylablib.devices import Thorlabs

"""
MFF101:
    RT:
        0: Transmittance
        1: Reflectance
    M1:
        0: On
        1: Off
    M2:
        0: On
        1: Off
    [0, 1, 1] = Transmittance, beam A
    [0, 0, 1] = Transmittance, beam B
    [0, 1, 0] = Transmittance, beam C
"""

SERIALNUMBER_RT = "37008835"
SERIALNUMBER_M1 = "37008924"
SERIALNUMBER_M2 = "37009004"

warnings.filterwarnings('ignore', message="model number .* doesn't match")

State_MFF = Union[int, bool, None]

class MFF101():
    def __init__(self, serial_number: str):
        self.flipper = Thorlabs.kinesis.MFF(serial_number)

    def __del__(self):
        self.flipper.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.__del__()

    def wait(self):
        self.flipper.wait_for_status("moving_bk", False)

    def get_state(self):
        return self.flipper.get_state()

    def move_to_state(self, state: State_MFF):
        if state is None:
            return
        self.wait()
        if state is True:
            state = 1
        elif state is False:
            state = 0
        self.flipper.move_to_state(state)

    def show_status(self):
        print(self.flipper.get_device_info())
        print(self.flipper.get_status())
        print(self.flipper.get_state())


def sync_move(flippers: List[MFF101], states: List[State_MFF]):
    sync_wait(flippers)
    for flip, stat in zip(flippers, states):
        flip.move_to_state(stat)

def sync_wait(flippers: List[MFF101]):
    for flip in flippers:
        flip.wait()


if __name__ == "__main__":
    flipper1  = MFF101(SERIALNUMBER_RT)
    flipper2  = MFF101(SERIALNUMBER_M1)
    flipper3  = MFF101(SERIALNUMBER_M2)

    # flipper1.show_status()
    # flipper1.move_to_state(0)
    # flipper1.move_to_state(1)

    try:
        sync_move([flipper1, flipper2, flipper3], [0, 0, 0])
        sync_move([flipper1, flipper2, flipper3], [1, 1, 1])
        # while True:
        #     random.choices([True, False, None], k=3)
        #     sync_move(
        #         [flipper1, flipper2, flipper3],
        #         random.choices([True, False, None], k=3))
        #     # sync_move([flipper1, flipper2, flipper3], [0, 0, 0])
        #     # sync_move([flipper1, flipper2, flipper3], [1, 1, 1])
    except KeyboardInterrupt:
        del flipper1
        del flipper2
        del flipper3
