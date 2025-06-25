import tkinter as tk
import time


class TimerWidget(tk.Frame):
    """Timer widget for countdown display"""
    def __init__(self, master, font=("Courier", 12, "bold"), **kwargs):
        super().__init__(master, **kwargs)
        self.time_left = 0
        self.active = False
        self.timer_label = tk.Label(self, text="00:00:00", font=font)
        self.timer_label.pack()

    def start(self, duration):
        """Start the countdown timer"""
        self.time_left = duration
        self.active = True
        self._update()

    def _update(self):
        """Update the timer display"""
        if self.active and self.time_left > 0:
            # Format time as HH:MM:SS
            hours = self.time_left // 3600
            minutes = (self.time_left % 3600) // 60
            seconds = self.time_left % 60
            time_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            
            self.timer_label.config(text=time_str)
            self.time_left -= 1
            
            # Schedule next update
            self.after(1000, self._update)
        elif self.time_left <= 0:
            self.timer_label.config(text="00:00:00")
            self.active = False

    def stop(self):
        """Stop the timer"""
        self.active = False
        self.timer_label.config(text="00:00:00") 