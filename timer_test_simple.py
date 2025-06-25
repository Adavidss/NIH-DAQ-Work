#!/usr/bin/env python3
"""
Simple Timer Test for SABRE GUI
Tests the new timer implementation to ensure visual updates work correctly.
"""

import tkinter as tk
import time
import winsound
from tkinter import messagebox

class SimpleTimerTest:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("SABRE Timer Test")
        self.root.geometry("500x300")
        
        # Timer variables - matching the main application
        self.timer_active = False
        self.timer_start_time = 0.0
        self.timer_duration = 0.0
        self.timer_job_id = None
        self.app_launch_time = time.time()
        self.audio_enabled = tk.BooleanVar(value=True)
        
        self.setup_ui()
        self.start_elapsed_timer()
        
    def setup_ui(self):
        """Set up the test UI"""
        # Title
        title_label = tk.Label(self.root, text="SABRE Timer System Test", 
                              font=("Arial", 16, "bold"))
        title_label.pack(pady=10)
        
        # Timer display (matching main app style)
        timer_frame = tk.Frame(self.root, bg="#e0e0e0", relief="groove", bd=2)
        timer_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(timer_frame, text="Timer Display:", font=("Arial", 12), 
                bg="#e0e0e0").pack(side="left", padx=10)
        
        self.timer_label = tk.Label(timer_frame, text="00:00:00", 
                                   font=("Courier", 14, "bold"), 
                                   fg="#003366", bg="#e0e0e0", 
                                   relief="sunken", padx=10, pady=2)
        self.timer_label.pack(side="right", padx=10, pady=2)
        
        # Test buttons
        button_frame = tk.Frame(self.root)
        button_frame.pack(pady=20)
        
        tk.Button(button_frame, text="Test 5 Second Timer", 
                 command=lambda: self.start_timer(5), 
                 bg="#1565C0", fg="white", font=("Arial", 10, "bold"),
                 width=20, height=2).pack(pady=5)
        
        tk.Button(button_frame, text="Test 10 Second Timer", 
                 command=lambda: self.start_timer(10),
                 bg="#2E7D32", fg="white", font=("Arial", 10, "bold"),
                 width=20, height=2).pack(pady=5)
        
        tk.Button(button_frame, text="Test 30 Second Timer", 
                 command=lambda: self.start_timer(30),
                 bg="#EF6C00", fg="white", font=("Arial", 10, "bold"),
                 width=20, height=2).pack(pady=5)
        
        tk.Button(button_frame, text="STOP Timer", 
                 command=self.stop_timer,
                 bg="#B71C1C", fg="white", font=("Arial", 10, "bold"),
                 width=20, height=2).pack(pady=5)
        
        # Audio toggle
        audio_frame = tk.Frame(self.root)
        audio_frame.pack(pady=10)
        tk.Checkbutton(audio_frame, text="Audio Alerts", 
                      variable=self.audio_enabled).pack()
        
        # Status display
        self.status_label = tk.Label(self.root, text="Ready - Timer showing elapsed time since launch", 
                                    fg="green", font=("Arial", 10))
        self.status_label.pack(pady=10)
        
    def start_timer(self, total_seconds):
        """Start countdown timer - matches main application implementation"""
        print(f"Starting timer for {total_seconds} seconds")
        self.status_label.config(text=f"Countdown timer started: {total_seconds} seconds", fg="orange")
        
        # Stop any existing timer completely 
        self.stop_timer()
        
        # Set up timer variables
        self.timer_active = True
        self.timer_start_time = time.time()
        self.timer_duration = float(total_seconds)
        
        # Immediately update display and start the timer loop
        self._timer_tick()
        
        # Play audio alert if enabled
        if self.audio_enabled.get():
            try:
                winsound.Beep(1000, 200)
            except Exception as e:
                print(f"Audio alert error: {e}")

    def _timer_tick(self):
        """Timer tick - updates display every 50ms for smooth countdown"""
        if not self.timer_active:
            return
            
        # Calculate remaining time
        elapsed = time.time() - self.timer_start_time
        remaining = max(0.0, self.timer_duration - elapsed)
        
        # Update display
        if remaining > 0:
            # Format as MM:SS:mmm
            minutes = int(remaining // 60)
            seconds = int(remaining % 60) 
            milliseconds = int((remaining * 1000) % 1000)
            time_text = f"{minutes:02d}:{seconds:02d}:{milliseconds:03d}"
            
            # Update timer label directly
            if hasattr(self, 'timer_label') and self.timer_label.winfo_exists():
                self.timer_label.config(text=time_text, fg="#FF6600")  # Orange during countdown
                
            # Schedule next update in 50ms for smooth display
            self.timer_job_id = self.root.after(50, self._timer_tick)
        else:
            # Timer complete
            self._timer_complete()

    def _timer_complete(self):
        """Handle timer completion"""
        print("Timer completed")
        self.timer_active = False
        self.status_label.config(text="Timer completed! Returning to elapsed timer in 2 seconds...", fg="green")
        
        # Set final display
        if hasattr(self, 'timer_label') and self.timer_label.winfo_exists():
            self.timer_label.config(text="00:00:000", fg="green")
        
        # Play completion sound
        if self.audio_enabled.get():
            try:
                winsound.Beep(880, 200)
                winsound.Beep(1760, 300)
            except Exception as e:
                print(f"Audio completion error: {e}")
        
        # Flash green then return to elapsed timer after 2 seconds
        self.root.after(2000, self._resume_elapsed_timer)

    def _resume_elapsed_timer(self):
        """Resume the elapsed timer display"""
        if not self.timer_active:  # Only if no new countdown started
            self.status_label.config(text="Elapsed timer resumed - showing time since launch", fg="blue")
            self._update_elapsed_timer()

    def stop_timer(self):
        """Stop the countdown timer completely"""
        was_active = self.timer_active
        self.timer_active = False
        
        # Cancel any pending timer job
        if hasattr(self, 'timer_job_id') and self.timer_job_id is not None:
            try:
                self.root.after_cancel(self.timer_job_id)
            except:
                pass
            self.timer_job_id = None
        
        if was_active:
            print("Timer stopped")
            self.status_label.config(text="Timer stopped - returning to elapsed timer", fg="red")
            self._resume_elapsed_timer()

    def start_elapsed_timer(self):
        """Start the elapsed timer when app launches"""
        self._update_elapsed_timer()

    def _update_elapsed_timer(self):
        """Update elapsed time since app start - only when no countdown active"""
        if hasattr(self, 'timer_active') and self.timer_active:
            # Don't interfere with countdown - check again in 1 second
            self.root.after(1000, self._update_elapsed_timer)
            return
            
        # Calculate elapsed time since app launch
        elapsed = int(time.time() - self.app_launch_time)
        hours = elapsed // 3600
        minutes = (elapsed % 3600) // 60
        seconds = elapsed % 60
        
        # Update display
        if hasattr(self, 'timer_label') and self.timer_label.winfo_exists():
            self.timer_label.config(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}", fg="#003366")
        
        # Schedule next update in 1 second
        self.root.after(1000, self._update_elapsed_timer)

    def run(self):
        """Run the test application"""
        print("Starting SABRE Timer Test...")
        print("- Blue timer shows elapsed time since launch")
        print("- Orange timer shows countdown during operations")
        print("- Green timer shows completion")
        print("- Test different timer durations with the buttons")
        self.root.mainloop()

if __name__ == "__main__":
    test = SimpleTimerTest()
    test.run() 