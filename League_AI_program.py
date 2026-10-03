import os
import time
import threading
import requests
import torch
import tkinter as tk
from tkinter import scrolledtext, messagebox
import json  # For saving and loading settings
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel
from datetime import timedelta

# Define the platform region as a constant
PLATFORM_REGION = "NA1"  # Ensure this is uppercase

# Set the model name
model_name = "tiiuae/falcon-7b"

# Function to check if the LoRA adapters are present
def check_model_exists(model_path):
    """
    Check if the LoRA adapter files exist in the specified directory.
    Looks for 'adapter_model.safetensors' or 'adapter_model.bin'.
    """
    has_safetensors = os.path.isfile(os.path.join(model_path, "adapter_model.safetensors"))
    has_bin = os.path.isfile(os.path.join(model_path, "adapter_model.bin"))
    return os.path.isdir(model_path) and (has_safetensors or has_bin)

# Function to load the model and tokenizer with CPU offloading
def load_model(lora_model_path):
    """
    Load the tokenizer and model with quantization and CPU offloading.
    """
    # Load the tokenizer
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.pad_token = tokenizer.eos_token  # Ensure pad token is set

    # Quantization configuration
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
        bnb_4bit_quant_type="nf4",
    )

    # Define max memory per device
    # Adjust these values based on your system's resources
    max_memory = {
        0: "6GB",     # Replace '6GB' with the amount of VRAM your GPU has
        "cpu": "12GB"  # Adjust based on your available CPU RAM
    }

    # Create the device map automatically
    device_map = "auto"

    # Load the base model with quantization and CPU offloading
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=quantization_config,
        device_map=device_map,
        max_memory=max_memory,
        offload_folder="./offload",  # Folder for offloaded weights
        offload_state_dict=True,     # Offload state dict to CPU
    )

    # Load the LoRA adapters
    model = PeftModel.from_pretrained(model, lora_model_path)

    # Move model to device (if not already handled by device_map)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)

    return tokenizer, model, device

# Riot API functions
def get_account_info(game_name, tag_line, api_key):
    """
    Retrieve account information using the Riot ID (gameName and tagLine).
    """
    # URL encode the gameName and tagLine
    game_name_encoded = requests.utils.quote(game_name)
    tag_line_encoded = requests.utils.quote(tag_line)
    url = f'https://americas.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{game_name_encoded}/{tag_line_encoded}'
    print(f"Accessing Account Info URL: {url}")
    response = requests.get(url, params={'api_key': api_key})
    return response

def get_current_game_info(puuid, api_key):
    """
    Retrieve current game information using the puuid.
    """
    # Using 'NA1' as the default platform region (uppercase)
    url = f'https://{PLATFORM_REGION}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}'
    print(f"Accessing Game Info URL: {url}")
    response = requests.get(url, params={'api_key': api_key})
    return response

def get_champion_data():
    """
    Retrieve champion data from Data Dragon.
    """
    version = get_latest_version()
    url = f'https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json'
    response = requests.get(url)
    return response.json()

def get_latest_version():
    """
    Get the latest version of the game from Data Dragon.
    """
    url = 'https://ddragon.leagueoflegends.com/api/versions.json'
    response = requests.get(url)
    versions = response.json()
    return versions[0]  # Latest version

def get_champion_name(champion_id, champion_data):
    """
    Retrieve champion name using champion ID.
    """
    for champ in champion_data['data'].values():
        if int(champ['key']) == champion_id:
            return champ['id']
    return "Unknown"

def calculate_next_dragon_spawn(game_info):
    """
    Calculate the time remaining until the next dragon spawn.
    """
    game_start_time = game_info.get('gameStartTime', 0)
    now = int(time.time() * 1000)  # Current time in milliseconds
    game_time_ms = now - game_start_time
    if game_time_ms < 0:
        game_time_ms = 0  # Prevent negative game time
    game_time = timedelta(milliseconds=game_time_ms)
    
    # Dragon spawn times in minutes
    dragon_spawn_times = [5, 10, 20, 25, 35, 40, 50, 55]
    
    # Calculate next dragon spawn
    current_minute = game_time.seconds // 60
    next_spawn = None
    for spawn in dragon_spawn_times:
        if spawn > current_minute:
            next_spawn = spawn - current_minute
            break
    
    if next_spawn is None:
        return "No more dragons for this game."
    else:
        return f"{next_spawn} minutes"

