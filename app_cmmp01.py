import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import os
import csv
from datetime import datetime
import numpy as np
import cv2
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import serial.tools.list_ports
from module_cmmp01 import CMMP01


class CMMP01GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("CMMP01 Camera Control")
        self.root.geometry("1200x800")

        # Device and measurement variables
        self.cmmp = None
        self.is_connected = False
        self.is_previewing = False
        self.is_recording = False
        self.preview_thread = None
        self.recording_thread = None
        self.recording_data = []
        self.recording_timestamps = []
        self.recording_start_time = None
        self.recording_duration = 0  # 0 means no limit

        # Settings
        self.save_folder = tk.StringVar(value=os.getcwd())
        self.auto_naming = tk.BooleanVar(value=True)
        self.colormap = tk.StringVar(value="viridis")
        self.vmin_auto = tk.BooleanVar(value=True)
        self.vmax_auto = tk.BooleanVar(value=True)
        self.vmin_manual = tk.DoubleVar(value=0.0)
        self.vmax_manual = tk.DoubleVar(value=1.0)
        self.show_values = tk.BooleanVar(value=False)
        self.recording_duration_var = tk.IntVar(value=0)  # seconds, 0 = no limit

        # UI State
        self.settings_visible = tk.BooleanVar(value=True)

        self.create_widgets()
        self.update_port_list()

    def create_widgets(self):
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left panel for controls
        self.left_panel = ttk.Frame(main_frame)
        self.left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # Settings toggle button
        toggle_frame = ttk.Frame(self.left_panel)
        toggle_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(
            toggle_frame, text="Hide Settings",
            command=self.toggle_settings).pack()

        # Settings panel
        self.settings_panel = ttk.LabelFrame(self.left_panel, text="Settings")
        self.settings_panel.pack(fill=tk.X, pady=(0, 10))

        self.create_connection_controls()
        self.create_measurement_controls()
        self.create_save_controls()
        self.create_display_controls()

        # Control buttons
        self.create_control_buttons()

        # Right panel for preview
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Preview area
        self.create_preview_area(right_panel)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var,
            relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def create_connection_controls(self):
        conn_frame = ttk.LabelFrame(self.settings_panel, text="Connection")
        conn_frame.pack(fill=tk.X, pady=5)

        # Port selection
        ttk.Label(conn_frame, text="Port:").pack(anchor=tk.W)
        port_frame = ttk.Frame(conn_frame)
        port_frame.pack(fill=tk.X, pady=2)

        self.port_var = tk.StringVar()
        self.port_combo = ttk.Combobox(
            port_frame, textvariable=self.port_var,
            width=15)
        self.port_combo.pack(side=tk.LEFT, padx=(0, 5))

        ttk.Button(
            port_frame, text="Refresh",
            command=self.update_port_list).pack(side=tk.LEFT, padx=(0, 5))

        # Connection button
        self.connect_btn = ttk.Button(
            conn_frame, text="Connect",
            command=self.toggle_connection)
        self.connect_btn.pack(pady=5)

        # Connection status
        self.conn_status = ttk.Label(
            conn_frame, text="Disconnected",
            foreground="red")
        self.conn_status.pack()

    def create_measurement_controls(self):
        meas_frame = ttk.LabelFrame(self.settings_panel, text="Measurement")
        meas_frame.pack(fill=tk.X, pady=5)

        # Data type (read-only after connection)
        ttk.Label(meas_frame, text="Data Type:").pack(anchor=tk.W)
        self.datatype_var = tk.StringVar(value="Voltage")
        datatype_combo = ttk.Combobox(
            meas_frame, textvariable=self.datatype_var,
            values=["Voltage", "Digital"], width=15)
        datatype_combo.pack(pady=2)

        # Interval (read-only)
        ttk.Label(meas_frame, text="Interval:").pack(anchor=tk.W)
        self.interval_var = tk.StringVar(value="N/A")
        interval_label = ttk.Label(meas_frame, textvariable=self.interval_var)
        interval_label.pack()

        # Recording duration
        ttk.Label(meas_frame, text="Recording Duration (sec, 0=unlimited):").pack(anchor=tk.W)
        duration_spin = ttk.Spinbox(
            meas_frame, from_=0, to=3600,
            textvariable=self.recording_duration_var, width=15)
        duration_spin.pack(pady=2)

    def create_save_controls(self):
        save_frame = ttk.LabelFrame(self.settings_panel, text="Save Settings")
        save_frame.pack(fill=tk.X, pady=5)

        # Save folder
        ttk.Label(save_frame, text="Save Folder:").pack(anchor=tk.W)
        folder_frame = ttk.Frame(save_frame)
        folder_frame.pack(fill=tk.X, pady=2)

        folder_entry = ttk.Entry(
            folder_frame, textvariable=self.save_folder,
            width=20)
        folder_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        ttk.Button(
            folder_frame, text="Browse",
            command=self.browse_folder).pack(side=tk.LEFT)

        # Auto naming
        ttk.Checkbutton(
            save_frame, text="Auto naming (timestamp)",
            variable=self.auto_naming).pack(anchor=tk.W, pady=2)

    def create_display_controls(self):
        display_frame = ttk.LabelFrame(self.settings_panel, text="Display Settings")
        display_frame.pack(fill=tk.X, pady=5)

        # Colormap
        ttk.Label(display_frame, text="Colormap:").pack(anchor=tk.W)
        colormap_combo = ttk.Combobox(
            display_frame, textvariable=self.colormap,
            values=[
                "viridis", "plasma", "inferno", "magma",
                "hot", "cool", "gray", "jet"], width=15)
        colormap_combo.pack(pady=2)
        colormap_combo.bind('<<ComboboxSelected>>', self.update_colormap)

        # vmin/vmax controls
        ttk.Checkbutton(
            display_frame, text="Auto vmin",
            variable=self.vmin_auto).pack(anchor=tk.W)

        vmin_frame = ttk.Frame(display_frame)
        vmin_frame.pack(fill=tk.X, pady=2)
        ttk.Label(vmin_frame, text="vmin:").pack(side=tk.LEFT)
        vmin_spin = ttk.Spinbox(
            vmin_frame, from_=-1000, to=1000, increment=0.1,
            textvariable=self.vmin_manual, width=10)
        vmin_spin.pack(side=tk.LEFT, padx=(5, 0))

        ttk.Checkbutton(
            display_frame, text="Auto vmax",
            variable=self.vmax_auto).pack(anchor=tk.W)

        vmax_frame = ttk.Frame(display_frame)
        vmax_frame.pack(fill=tk.X, pady=2)
        ttk.Label(vmax_frame, text="vmax:").pack(side=tk.LEFT)
        vmax_spin = ttk.Spinbox(
            vmax_frame, from_=-1000, to=1000, increment=0.1,
            textvariable=self.vmax_manual, width=10)
        vmax_spin.pack(side=tk.LEFT, padx=(5, 0))

        # Show values
        ttk.Checkbutton(
            display_frame, text="Show values on hover",
            variable=self.show_values).pack(anchor=tk.W, pady=2)

    def create_control_buttons(self):
        control_frame = ttk.LabelFrame(self.left_panel, text="Controls")
        control_frame.pack(fill=tk.X, pady=5)

        # Preview button
        self.preview_btn = ttk.Button(
            control_frame, text="Start Preview",
            command=self.toggle_preview, state=tk.DISABLED)
        self.preview_btn.pack(fill=tk.X, pady=2)

        # Capture button
        self.capture_btn = ttk.Button(
            control_frame, text="Capture Image",
            command=self.capture_image, state=tk.DISABLED)
        self.capture_btn.pack(fill=tk.X, pady=2)

        # Record button
        self.record_btn = ttk.Button(
            control_frame, text="Start Recording",
            command=self.toggle_recording, state=tk.DISABLED)
        self.record_btn.pack(fill=tk.X, pady=2)

        # Recording status
        self.record_status = ttk.Label(control_frame, text="", foreground="red")
        self.record_status.pack()

    def create_preview_area(self, parent):
        preview_frame = ttk.LabelFrame(parent, text="Preview")
        preview_frame.pack(fill=tk.BOTH, expand=True)

        # Create matplotlib figure with GridSpec
        self.fig = Figure(figsize=(8, 6), dpi=100)
        gs = gridspec.GridSpec(1, 2, figure=self.fig, width_ratios=[4, 0.2], wspace=0.05)

        # Main plot
        self.ax = self.fig.add_subplot(gs[0, 0])

        # Colorbar axes
        self.cbar_ax = self.fig.add_subplot(gs[0, 1])

        # Initialize with empty plot
        self.current_data = np.zeros((10, 10))
        self.im = self.ax.imshow(
            self.current_data, cmap=self.colormap.get(),
            interpolation='nearest', aspect=2.0)

        # Create colorbar
        self.cbar = self.fig.colorbar(self.im, cax=self.cbar_ax)
        self.ax.set_title("No Data")

        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, preview_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        # Mouse hover for value display
        self.canvas.mpl_connect('motion_notify_event', self.on_mouse_move)
        self.canvas.mpl_connect('axes_leave_event', self.on_mouse_leave)

        # Store last hover info to prevent flickering
        self.last_hover_info = None

    def update_port_list(self):
        ports = [port.device for port in serial.tools.list_ports.comports()]
        self.port_combo['values'] = ports
        if ports:
            self.port_combo.set(ports[0])

    def toggle_connection(self):
        if not self.is_connected:
            self.connect_device()
        else:
            self.disconnect_device()

    def connect_device(self):
        try:
            port = self.port_var.get()
            if not port:
                messagebox.showerror("Error", "Please select a port")
                return

            self.cmmp = CMMP01(port)

            # Set datatype
            self.cmmp.datatype(self.datatype_var.get())

            # Get interval
            interval = self.cmmp.interval()
            self.interval_var.set(f"{interval} µsec")

            self.is_connected = True
            self.connect_btn.config(text="Disconnect")
            self.conn_status.config(text="Connected", foreground="green")

            # Enable controls
            self.preview_btn.config(state=tk.NORMAL)
            self.capture_btn.config(state=tk.NORMAL)
            self.record_btn.config(state=tk.NORMAL)

            self.status_var.set(f"Connected to {port}")

        except Exception as e:
            messagebox.showerror("Connection Error", f"Failed to connect: {str(e)}")

    def disconnect_device(self):
        if self.is_previewing:
            self.stop_preview()
        if self.is_recording:
            self.stop_recording()

        if self.cmmp:
            self.cmmp.close()
            self.cmmp = None

        self.is_connected = False
        self.connect_btn.config(text="Connect")
        self.conn_status.config(text="Disconnected", foreground="red")

        # Disable controls
        self.preview_btn.config(state=tk.DISABLED)
        self.capture_btn.config(state=tk.DISABLED)
        self.record_btn.config(state=tk.DISABLED)

        self.status_var.set("Disconnected")

    def toggle_preview(self):
        if not self.is_previewing:
            self.start_preview()
        else:
            self.stop_preview()

    def start_preview(self):
        if not self.is_connected:
            return

        self.is_previewing = True
        self.preview_btn.config(text="Stop Preview")
        self.preview_thread = threading.Thread(target=self.preview_loop)
        self.preview_thread.daemon = True
        self.preview_thread.start()

    def stop_preview(self):
        self.is_previewing = False
        self.preview_btn.config(text="Start Preview")

    def preview_loop(self):
        while self.is_previewing:
            try:
                assert self.cmmp
                data = self.cmmp.measure()
                self.root.after(0, self.update_preview, data)
                time.sleep(0.1)
            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Preview error: {str(e)}"))
                break

    def update_preview(self, data):
        if not self.is_previewing:
            return

        # Store current data for mouse hover
        self.current_data = data

        self.im.set_array(data)

        # Update colormap
        self.im.set_cmap(self.colormap.get())

        # Update vmin/vmax
        if self.vmin_auto.get():
            vmin = data.min()
        else:
            vmin = self.vmin_manual.get()

        if self.vmax_auto.get():
            vmax = data.max()
        else:
            vmax = self.vmax_manual.get()

        self.im.set_clim(vmin, vmax)

        # Update colorbar
        self.cbar.update_normal(self.im)

        # Update title (keep last hover info if available)
        if self.last_hover_info and self.show_values.get():
            x, y, value = self.last_hover_info
            unit = "mV" if self.datatype_var.get() == "Voltage" else "LSB"
            self.ax.set_title(f"Live Preview - {self.datatype_var.get()} | Pixel ({x}, {y}): {value:.2f} {unit}")
        else:
            self.ax.set_title(f"Live Preview - {self.datatype_var.get()}")

        self.canvas.draw_idle()

    def update_colormap(self, event=None):
        if hasattr(self, 'im'):
            self.im.set_cmap(self.colormap.get())
            self.canvas.draw()

    def capture_image(self):
        if not self.is_connected:
            return

        try:
            assert self.cmmp
            data = self.cmmp.measure()
            self.save_data(data, is_single=True)
            self.status_var.set("Image captured")
        except Exception as e:
            messagebox.showerror("Capture Error", f"Failed to capture: {str(e)}")

    def toggle_recording(self):
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()

    def start_recording(self):
        if not self.is_connected:
            return

        self.is_recording = True
        self.record_btn.config(text="Stop Recording")
        self.record_status.config(text="Recording...")

        self.recording_data = []
        self.recording_timestamps = []
        self.recording_start_time = time.time()

        self.recording_thread = threading.Thread(target=self.recording_loop)
        self.recording_thread.daemon = True
        self.recording_thread.start()

    def stop_recording(self):
        self.is_recording = False
        self.record_btn.config(text="Start Recording")
        self.record_status.config(text="")

        if self.recording_data:
            self.save_recording()

    def recording_loop(self):
        while self.is_recording:
            try:
                assert self.cmmp
                assert self.recording_start_time is not None
                data = self.cmmp.measure()
                current_time = time.time() - self.recording_start_time

                self.recording_data.append(data)
                self.recording_timestamps.append(current_time)

                # Check duration limit
                if (self.recording_duration_var.get() > 0 and current_time >= self.recording_duration_var.get()):
                    self.root.after(0, self.stop_recording)
                    break

                self.root.after(0, lambda: self.record_status.config(
                    text=f"Recording... {len(self.recording_data)} frames, {current_time:.1f}s"))

                time.sleep(0.1)

            except Exception as e:
                self.root.after(0, lambda: self.status_var.set(f"Recording error: {str(e)}"))
                break

    def save_recording(self):
        if not self.recording_data:
            return

        try:
            # Convert to numpy array
            data_array = np.array(self.recording_data)
            timestamps = np.array(self.recording_timestamps)

            # Get filename
            if self.auto_naming.get():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                base_filename = f"recording_{timestamp}"
            else:
                base_filename = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
                )
                if not base_filename:
                    return
                base_filename = os.path.splitext(base_filename)[0]

            folder = self.save_folder.get()

            # Save individual frames as PNG
            for i, data in enumerate(self.recording_data):
                filename = os.path.join(folder, f"{base_filename}_frame_{i:04d}.png")
                self.save_image(data, filename)

            # Save as CSV
            csv_filename = os.path.join(folder, f"{base_filename}_data.csv")
            self.save_csv(data_array, timestamps, csv_filename)

            # Create video (optional)
            self.create_video(base_filename, folder)

            self.status_var.set(f"Recording saved: {len(self.recording_data)} frames")

        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save recording: {str(e)}")

    def save_data(self, data, is_single=False):
        try:
            # Get filename
            if self.auto_naming.get():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                if is_single:
                    base_filename = f"capture_{timestamp}"
                else:
                    base_filename = f"recording_{timestamp}"
            else:
                base_filename = filedialog.asksaveasfilename(
                    defaultextension=".png",
                    filetypes=[("PNG files", "*.png"), ("All files", "*.*")]
                )
                if not base_filename:
                    return
                base_filename = os.path.splitext(base_filename)[0]

            folder = self.save_folder.get()

            # Save PNG
            png_filename = os.path.join(folder, f"{base_filename}.png")
            self.save_image(data, png_filename)

            # Save CSV
            csv_filename = os.path.join(folder, f"{base_filename}.csv")
            with open(csv_filename, 'w', newline='') as csvfile:
                writer = csv.writer(csvfile)
                for row in data:
                    writer.writerow(row)

        except Exception as e:
            messagebox.showerror("Save Error", f"Failed to save data: {str(e)}")

    def save_image(self, data, filename):
        fig = plt.figure(figsize=(8, 6))
        gs = gridspec.GridSpec(1, 2, figure=fig, width_ratios=[4, 0.2], wspace=0.05)

        # Main plot
        ax = fig.add_subplot(gs[0, 0])

        # Colorbar axes
        cbar_ax = fig.add_subplot(gs[0, 1])

        vmin = data.min() if self.vmin_auto.get() else self.vmin_manual.get()
        vmax = data.max() if self.vmax_auto.get() else self.vmax_manual.get()

        im = ax.imshow(
            data, cmap=self.colormap.get(), vmin=vmin, vmax=vmax,
            interpolation='nearest', aspect=2.0)
        cbar = fig.colorbar(im, cax=cbar_ax)

        unit = "mV" if self.datatype_var.get() == "Voltage" else "LSB"
        cbar.set_label(f'{self.datatype_var.get()} ({unit})')

        ax.set_title(f"{self.datatype_var.get()} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        ax.set_xlabel('X')
        ax.set_ylabel('Y')

        plt.savefig(filename, dpi=300, bbox_inches='tight')
        plt.close()

    def save_csv(self, data_array, timestamps, filename):
        # data_array shape: (frames, 10, 10)
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)

            # Write header
            header = ['timestamp'] + [f'pixel_{i}_{j}' for i in range(10) for j in range(10)]
            writer.writerow(header)

            # Write data
            for frame_idx, timestamp in enumerate(timestamps):
                row = [timestamp] + data_array[frame_idx].flatten().tolist()
                writer.writerow(row)

    def create_video(self, base_filename, folder):
        try:
            # Create video from saved PNG files
            video_filename = os.path.join(folder, f"{base_filename}.mp4")

            # Get list of PNG files
            png_files = [
                f for f in os.listdir(folder)
                if f.startswith(base_filename) and f.endswith('.png') and 'frame_' in f]
            png_files.sort()

            if not png_files:
                return

            # Read first image to get dimensions
            first_img = cv2.imread(os.path.join(folder, png_files[0]))
            height, width, layers = first_img.shape

            # Create video writer
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video = cv2.VideoWriter(video_filename, fourcc, 10.0, (width, height))

            # Add frames to video
            for png_file in png_files:
                img = cv2.imread(os.path.join(folder, png_file))
                video.write(img)

            video.release()

        except Exception as e:
            print(f"Video creation failed: {str(e)}")

    def browse_folder(self):
        folder = filedialog.askdirectory(initialdir=self.save_folder.get())
        if folder:
            self.save_folder.set(folder)

    def toggle_settings(self):
        if self.settings_visible.get():
            self.settings_panel.pack_forget()
            self.settings_visible.set(False)
            # Update button text
            for widget in self.left_panel.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Button) and child.cget('text') in ['Hide Settings', 'Show Settings']:
                            child.config(text='Show Settings')
                            break
        else:
            self.settings_panel.pack(fill=tk.X, pady=(0, 10), after=self.left_panel.winfo_children()[0])
            self.settings_visible.set(True)
            # Update button text
            for widget in self.left_panel.winfo_children():
                if isinstance(widget, ttk.Frame):
                    for child in widget.winfo_children():
                        if isinstance(child, ttk.Button) and child.cget('text') in ['Hide Settings', 'Show Settings']:
                            child.config(text='Hide Settings')
                            break

    def on_mouse_move(self, event):
        if event.inaxes == self.ax and self.show_values.get() and hasattr(self, 'current_data'):
            # Get pixel coordinates
            if event.xdata is not None and event.ydata is not None:
                x, y = int(round(event.xdata)), int(round(event.ydata))
                if 0 <= x < 10 and 0 <= y < 10:
                    # Get current data value
                    value = self.current_data[y, x]
                    unit = "mV" if self.datatype_var.get() == "Voltage" else "LSB"

                    # Store hover info
                    self.last_hover_info = (x, y, value)

                    self.ax.set_title(f"Live Preview - {self.datatype_var.get()} | Pixel ({x}, {y}): {value:.2f} {unit}")
                    self.canvas.draw_idle()
                    return

        # Clear hover info if outside valid area
        if self.last_hover_info:
            self.last_hover_info = None
            if hasattr(self, 'ax'):
                self.ax.set_title(f"Live Preview - {self.datatype_var.get()}")
                self.canvas.draw_idle()

    def on_mouse_leave(self, event):
        # Clear hover info when mouse leaves the axes
        if self.last_hover_info:
            self.last_hover_info = None
            if hasattr(self, 'ax'):
                self.ax.set_title(f"Live Preview - {self.datatype_var.get()}")
                self.canvas.draw_idle()

    def on_closing(self):
        if self.is_connected:
            self.disconnect_device()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = CMMP01GUI(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
