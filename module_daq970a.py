from module_daq970a_visa import (
    Daq970a,
    test_all_raw_data,
    test_elapsed_time)


if __name__ == "__main__":
    name_daq = "USB0::0x2A8D::0x5101::MY58035013::INSTR"
    # name_daq = None
    # Example usage - simple approach for tutorial/learning
    # The destructor will automatically clean up resources if an error occurs
    daq = Daq970a(name_daq)
    daq.configure_volt_dc("AUTO", "DEF", "101", verbose=True)
    mean_vals, std_vals = daq.measure()
    print(f"Mean: {mean_vals}")
    print(f"Std: {std_vals}")
    # Optional: Explicit cleanup (good practice for long-running applications)
    # daq.disconnect()

    # test_elapsed_time(name_daq)
    # test_all_raw_data(name_daq)
