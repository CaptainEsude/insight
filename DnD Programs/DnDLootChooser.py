import os
import random
import pyperclip
from kivy.app import App
from kivy.uix.widget import Widget
import openpyxl
from kivy.lang import Builder
from kivy.properties import NumericProperty, StringProperty, ListProperty, ObjectProperty, BooleanProperty, BoundedNumericProperty, OptionProperty, ReferenceListProperty, AliasProperty, DictProperty, VariableListProperty, ConfigParserProperty, ColorProperty
from kivy.clock import Clock
from datetime import datetime
import pyperclip
from kivy.core.window import Window

# Load the Kivy file
Builder.load_file('designer.kv')

# Create a class for the GridLayout
class MyGridLayout(Widget):
    #define variables
    IsayText = StringProperty("")
    time_text = StringProperty("")
    contents_of_box = StringProperty()
    chest_selected = StringProperty()
    chest_size_selected = StringProperty()

    #initialize variables
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        Clock.schedule_interval(self.update_time, 1)  # Update every second
        self.update_time()

    #updateing time
    def update_time(self, dt=None):
        self.time_text = datetime.now().strftime("%I:%M:%S %p")  # 12-hour format with AM/PM
        
    #import loot tables
    workbook = openpyxl.load_workbook("Loot_Tables.xlsx")

    #import sheets
    adventurers_gear = workbook["Adventurers Gear"]
    alchemy = workbook["Alchemy"]
    valuables = workbook["Valuables"]
    random_junk = workbook["Random Junk"]
    spells = workbook["Spells"]

    #initialize dictionary
    XSL_chest_contents = {}

    #initialize sheet names
    sheet_names = ["Adventurers Gear", "Alchemy", "Valuables", "Random Junk", "Spells"]

    #initialize loot table selection
    def loot_table_selection(self):
        for sheet_name in self.sheet_names:
            sheet = self.workbook[sheet_name]
            filtered_rows = []

            for row in sheet.iter_rows(values_only=True):
                # Replace None values with defaults
                clean_row = [cell if cell is not None else "Unknown" for cell in row[:4]]
                filtered_rows.append(clean_row)

            if filtered_rows:
                self.XSL_chest_contents[sheet_name] = filtered_rows

    #get chests
    def get_chests(self):
        return ['common chest', 'uncommon chest', 'rare chest', 'very rare chest', 'legendary chest']
    
    def get_chest_size(self):
        return ['extra small','small', 'medium', 'large', 'huge']
    
    #get chest contents
    def on_chest_select(self, chest):
        self.chest_selected = chest
        self.loot_table_selection()
        self.show_contents()

    def on_chest_select_size(self, chest):
        self.chest_size_selected = chest

    def items_in_chest(self):
        if self.chest_size_selected == "extra small":
            return random.randint(1, 3)
        elif self.chest_size_selected == "small":
            return random.randint(3, 6)
        elif self.chest_size_selected == "medium":
            return random.randint(5, 7)
        elif self.chest_size_selected == "large":
            return random.randint(4, 8)
        elif self.chest_size_selected == "huge":
            return random.randint(6, 10)
    
    # Choose chest value based on rarity
    def choosing_chest_value(self, chest_value_min, chest_value_max):
        content_str = ""
        all_items = []
        
        # Collect all items from the filtered uncommon chest data
        for sheet_name, items in self.XSL_chest_contents.items():
            for item in items:
                if len(item) >= 4:  # Ensure that the item has at least 4 values
                    name = item[1]  # Item name
                    value = item[2]  # Item value
                    rarity = item[3]  # Item rarity
                    
                    try:
                        valueint = float(value)
                    except ValueError:
                        continue
                    
                    if valueint >= chest_value_min and valueint <= chest_value_max:  # Add item only if value is <= 200
                        all_items.append((name, valueint, rarity))
        # Randomly select up to 5 items, ensuring total value does not exceed 200
        total_value = 0
        selected_items = []
        size_chest = self.items_in_chest()
        max_items = int(size_chest)

        # Randomly select items until the total value exceeds 200 or 5 items are selected
        while total_value < chest_value_max and len(selected_items) < max_items and all_items:
#            attempts += 1
#            if attempts > 50:  # Limit the number of attempts to avoid infinite loop
#                break
            item = random.choice(all_items)
            item_value = item[1]
            if total_value + item_value <= chest_value_max:
                selected_items.append(item)
                total_value += item_value
                all_items.remove(item)  # Remove selected item to avoid duplicates
            else:
                # If item value exceeds chest_value_max, remove it from the list
                all_items.remove(item)  # Try another item
        # Prepare the string of selected items

        for item in selected_items:
            content_str += f"Name: {item[0]}\nValue: {item[1]} Gold\n Rarity: {item[2]}\n\n"

        # Update the label with the selected items    
        self.contents_of_box = content_str.strip()  # Update the label with the selected items

    #show contents
    def show_contents(self):
        if self.chest_selected == "common chest":
            self.choosing_chest_value(0, random.randint(1, 25))
        elif self.chest_selected == "uncommon chest":
            self.choosing_chest_value(25, random.randint(25, 100))
        elif self.chest_selected == "rare chest":
            self.choosing_chest_value(100, random.randint(100, 500))
        elif self.chest_selected == "very rare chest":
            self.choosing_chest_value(500, random.randint(500, 1500))
        elif self.chest_selected == "legendary chest":
            self.choosing_chest_value(1500, random.randint(1500, 10000))


    #copy contents
    def copy_contents(self):
        pyperclip.copy(self.contents_of_box)

# Create the App class
class DnDLootChooser(App):
    def build(self):
        Window.size = (550, 850)
        return MyGridLayout()

# Run the app
if __name__ == '__main__':
    DnDLootChooser().run()