def calculate_game_time(game_info):
    """
    Calculate the current game time.
    """
    game_start_time = game_info.get('gameStartTime', 0)
    now = int(time.time() * 1000)  # Current time in milliseconds
    game_time_ms = now - game_start_time
    if game_time_ms < 0:
        game_time_ms = 0  # Prevent negative game time
    game_time = timedelta(milliseconds=game_time_ms)
    return str(game_time).split('.')[0]  # Format as HH:MM:SS

def extract_game_state(game_info, puuid, champion_data):
    """
    Extract relevant game state information for generating advice.
    """
    participants = game_info.get('participants', [])
    player_info = None
    champions_in_game = []

    for p in participants:
        # Collect all champions in the game
        champions_in_game.append(get_champion_name(p['championId'], champion_data))
        
        # Identify the player's participant info using puuid
        if p['puuid'] == puuid:
            player_info = p

    if not player_info:
        return None

    # Extract player-specific data
    player_champion = get_champion_name(player_info['championId'], champion_data)
    player_gold = player_info.get('goldEarned', 0)
    player_level = player_info.get('summonerLevel', 1)  # Adjust key based on actual data
    player_kills = player_info.get('kills', 0)
    player_deaths = player_info.get('deaths', 0)
    player_assists = player_info.get('assists', 0)
    # Assuming 'items' key contains item IDs or names; adjust based on actual data
    # Here, we mock it as an empty list since actual data structure may vary
    player_items = player_info.get('items', [])
    # Convert item IDs to names if possible
    player_items = [item.get('name', f"Item {item.get('id', 'Unknown')}") for item in player_items]
    # Assuming 'position' key exists; adjust based on actual data
    player_position = player_info.get('position', 'Unknown')

    # Construct a dictionary with all extracted data
    game_state = {
        'champions_in_game': champions_in_game,
        'player_champion': player_champion,
        'player_gold': player_gold,
        'player_level': player_level,
        'player_kills': player_kills,
        'player_deaths': player_deaths,
        'player_assists': player_assists,
        'player_items': player_items,
        'player_position': player_position,
        'next_dragon_spawn_in': calculate_next_dragon_spawn(game_info),
        'game_time': calculate_game_time(game_info),
        # Additional metrics can be added here
    }

    return game_state

def create_prompt(game_state):
    """
    Create a comprehensive prompt based on the game state.
    """
    if not game_state:
        return None

    champions = ", ".join(game_state['champions_in_game'])
    your_champion = game_state['player_champion']
    your_gold = game_state['player_gold']
    your_level = game_state['player_level']
    your_kills = game_state['player_kills']
    your_deaths = game_state['player_deaths']
    your_assists = game_state['player_assists']
    your_items = ", ".join(game_state['player_items']) if game_state['player_items'] else "None"
    your_position = game_state['player_position']
    next_dragon = game_state['next_dragon_spawn_in']
    game_time = game_state['game_time']

    # Conditional advice based on gold
    if game_state['player_gold'] > 1500:
        gold_advice = "You have a healthy gold lead. Consider itemizing aggressively and looking for objectives."
    elif game_state['player_gold'] < 800:
        gold_advice = "Your gold is low. Focus on farming safely and avoiding unnecessary deaths."
    else:
        gold_advice = "Maintain a balance between farming and assisting your team."

    # Champion-specific advice
    if game_state['player_champion'].lower() == "akali":
        champ_advice = "As Akali, focus on roaming mid and utilizing your mobility to catch out-of-position enemies."
    elif game_state['player_champion'].lower() == "ashe":
        champ_advice = "As Ashe, prioritize vision control and positioning to maximize your ranged damage in team fights."
    else:
        champ_advice = ""

    # Construct the prompt
    prompt = f"""
Game Time: {game_time}
Your Champion: {your_champion}
Current Gold: {your_gold}
Level: {your_level}
Kills/Deaths/Assists: {your_kills}/{your_deaths}/{your_assists}
Items: {your_items}
Position: {your_position}
Next Dragon Spawn In: {next_dragon}
Champions in Game: {champions}

{gold_advice}
{champ_advice}

Based on the current game state, provide strategic advice on the following:
1. Item purchases
2. When to back to base
3. Objective control (e.g., towers, dragons, Baron)
4. Team fight participation
5. Lane management

Please tailor your advice to optimize performance and game outcome.
Provide your advice in a numbered list format with clear and actionable steps.
Example:
1. Buy a Long Sword and Boots of Speed.
2. Do not push Barracks or Baron before level 6.
3. Do not push Dragon or Baron until level 6.
"""

    return prompt

