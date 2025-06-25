import time


class CountdownController:
    """Handles countdown timer functionality"""
    
    def __init__(self, parent):
        self.parent = parent
        self.countdown_running = False
        self.countdown_end_time = None
        self.after_id = None
        
    def start_countdown(self, duration_s):
        """Start countdown timer for given duration in seconds"""
        if not hasattr(self.parent, 'countdown_label'):
            print("Timer label not initialized yet")
            return
            
        self.countdown_end_time = time.time() + duration_s
        self.countdown_running = True
        self.update_countdown()
        print(f"Countdown started for {duration_s} seconds")

    def update_countdown(self):
        """Update countdown display every millisecond"""
        if not self.countdown_running:
            return
            
        remaining = max(0.0, self.countdown_end_time - time.time()) if self.countdown_end_time else 0.0
        
        if remaining > 0:
            minutes = int(remaining // 60)
            seconds = int(remaining % 60)
            milliseconds = int((remaining % 1) * 1000)
            
            if hasattr(self.parent, 'countdown_label') and self.parent.countdown_label is not None:
                self.parent.countdown_label.config(
                    text=f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
                )
            
            self.after_id = self.parent.after(1, self.update_countdown)
        else:
            if hasattr(self.parent, 'countdown_label') and self.parent.countdown_label is not None:
                self.parent.countdown_label.config(text="00:00.000")
            self.countdown_running = False
            print("Countdown completed")

    def stop_countdown(self):
        """Stop the countdown timer"""
        self.countdown_running = False
        if self.after_id:
            self.parent.after_cancel(self.after_id)
            self.after_id = None
        if hasattr(self.parent, 'countdown_label') and self.parent.countdown_label is not None:
            self.parent.countdown_label.config(text="00:00.000")
        print("Countdown stopped") 