import tkinter as tk
from tkinter import messagebox
import time
import random
import numpy as np
from datetime import datetime
import pygame  # For sound
import os

# Initialize pygame mixer for sound
pygame.mixer.init()

# Sudoku puzzle generation
def generate_sudoku():
    base = 3
    side = base * base

    # Randomly filled in a valid Sudoku grid, then remove numbers to create puzzle
    def pattern(r, c): return (base*(r % base) + r // base + c) % side
    rBase = range(base)
    rows = [g * base + r for g in rBase for r in rBase]
    cols = [g * base + c for g in rBase for c in rBase]
    
    nums = random.sample(range(1, base * base + 1), base * base)  # Random number set for filling the grid
    grid = [[nums[pattern(r, c)] for c in cols] for r in rows]

    # Set 8 or 9 random cells to 0
    num_cells_to_clear = random.randint(8, 9)  # Randomly choose between 8 or 9 empty cells
    for _ in range(num_cells_to_clear):
        # Randomly select a row and column index
        row = random.randint(0, 8)
        col = random.randint(0, 8)
        
        # Set the selected cell to 0 (empty)
        grid[row][col] = 0

    return grid


# Basic Sudoku Solver to check completion
def check_sudoku(solution):
    for row in solution:
        if len(set(row)) != 9:
            return False
    return True

class AlarmClockApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Alarm Clock with Sudoku")
        
        # Call the setup_widgets function to initialize all the widgets
        self.setup_widgets("show")

        self.sudoku_frame = tk.Frame(self.root)
        self.sudoku_frame.pack()

        self.sudoku_puzzle = None
        self.sudoku_solution = None
        self.alarm_set = False
        self.alarm_time = None
        self.alarm_active = False

        self.update_time()

    def setup_widgets(self, action="show"):
        """
        Set up or hide the widgets depending on the action.
        action: "show" to display widgets, "hide" to hide them
        """
        if action == "show":
            # Initialize and show the widgets
            self.current_time_label = tk.Label(self.root, font=("Helvetica", 24))
            self.current_time_label.pack()

            self.alarm_time_label = tk.Label(self.root, text="Set Alarm Time:", font=("Helvetica", 14))
            self.alarm_time_label.pack()

            self.hours = [f"{i:02d}" for i in range(1, 13)]
            self.minutes = [f"{i:02d}" for i in range(0, 60, 2)]
            self.am_pm = ["AM", "PM"]

            self.hour_var = tk.StringVar(self.root)
            self.hour_var.set(self.hours[0])

            self.minute_var = tk.StringVar(self.root)
            self.minute_var.set(self.minutes[0])

            self.am_pm_var = tk.StringVar(self.root)
            self.am_pm_var.set(self.am_pm[0])

            self.hour_menu = tk.OptionMenu(self.root, self.hour_var, *self.hours)
            self.hour_menu.pack(side=tk.LEFT)

            self.minute_menu = tk.OptionMenu(self.root, self.minute_var, *self.minutes)
            self.minute_menu.pack(side=tk.LEFT)

            self.am_pm_menu = tk.OptionMenu(self.root, self.am_pm_var, *self.am_pm)
            self.am_pm_menu.pack(side=tk.LEFT)

            self.set_alarm_button = tk.Button(self.root, text="Set Alarm", font=("Helvetica", 14), command=self.set_alarm)
            self.set_alarm_button.pack()

        elif action == "hide":
            # Hide the widgets when the alarm is set
            self.current_time_label.pack_forget()
            self.alarm_time_label.pack_forget()
            self.hour_menu.pack_forget()
            self.minute_menu.pack_forget()
            self.am_pm_menu.pack_forget()
            self.set_alarm_button.pack_forget()

    def update_time(self):
        # Get the current time in 12-hour format with AM/PM
        current_time = time.strftime("%I:%M:%S %p")  # 12-hour format with AM/PM
        correction_time = time.strftime("%I:%M %p")
        self.current_time_label.config(text=current_time)
        
        # Debugging: Print both times to check if they match
        if self.alarm_set and not self.alarm_active:
            
            alarm_time_str = self.alarm_time
            current_time_now = datetime.strptime(current_time, "%I:%M:%S %p")
            alarm_time = datetime.strptime(alarm_time_str, "%I:%M %p")
            howmuchisLeft = alarm_time - current_time_now
            if howmuchisLeft.total_seconds() > 0:  # If the alarm time is in the future
                os.system('clear')
                print(f"Alarm will activate in: {str(howmuchisLeft)}")
            if correction_time == self.alarm_time:
                self.trigger_alarm()
                print("Wakey Wakey")
        
        self.root.after(1000, self.update_time)

    def set_alarm(self):
        # Get selected alarm time
        hour = self.hour_var.get()
        minute = self.minute_var.get()
        am_pm = self.am_pm_var.get()

        # Convert to 12-hour format string (AM/PM)
        self.alarm_time = f"{hour}:{minute} {am_pm}"

        self.alarm_set = True
        self.alarm_active = False
        self.sudoku_frame.pack_forget()  # hide sudoku puzzle

        # Show confirmation message
        messagebox.showinfo("Alarm Set", f"Alarm is set for {self.alarm_time}.")

    def trigger_alarm(self):
        os.system('clear')
        self.alarm_active = True
        self.alarm_time_label = tk.Label(self.root, text="ALARM! Solve Sudoku to stop.", font=("Helvetica", 16, "bold"), fg="red")
        self.setup_widgets(action="hide")

        # Play sound
        self.play_alarm_sound()

        # Generate Sudoku puzzle
        self.sudoku_puzzle = generate_sudoku()
        self.sudoku_solution = np.array(self.sudoku_puzzle).copy()
        
        # Display Sudoku Puzzle below the alarm label
        self.show_sudoku()  # Call the method to show the puzzle

    def play_alarm_sound(self):
        try:
            # Load and play sound file (make sure the sound file is in the same directory or provide the full path)
            pygame.mixer.music.load("alarm_sound.mp3")  # Add your alarm sound file (MP3 or WAV format)
            pygame.mixer.music.play(-1)  # Loop the alarm sound
        except Exception as e:
            print(f"Error loading sound: {e}")  # Handle errors if the sound file is not found

    def stop_alarm_sound(self):
        pygame.mixer.music.stop()  # Stop the alarm sound when the alarm is solved

    def show_sudoku(self):
        # Ensure the Sudoku frame is cleared and not packed yet
        for widget in self.sudoku_frame.winfo_children():
            widget.destroy()  # Clear any existing puzzle

        self.sudoku_entries = []
        for i in range(9):
            row_entries = []
            for j in range(9):
                entry = tk.Entry(self.sudoku_frame, width=3, font=("Helvetica", 14))
                entry.grid(row=i, column=j)  # Using grid to align the entries
                
                if self.sudoku_puzzle[i][j] != 0:  # If the cell has a predefined value
                    entry.insert(tk.END, str(self.sudoku_puzzle[i][j]))  # Pre-fill the cell
                    entry.config(state="disabled")  # Disable the cell (can't be edited)
                else:
                    entry.config(state="normal")  # Enable the cell (can be edited)

                row_entries.append(entry)
            self.sudoku_entries.append(row_entries)

        # Repack the sudoku_frame to ensure it shows up after being hidden
        self.sudoku_frame.pack(fill=tk.BOTH, expand=True, pady=10)  # Adding some padding for spacing

        # Add the Submit button below the Sudoku grid
        self.submit_button = tk.Button(self.sudoku_frame, text="Submit", font=("Helvetica", 14), command=self.check_solution)
        self.submit_button.grid(row=9, column=0, columnspan=9)  # Submit button placed below the puzzle

    def check_solution(self):
        user_solution = []
        for row_entries in self.sudoku_entries:
            user_solution.append([int(entry.get()) for entry in row_entries])
        
        if check_sudoku(user_solution):
            self.stop_alarm()
        else:
            messagebox.showerror("Incorrect", "Sudoku is not solved correctly. Try again!")

    def stop_alarm(self):
        # Stop the alarm process
        self.alarm_active = False
        self.alarm_time_label.destroy()  # Remove the alarm label
        self.stop_alarm_sound()  # Stop the sound when the alarm is solved
        
        # Hide sudoku frame
        self.sudoku_frame.pack_forget()

        # Reset the alarm-related variables
        self.alarm_set = False
        self.alarm_time = None

        # Show the initial widgets again
        self.setup_widgets(action="show")

        # Reset the current time display to the current time
        self.update_time()  # Start updating time again

        # Optionally, reset any other widgets you want to reinitialize

        messagebox.showinfo("Alarm", "Congratulations! Alarm stopped.")

        
# Run the app
if __name__ == "__main__":
    root = tk.Tk()
    app = AlarmClockApp(root)
    root.mainloop()