def generate_advice(prompt, tokenizer, model, device):
    """
    Generate advice based on the prompt using the loaded model.
    """
    inputs = tokenizer(prompt, return_tensors="pt").to(device)
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=300,  # Increased token limit for more comprehensive advice
            do_sample=True,
            top_p=0.95,
            top_k=50,
            temperature=0.7,
            eos_token_id=tokenizer.eos_token_id,
            pad_token_id=tokenizer.pad_token_id,
        )
    # Explicitly set `clean_up_tokenization_spaces=True` in decode to suppress FutureWarning
    response = tokenizer.decode(outputs[0], skip_special_tokens=True, clean_up_tokenization_spaces=True)
    # Remove the prompt from the response
    return response[len(prompt):].strip()

# GUI Application Class
class LeagueAssistantGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("League Assistant")

        # Variables
        self.running = False
        self.thread = None
        self.tokenizer = None
        self.model = None
        self.device = None
        self.game_name = ""
        self.tag_line = ""
        self.api_key = ""
        self.champion_data = None
        self.settings_file = "settings.json"

        # Load settings
        self.load_settings()

        # Create GUI elements
        self.create_widgets()

        # Handle window close event to save settings
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        """
        Create and layout the GUI widgets.
        """
        # Game Name (Riot ID)
        tk.Label(self.root, text="Game Name (Riot ID):").grid(row=0, column=0, sticky="e")
        self.game_name_entry = tk.Entry(self.root, width=30)
        self.game_name_entry.grid(row=0, column=1)
        self.game_name_entry.insert(0, self.game_name)  # Load saved value

        # Tag Line (Riot ID)
        tk.Label(self.root, text="Tag Line (Riot ID):").grid(row=1, column=0, sticky="e")
        self.tag_line_entry = tk.Entry(self.root, width=30)
        self.tag_line_entry.grid(row=1, column=1)
        self.tag_line_entry.insert(0, self.tag_line)  # Load saved value

        # Update Interval
        tk.Label(self.root, text="Update Interval (seconds):").grid(row=2, column=0, sticky="e")
        self.update_interval_entry = tk.Entry(self.root, width=30)
        self.update_interval_entry.grid(row=2, column=1)
        self.update_interval_entry.insert(0, "10")  # Default to 10 seconds

        # API Key
        tk.Label(self.root, text="Riot API Key:").grid(row=3, column=0, sticky="e")
        self.api_key_entry = tk.Entry(self.root, width=30, show="*")
        self.api_key_entry.grid(row=3, column=1)
        self.api_key_entry.insert(0, self.api_key)  # Load saved value

        # Start and Stop Buttons
        self.start_button = tk.Button(self.root, text="Start Assistant", command=self.start_assistant)
        self.start_button.grid(row=4, column=0, pady=10)

        self.stop_button = tk.Button(self.root, text="Stop Assistant", command=self.stop_assistant, state=tk.DISABLED)
        self.stop_button.grid(row=4, column=1, pady=10)

        # Status Label
        self.status_label = tk.Label(self.root, text="Status: Idle")
        self.status_label.grid(row=5, column=0, columnspan=2)

        # Output Text Area
        self.output_text = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, width=60, height=20)
        self.output_text.grid(row=6, column=0, columnspan=2, padx=10, pady=10)

    def save_settings(self):
        """
        Save the input field values to a JSON file.
        """
        settings = {
            "game_name": self.game_name,
            "tag_line": self.tag_line,
            "api_key": self.api_key,
        }
        try:
            with open(self.settings_file, "w") as f:
                json.dump(settings, f)
            print("Settings saved successfully.")
        except Exception as e:
            print(f"Error saving settings: {e}")

    def load_settings(self):
        """
        Load the input field values from a JSON file if it exists.
        """
        if os.path.isfile(self.settings_file):
            try:
                with open(self.settings_file, "r") as f:
                    settings = json.load(f)
                    self.game_name = settings.get("game_name", "")
                    self.tag_line = settings.get("tag_line", "")
                    self.api_key = settings.get("api_key", "")
                print("Settings loaded successfully.")
            except Exception as e:
                print(f"Error loading settings: {e}")
                self.game_name = ""
                self.tag_line = ""
                self.api_key = ""
        else:
            self.game_name = ""
            self.tag_line = ""
            self.api_key = ""

    def on_closing(self):
        """
        Handle the window close event to save settings and stop the assistant if running.
        """
        if self.running:
            self.running = False
            self.thread.join()
        self.save_settings()
        self.root.destroy()

    def start_assistant(self):
        """
        Start the assistant by retrieving input values, saving settings, and launching the assistant thread.
        """
        self.game_name = self.game_name_entry.get().strip()
        self.tag_line = self.tag_line_entry.get().strip()
        self.api_key = self.api_key_entry.get().strip()

        if not self.game_name or not self.tag_line or not self.api_key:
            messagebox.showerror("Input Error", "Please fill in all fields.")
            return

        # Save settings
        self.save_settings()

        # Disable inputs and start button
        self.game_name_entry.config(state=tk.DISABLED)
        self.tag_line_entry.config(state=tk.DISABLED)
        self.update_interval_entry.config(state=tk.DISABLED)
        self.api_key_entry.config(state=tk.DISABLED)
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)

        # Start the assistant thread
        self.running = True
        self.thread = threading.Thread(target=self.run_assistant)
        self.thread.start()

    def stop_assistant(self):
        """
        Stop the assistant by updating the running flag and disabling the stop button.
        """
        self.running = False
        self.stop_button.config(state=tk.DISABLED)
        self.update_status("Stopping...")
        print("Assistant is stopping...")

    def sanitize_advice(self, advice):
        """
        Sanitize the model's advice to remove any unintended content like code snippets or HTML tags.
        """
        # Remove any code blocks
        import re
        advice = re.sub(r'```.*?```', '', advice, flags=re.DOTALL)
        # Remove HTML tags
        advice = re.sub(r'<[^>]+>', '', advice)
        # Remove any remaining code snippets or braces
        advice = re.sub(r'function\s+\w+\s*\([^)]*\)\s*\{[^}]*\}', '', advice)
        advice = re.sub(r'[\{\}*/]', '', advice)
        # Remove repetitive phrases
        advice = re.sub(r'(I can do better than that\.)+', 'I can provide more tailored advice.', advice)
        # Strip leading/trailing whitespace
        advice = advice.strip()
        return advice

    def run_assistant(self):
        """
        The main loop of the assistant that loads the model, retrieves account info,
        checks the current game state, and generates advice.
        """
        # Check if the trained model is available
        lora_model_path = "./results"  # Path where your fine-tuned LoRA adapters are saved
        if not check_model_exists(lora_model_path):
            self.update_status("Trained model not found at './results'.")
            print("Trained model not found at './results'.")
            self.enable_inputs()
            return

        self.update_status("Loading model...")
        print("Loading model...")
        try:
            # Load the model and tokenizer
            self.tokenizer, self.model, self.device = load_model(lora_model_path)
        except Exception as e:
            self.update_status(f"Error loading model: {e}")
            print(f"Error loading model: {e}")
            self.enable_inputs()
            return

        self.update_status("Loading champion data...")
        print("Loading champion data...")
        try:
            # Load champion data
            self.champion_data = get_champion_data()
        except Exception as e:
            self.update_status(f"Error loading champion data: {e}")
            print(f"Error loading champion data: {e}")
            self.enable_inputs()
            return

        # Get account info
        self.update_status("Retrieving account info...")
        print("Retrieving account info...")
        account_info_response = get_account_info(self.game_name, self.tag_line, self.api_key)
        # Debug: Print the account_info response
        try:
            account_info_json = account_info_response.json()
            print("Account Info Response:", account_info_json)
        except json.JSONDecodeError:
            account_info_json = {}
            print("Account Info Response: Invalid JSON")

        if account_info_response.status_code == 400:
            error_message = account_info_json.get('status', {}).get('message', 'Bad Request.')
            print(f"Error accessing Account Info endpoint: {error_message}")
            self.update_output(f"Error accessing Account Info endpoint: {error_message}\nSkipping to next step.\n")
            self.update_status("Skipping Account Info due to error.")
            # Skip further processing
            self.enable_inputs()
            return
        elif 'puuid' not in account_info_json:
            error_message = account_info_json.get('status', {}).get('message', 'Account not found or invalid API key.')
            print(f"Error accessing Account Info endpoint: {error_message}")
            self.update_output(f"Error accessing Account Info endpoint: {error_message}\nSkipping to next step.\n")
            self.update_status("Skipping Account Info due to error.")
            # Skip further processing
            self.enable_inputs()
            return

        puuid = account_info_json['puuid']
        # Construct riot_id as "gameName#tagLine"
        riot_id = f"{account_info_json.get('gameName', 'Unknown')}#{account_info_json.get('tagLine', '')}"

        while self.running:
            try:
                # Retrieve current game info
                self.update_status("Retrieving current game info...")
                print("Retrieving current game info...")
                game_info_response = get_current_game_info(puuid, self.api_key)
                # Debug: Print the game_info response
                try:
                    game_info_json = game_info_response.json()
                    print("Game Info Response:", game_info_json)
                except json.JSONDecodeError:
                    game_info_json = {}
                    print("Game Info Response: Invalid JSON")

                if game_info_response.status_code == 400:
                    error_message = game_info_json.get('status', {}).get('message', 'Bad Request.')
                    print(f"Error accessing Game Info endpoint: {error_message}")
                    self.update_output(f"Error accessing Game Info endpoint: {error_message}\nSkipping to next iteration.\n")
                    self.update_status("Skipping Game Info due to error.")
                    # Wait before next iteration
                    update_interval_str = self.update_interval_entry.get().strip()
                    try:
                        update_interval = int(update_interval_str)
                        if update_interval < 1:
                            raise ValueError
                    except ValueError:
                        update_interval = 5  # Fallback to 5 seconds
                        self.update_output("Invalid update interval. Using default of 5 seconds.\n")
                    for _ in range(update_interval):
                        if not self.running:
                            break
                        time.sleep(1)
                    continue

                if 'participants' not in game_info_json:
                    if 'status' in game_info_json and game_info_json['status']['status_code'] == 404:
                        message = "Not currently in a game. Checking again in 10 seconds...\n"
                        self.update_output(message)
                        print(message.strip())
                        self.update_status("Not in a game.")
                        # Wait before retrying
                        for _ in range(10):
                            if not self.running:
                                break
                            time.sleep(1)
                        continue
                    else:
                        message = "Unexpected response when retrieving game info. Skipping to next iteration.\n"
                        self.update_output(message)
                        print(message.strip())
                        self.update_status("Unexpected game info response.")
                        # Wait before next iteration
                        update_interval_str = self.update_interval_entry.get().strip()
                        try:
                            update_interval = int(update_interval_str)
                            if update_interval < 1:
                                raise ValueError
                        except ValueError:
                            update_interval = 5  # Fallback to 5 seconds
                            self.update_output("Invalid update interval. Using default of 5 seconds.\n")
                        for _ in range(update_interval):
                            if not self.running:
                                break
                            time.sleep(1)
                        continue

                game_info = game_info_json

                # Extract detailed game state
                game_state = extract_game_state(game_info, puuid, self.champion_data)

                if not game_state:
                    message = "Could not extract game state. Skipping to next iteration.\n"
                    self.update_output(message)
                    print(message.strip())
                    self.update_status("Could not extract game state.")
                    # Wait before next iteration
                    update_interval_str = self.update_interval_entry.get().strip()
                    try:
                        update_interval = int(update_interval_str)
                        if update_interval < 1:
                            raise ValueError
                    except ValueError:
                        update_interval = 5  # Fallback to 5 seconds
                        self.update_output("Invalid update interval. Using default of 5 seconds.\n")
                    for _ in range(update_interval):
                        if not self.running:
                            break
                        time.sleep(1)
                    continue

                # Create prompt with detailed game state
                prompt = create_prompt(game_state)
                if not prompt:
                    message = "Could not create prompt. Skipping to next iteration.\n"
                    self.update_output(message)
                    print(message.strip())
                    self.update_status("Could not create prompt.")
                    # Wait before next iteration
                    update_interval_str = self.update_interval_entry.get().strip()
                    try:
                        update_interval = int(update_interval_str)
                        if update_interval < 1:
                            raise ValueError
                    except ValueError:
                        update_interval = 5  # Fallback to 5 seconds
                        self.update_output("Invalid update interval. Using default of 5 seconds.\n")
                    for _ in range(update_interval):
                        if not self.running:
                            break
                        time.sleep(1)
                    continue

                # Generate advice
                self.update_status("Generating advice...")
                print("Generating advice...")
                advice = generate_advice(prompt, self.tokenizer, self.model, self.device)
                # Sanitize the advice to remove any code snippets or HTML tags
                advice = self.sanitize_advice(advice)
                message = f"Advice:\n{advice}\n"
                self.update_output(message)
                print(message.strip())

                # Wait before the next update
                update_interval_str = self.update_interval_entry.get().strip()
                try:
                    update_interval = int(update_interval_str)
                    if update_interval < 1:
                        raise ValueError
                except ValueError:
                    update_interval = 5  # Fallback to 5 seconds
                    self.update_output("Invalid update interval. Using default of 5 seconds.\n")
                for _ in range(update_interval):
                    if not self.running:
                        break
                    time.sleep(1)

            except Exception as e:
                message = f"An error occurred: {e}\nChecking again in 5 seconds...\n"
                self.update_output(message)
                print(message.strip())
                time.sleep(5)

        self.update_status("Assistant stopped.")
        print("Assistant stopped.")
        self.enable_inputs()

    def sanitize_advice(self, advice):
        """
        Sanitize the model's advice to remove any unintended content like code snippets or HTML tags.
        """
        # Remove any code blocks
        import re
        advice = re.sub(r'```.*?```', '', advice, flags=re.DOTALL)
        # Remove HTML tags
        advice = re.sub(r'<[^>]+>', '', advice)
        # Remove any remaining code snippets or braces
        advice = re.sub(r'function\s+\w+\s*\([^)]*\)\s*\{[^}]*\}', '', advice)
        advice = re.sub(r'[\{\}*/]', '', advice)
        # Remove repetitive phrases
        advice = re.sub(r'(I can do better than that\.)+', 'I can provide more tailored advice.', advice)
        # Strip leading/trailing whitespace
        advice = advice.strip()
        return advice

    def update_status(self, message):
        """
        Update the status label in the GUI.
        """
        def callback():
            self.status_label.config(text=f"Status: {message}")
        self.root.after(0, callback)

    def update_output(self, message):
        """
        Update the output text area in the GUI.
        """
        def callback():
            self.output_text.insert(tk.END, message)
            self.output_text.see(tk.END)
        self.root.after(0, callback)

    def enable_inputs(self):
        """
        Re-enable the input fields and start button after stopping the assistant.
        """
        def callback():
            self.game_name_entry.config(state=tk.NORMAL)
            self.tag_line_entry.config(state=tk.NORMAL)
            self.update_interval_entry.config(state=tk.NORMAL)
            self.api_key_entry.config(state=tk.NORMAL)
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
        self.root.after(0, callback)

# Main function to run the GUI
def main():
    root = tk.Tk()
    app = LeagueAssistantGUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
