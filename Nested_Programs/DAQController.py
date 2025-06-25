import nidaqmx


class DAQController:
    """Handles all DAQ communication"""
    def send_digital(self, digital_outputs):
        try:
            with nidaqmx.Task() as task:
                channels = ','.join(digital_outputs.keys())
                task.do_channels.add_do_chan(channels)
                signals = [1 if digital_outputs[k] else 0 for k in digital_outputs]
                task.write(signals)
        except Exception as e:
            print(f"Error sending digital signals: {e}")

    def send_analog(self, analog_outputs):
        try:
            for channel, value in analog_outputs.items():
                with nidaqmx.Task() as task:
                    task.ao_channels.add_ao_voltage_chan(f"Dev1/{channel}", min_val=-10.0, max_val=10.0)
                    task.write(value)
        except Exception as e:
            print(f"Error sending analog signals: {e}") 