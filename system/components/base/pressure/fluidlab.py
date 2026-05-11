import os
import json
import time
import serial
import threading

class PressureControlLibrary:
    def __init__(self, port="COM15", baudrate=115200, timeout=1):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.ser = serial.Serial(self.port, self.baudrate, timeout=self.timeout)
        self.stop_thread = False  # Control thread exit
    
    def send_command(self, command, retries=10):
        """Send command and read return value with retry mechanism"""
        for attempt in range(retries):
            self.ser.write(command.encode())
            time.sleep(0.05)  # Wait for device response
            response = self.ser.read_all().decode().strip()
            if response:  # Check if there is a response
                return response
            print(f"Attempt {attempt + 1} failed, retrying...")
        raise RuntimeError(f"Command sending failed: {command}")
    
    def set_pressures(self, pressures):
        """Set pressure values for four channels"""
        if len(pressures) != 4:
            raise ValueError("Four pressure values must be provided!")

        checksum = sum(pressures)
        command = f"w{','.join(f'{p}' for p in pressures)},{checksum}\r"
        while True:
            response = self.send_command(command)
            if "transmission OK" in response:
                return response
            print(f"Setting failed, returned: {response}, retrying...")
            time.sleep(0.1)
    
    def reset_device(self):
        """Reset device"""
        print("Resetting device...")
        self.ser.write(b"i")  # Send reset command, don't wait for return
        time.sleep(1)  # Wait for device reset for a period (adjust according to device requirements)
        print("Device reset completed.")
    
    @staticmethod
    def linear_interpolate(data, target_y):
        """Linear interpolation based on target feedback value, supports four channels"""
        interpolated_pressures = []
        for channel_data in data:
            if target_y == 0:
                # If target pressure is 0, directly return input pressure value that is 0 in interpolation data
                for x, y in channel_data:
                    if y == 0:
                        interpolated_pressures.append(x)
                        break
                else:
                    # If there's no exact 0 point, choose the closest value to 0
                    closest = min(channel_data, key=lambda p: abs(p[1]))
                    interpolated_pressures.append(closest[0])
            else:
                for i in range(len(channel_data) - 1):
                    x1, y1 = channel_data[i]
                    x2, y2 = channel_data[i + 1]
                    if y1 <= target_y <= y2:
                        # Linear interpolation to calculate input value
                        x = x1 + (target_y - y1) * (x2 - x1) / (y2 - y1)
                        interpolated_pressures.append(round(x,4))
                        break
                else:
                    raise ValueError(f"Cannot find suitable interpolation point, target_y={target_y}")

        return interpolated_pressures
    
    @staticmethod
    def save_calibration_data(data, filename="calibration_data.json"):
        """Save calibration data to file"""
        with open(filename, "w") as file:
            json.dump(data, file)
        print(f"Calibration data saved to {filename}")
    
    @staticmethod
    def load_calibration_data(filename="calibration_data.json"):
        """Load calibration data from file"""
        # If filename is relative, make it relative to this module's directory
        if not os.path.isabs(filename):
            module_dir = os.path.dirname(os.path.abspath(__file__))
            filename = os.path.join(module_dir, filename)
        
        if os.path.exists(filename):
            with open(filename, "r") as file:
                return json.load(file)
        else:
            print(f"Calibration data file {filename} not found, please recalibrate the device.")
            return None
    
    def calibrate_and_collect_data(self):
        """Calibrate and collect data"""
        calibration_data = {
            "channel_1": [],  # Calibration data for first three channels
            "channel_2": [],
            "channel_3": [],
            "channel_4": []  # Calibration data for fourth channel
        }

        max_pressure = 2000
        step = max_pressure / 100

        print("Starting calibration data collection...")
        for i in range(101):
            # Handle pressure for first three channels and fourth channel separately
            pressure_1 = step * i  # First pressure value for first three channels
            pressure_2 = -1000 + (2000 * i / 100)  # Second pressure value for fourth channel, range from -1000 to 1000

            print(f"Setting pressure: First three channels: {pressure_1}, Fourth channel: {pressure_2}")

            # Set pressure values for first three channels, fourth channel set to `pressure_2`
            self.set_pressures([pressure_1] * 3 + [pressure_2])
            time.sleep(10)  # Wait 10 seconds to ensure stability
            read_response = self.send_command("r")
            read_values = [float(v) for v in read_response.split(",")]

            # Save calibration data for each channel separately
            calibration_data["channel_1"].append((pressure_1, read_values[0]))  # First channel calibration
            calibration_data["channel_2"].append((pressure_1, read_values[1]))  # Second channel calibration
            calibration_data["channel_3"].append((pressure_1, read_values[2]))  # Third channel calibration
            calibration_data["channel_4"].append((pressure_2, read_values[3]))  # Fourth channel calibration

            print(f"Reading returned: {read_response}")
            time.sleep(0.5)

        print("Calibration data collection completed:")
        for channel, data in calibration_data.items():
            print(f"{channel} calibration data: {data}")

        return calibration_data
    
    def read_pressures(self):
        """Read current pressure values"""
        response = self.send_command("r")
        return [float(val) for val in response.split(",")]
    
    def interactive_pressure_control(self, calibration_data):
        """Interactive pressure control"""
        while not self.stop_thread:
            # Get user input for target pressure values
            input_pressures = input("Please enter four target pressure values (format: p1,p2,p3,p4, press 'q' to exit): ")
            if input_pressures.lower() == 'q':
                print("Exiting interactive mode")
                self.stop_thread = True  # Set thread exit flag
                break
            try:
                pressures = list(map(float, input_pressures.split(",")))
                if len(pressures) != 4:
                    raise ValueError("Please enter four pressure values")

                # Use linear interpolation to calculate input pressure for each channel
                target_pressures = []
                for i in range(4):
                    target_y = pressures[i]
                    input_pressure = self.linear_interpolate([calibration_data[f"channel_{i + 1}"]], target_y)
                    target_pressures.append(input_pressure[0])  # Only take one value

                # Set pressure
                print(f"Target pressure: {pressures}, Input pressure: {target_pressures}")
                self.set_pressures(target_pressures)

                # Wait 3 seconds
                time.sleep(3)

                # Read pressure feedback
                current_pressures = self.read_pressures()
                print(f"Current pressure readings: {current_pressures}")

            except ValueError as e:
                print(f"Invalid input: {e}")
    
    def adjust_pressures_relative(self, adjustments):
        print(adjustments)
        current_pressures = self.read_pressures()
        new_pressures = []
        for i in range(4):
            # Calculate new target pressure value
            print(current_pressures[i])
            new_pressure = current_pressures[i] + adjustments[i]
            
            # Limit target pressure value according to channel
            if i < 3:
                # First three channels limit range 0 ~ 2000
                new_pressure = max(min(new_pressure, 2000), 0)
            else:
                # Fourth channel limit range -1000 ~ 1000
                new_pressure = max(min(new_pressure, 1000), -1000)
            
            new_pressures.append(new_pressure)
        
        print(f"New target pressure: {new_pressures}")
        self.set_pressures(new_pressures)
        return new_pressures

    def start_interactive_thread(self, calibration_data):
        """Start interactive control thread"""
        thread = threading.Thread(target=self.interactive_pressure_control, args=(calibration_data,))
        thread.start()
        return thread
    
    def initialize(self):
        """Initialize program"""
        calibration_data = self.load_calibration_data()

        if calibration_data:
            print("Loading saved calibration data...")
        else:
            # No calibration data, start calibration
            print("No existing calibration data found, starting calibration...")
            calibration_data = self.calibrate_and_collect_data()
            self.save_calibration_data(calibration_data)
        return calibration_data
        # Start interactive control thread
        #interactive_thread = self.start_interactive_thread(calibration_data)
        #interactive_thread.join()  # Main thread waits for interactive thread to exit

if __name__ == "__main__":
    print("=== Pressure Control Calibration Tool ===")
    print("This will perform a full calibration cycle.")
    
    # Initialize pressure controller
    lib = PressureControlLibrary(port="COM3")
    
    # Reset device
    lib.reset_device()
    
    # Force calibration
    print("\nStarting calibration process...")
    calibration_data = lib.calibrate_and_collect_data()
    
    # Save calibration data to module directory
    module_dir = os.path.dirname(os.path.abspath(__file__))
    save_path = os.path.join(module_dir, "calibration_data.json")
    lib.save_calibration_data(calibration_data, save_path)
    
    print(f"\nCalibration completed! Data saved to: {save_path}")
    print("You can now use this calibration data in your applications.")
