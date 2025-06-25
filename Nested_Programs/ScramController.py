import threading
import winsound
import nidaqmx
import time

from Constants_Paths import DAQ_DEVICE, DIO_CHANNELS


class ScramController:
    """
    ONE responsibility: put every NI-DAQ line into a safe, idle state *now*.
    Usage:
        self.scram = ScramController(parent=self)   # inside SABREGUI.__init__
        ...
        def scram_experiment(self):
            self.scram()
    """

    SAFE_AO_RANGE = (-10.0, 10.0)
    SAFE_AO_CHANS = f"{DAQ_DEVICE}/ao0:3"  # adjust if you use fewer/more lines

    def __init__(self, parent: "SABREGUI"):
        self.gui      = parent
        self.system   = nidaqmx.system.System.local()

    # ------------------------------------------------------------------ public -
    def __call__(self):
        """Blocking emergency stop.  Returns when hardware is safe."""
        try:
            self._kill_tasks()
            self._reset_device()
            self._drive_safe_levels()
        finally:
            self._sync_gui()

    def emergency_stop(self):
        """Alias for backward compatibility"""
        self.__call__()

    def send_zero_voltage(self):
        """Alias for set_voltage_to_zero for backward compatibility"""
        self.set_voltage_to_zero()

    def set_voltage_to_zero(self):
        """Set the voltage to 0V on ao3 with proper cleanup"""
        try:
            # First cleanup existing tasks
            self.cleanup_tasks()
            
            # Create new task with context manager
            with nidaqmx.Task() as task:
                task.ao_channels.add_ao_voltage_chan(
                    f"{DAQ_DEVICE}/ao3", 
                    min_val=self.SAFE_AO_RANGE[0], 
                    max_val=self.SAFE_AO_RANGE[1]
                )
                task.write(0.0, auto_start=True)
                print("[SCRAM] Set voltage to 0V")
                if hasattr(self.gui, 'update_waveform_plot'):
                    self.gui.update_waveform_plot(0.0, time.time())
        except Exception as e:
            print(f"[SCRAM] Error setting voltage to 0V: {e}")

    def reset_plots(self):
        """Reset all plots to initial state"""
        try:
            if hasattr(self.gui, 'ax') and hasattr(self.gui, 'canvas'):
                self.gui.ax.clear()
                self.gui.ax.set_xlabel("Time (s)")
                self.gui.ax.set_ylabel("Voltage (V)")
                self.gui.ax.set_title("Waveform Preview")
                self.gui.ax.grid(True, linestyle="--", linewidth=0.3)
                
                # Clear any line references
                if hasattr(self.gui, 'line'):
                    self.gui.line = None
                
                # Force immediate redraw to show blank plot
                self.gui.canvas.draw()
                self.gui.canvas.flush_events()
                print("[SCRAM] Waveform plot reset to blank")
        except Exception as e:
            print(f"[SCRAM] Error resetting plots: {e}")

    # ----------------------------------------------------------- implementation
    def _kill_tasks(self):
        """Stop & close every open task as quickly as possible."""
        for task in list(self.system.tasks):
            try:
                task.stop()
            except Exception:
                pass
            try:
                task.close()
            except Exception:
                pass
        # clear GUI reference
        if hasattr(self.gui, "test_task"):
            self.gui.test_task = None

    def _reset_device(self):
        """Hardware reset clears watchdogs/regeneration, < 50 ms."""
        try:
            self.system.devices[DAQ_DEVICE].reset_device()
        except Exception as exc:
            print(f"[SCRAM] reset_device warning: {exc}")

    def _drive_safe_levels(self):
        """Load and maintain Initial_State configuration, not just all LOW."""
        # AO - Set to 0V first
        try:
            with nidaqmx.Task() as ao:
                ao.ao_channels.add_ao_voltage_chan(
                    self.SAFE_AO_CHANS,
                    min_val=self.SAFE_AO_RANGE[0],
                    max_val=self.SAFE_AO_RANGE[1]
                )
                ao.write([0.0] * ao.number_of_channels)
                ao.start()
        except Exception as exc:
            print(f"[SCRAM] AO safe-level warning: {exc}")

        # DO - Load Initial_State configuration instead of all LOW
        try:
            success = self._load_initial_state_config()
            if not success:
                print("[SCRAM] Failed to load Initial_State, falling back to all LOW")
                # Fallback to all LOW if Initial_State can't be loaded
                with nidaqmx.Task() as do:
                    do.do_channels.add_do_chan(",".join(DIO_CHANNELS))
                    do.write([0] * len(DIO_CHANNELS))
                do.start()
                print("[SCRAM] DO fallback safe-level set (all LOW)")
        except Exception as exc:
            print(f"[SCRAM] DO safe-level warning: {exc}")
            
    def _load_initial_state_config(self):
        """Load the Initial_State configuration and apply DIO settings."""
        try:
            import json
            import os
            from .Constants_Paths import CONFIG_DIR
            
            config_file = os.path.join(CONFIG_DIR, "Initial_State.json")
            if not os.path.exists(config_file):
                print(f"[SCRAM] Initial_State config file not found: {config_file}")
                return False

            with open(config_file, "r") as file:
                config_data = json.load(file)

            # Extract DIO states from config
            dio_states = {}
            for i in range(8):
                dio_states[f"DIO{i}"] = config_data.get(f"DIO{i}", "LOW").upper() == "HIGH"

            # Send DIO states to DAQ
            with nidaqmx.Task() as do:
                do.do_channels.add_do_chan(",".join(DIO_CHANNELS))
                # Convert states to list for DAQ
                signals = [dio_states[f"DIO{i}"] for i in range(8)]
                do.write(signals)
                do.start()
                
            print(f"[SCRAM] Initial_State DIO configuration applied: {signals}")
            
            # Update GUI state label to indicate Initial_State, not EMERGENCY STOP
            if hasattr(self.gui, 'state_label'):
                self.gui.state_label.config(text="State: Initial (Post-SCRAM)")
                
            return True

        except Exception as e:
            print(f"[SCRAM] Error loading Initial_State configuration: {e}")
            return False

    def cleanup_tasks(self):
        """Clean up any existing DAQ tasks"""
        try:
            # First close GUI's test task if it exists
            if hasattr(self.gui, 'test_task') and self.gui.test_task:
                try:
                    self.gui.test_task.stop()
                    self.gui.test_task.close()
                except:
                    pass
                self.gui.test_task = None

            # Close GUI's DIO task if it exists
            if hasattr(self.gui, 'dio_task') and self.gui.dio_task:
                try:
                    self.gui.dio_task.close()
                except:
                    pass
                self.gui.dio_task = None

            # Then close any other tasks through standard cleanup
            self._kill_tasks()
            
            # Brief delay to ensure hardware cleanup
            import time
            time.sleep(0.05)
            
        except Exception as e:
            print(f"[SCRAM] Error cleaning up tasks: {e}")

    def _sync_gui(self):
        """Bring the GUI back to a known idle state."""
        try:
            g = self.gui
            g.stop_polarization = False
            g.plotting = False
            g.time_window = None

            # Cancel any existing timer thread
            if hasattr(g, 'timer_thread') and g.timer_thread:
                g.timer_thread.cancel()
                g.timer_thread = None

            # Reset timer variables
            g.end_time = None
            g.start_time = None

            # Update GUI elements if they exist
            if hasattr(g, 'timer_label') and g.timer_label.winfo_exists():
                g.timer_label.config(text="00:00:000")
                g.timer_label.update()
            
            if hasattr(g, 'state_label') and g.state_label.winfo_exists():
                g.state_label.config(text="State: Idle")
                g.state_label.update()

            # Reset plots
            self.reset_plots()

            # virtual panel back to initial (if present)
            if getattr(g, "virtual_panel", None) and g.virtual_panel.winfo_exists():
                g.virtual_panel.running = False
                g.virtual_panel.load_config("Initial_State")

            # audible cue
            if g.audio_enabled.get():
                threading.Thread(target=lambda: winsound.Beep(1800, 300),
                               daemon=True).start()

        except Exception as e:
            print(f"Error syncing GUI: {e}")
