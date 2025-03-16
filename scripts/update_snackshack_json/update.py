#!/usr/bin/env python3
"""
Script to update snackshack.json with data from SignUpGenius.
Uses environment variables for SignUpGenius credentials.
"""

import os
import json
import requests
import datetime
import pytz
import sys
import re
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# SignUpGenius API credentials
SIGNUP_ID = os.getenv("SIGNUP_ID")
API_KEY = os.getenv("API_KEY")
# Test date for debugging
TEST_DATE = os.getenv("TEST_DATE")
# Debug mode
DEBUG = os.getenv("DEBUG")

# Check the required environment variables are set
if not SIGNUP_ID or not API_KEY:
    print("Error: Both SIGNUP_ID and API_KEY environment variables must be set")
    print("Create a .env file with these variables or set them in your environment")
    sys.exit(1)

# Constants
BASE_URL = "https://api.signupgenius.com/v2/k"  # Removed trailing slash
REPORT_ENDPOINT = f"/signups/report/all/{SIGNUP_ID}/"
API_DOCS = "https://developer.signupgenius.com/developer/keybaseddocs"

# Calculate the path to the JSON file using os.path
script_dir = os.path.dirname(os.path.abspath(__file__))
repo_root = os.path.abspath(os.path.join(script_dir, "../.."))
JSON_FILE_PATH = Path(os.path.join(repo_root, "data", "snackshack.json"))
print(f"JSON file path: {JSON_FILE_PATH}")

# Snack shack locations
LOCATIONS = ["Madison", "Garfield", "Minor's Classic"]

# Signup URL template
SIGNUP_URL_TEMPLATE = "https://www.signupgenius.com/go/5080C44AEAB2EAAFF2-54832801-evll#/"

def get_signupgenius_data():
    """Fetch signup data from SignUpGenius API."""
    print(f"Fetching data from SignUpGenius API for signup ID: {SIGNUP_ID}")
    
    try:
        # Fix URL construction to avoid double slashes
        url = f"{BASE_URL}{REPORT_ENDPOINT}?user_key={API_KEY}"
        # print the url, hide the api key
        print(f"API URL: {url.replace(API_KEY, '********')}")
        
        response = requests.get(url)
        response.raise_for_status()  # Raise an exception for 4XX/5XX responses
        
        print(f"Successfully retrieved data from SignUpGenius API")
        data = response.json()
        
        # Debug: Print the structure of the response
        if DEBUG:
            print("API Response Structure:")
            if "data" in data:
                print(f"  - data keys: {list(data['data'].keys())}")
                if "signups" in data["data"]:
                    print(f"  - Number of signups: {len(data['data']['signups'])}")
                    if data["data"]["signups"]:
                        print(f"  - First signup keys: {list(data['data']['signups'][0].keys())}")
                elif "signup" in data["data"]:
                    if isinstance(data["data"]["signup"], list):
                        print(f"  - Number of signups: {len(data['data']['signup'])}")
                        if data["data"]["signup"]:
                            print(f"  - First signup keys: {list(data['data']['signup'][0].keys())}")
                    else:
                        print("  - Single signup object found")
            else:
                print(f"  - Response keys: {list(data.keys())}")
        
        return data
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from SignUpGenius API: {e}")
        raise

def determine_status(volunteer_count, max_volunteers):
    """Determine the status based on volunteer count."""
    if volunteer_count == 0:
        return "Closed"
    # If the volunteer count is at least max_volunteers, the grill is fully open
    elif volunteer_count >= max_volunteers:
        return "Fully Open"
    # If the volunteer count is 75% of max, the grill is open
    elif volunteer_count >= max_volunteers * 0.75:
        return "Grill open"
    else:
        return "Limited"

def extract_time_from_item(item):
    """Extract the time from the item description."""
    # Try to extract using regex
    time_pattern = re.compile(r'(\d+:\d+\s*(?:am|pm)?)\s*-\s*(\d+:\d+\s*(?:am|pm)?|close)', re.IGNORECASE)
    match = time_pattern.search(item)
    if match:
        time_range = match.group(0).strip()
        if DEBUG:
            print(f"  - Extracted time range: {time_range}")
        return time_range
    
    return None

def process_signups(signups_data):
    """Process the signups data and organize by time and location."""

    # Get today's date in Pacific time
    pacific = pytz.timezone('US/Pacific')
    today = datetime.datetime.now(pacific).date()
    today_str = today.strftime("%Y-%m-%d")
    
    # If TEST_DATE is set, use that instead
    if TEST_DATE:
        try:
            today = datetime.datetime.strptime(TEST_DATE, "%Y-%m-%d").date()
            today_str = TEST_DATE
            print(f"Using test date: {today_str}")
        except ValueError:
            print(f"Invalid TEST_DATE format: {TEST_DATE}. Using today's date instead.")
    
    print(f"Processing signups for today: {today_str}")
    
    # Initialize data structure
    processed_data = {
        "date": today_str,
        "times": []
    }
    
    # Check for the correct data structure
    signups = []
    if "data" in signups_data:
        if "signups" in signups_data["data"]:
            signups = signups_data["data"]["signups"]
        elif "signup" in signups_data["data"]:
            # Handle the case where the API returns 'signup' instead of 'signups'
            signup_data = signups_data["data"]["signup"]
            # Check if it's a list or a single item
            if isinstance(signup_data, list):
                signups = signup_data
            else:
                signups = [signup_data]
    
    print(f"Found {len(signups)} total signups in the data")
    
    # Debug: Print a sample of the first signup if available
    if DEBUG:
        if signups:
            print("Sample signup data:")
            sample_signup = signups[0]
            for key, value in sample_signup.items():
                print(f"  - {key}: {value}")
    
    # Find all available dates in the signups data
    available_dates = set()
    for signup in signups:
        # Try to extract date from various possible fields
        signup_date_str = None
        if 'startdatestring' in signup and signup['startdatestring']:
            # Extract just the date part from the string (e.g., "2025-04-02 07:00 GMT")
            date_parts = signup['startdatestring'].split(' ')
            if date_parts:
                signup_date_str = date_parts[0]
        elif 'startdate' in signup and signup['startdate']:
            # Convert timestamp to date string if needed
            try:
                timestamp = int(signup['startdate'])
                signup_date_str = datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass
        
        if signup_date_str:
            try:
                signup_date = datetime.datetime.strptime(signup_date_str, "%Y-%m-%d").date()
                available_dates.add(signup_date)
            except ValueError:
                pass
    
    # Sort the available dates
    sorted_dates = sorted(available_dates)
    
    # Find the target date (today or the first date after today with data)
    target_date = None
    for date in sorted_dates:
        if date >= today:
            target_date = date
            break
    
    # If no future dates are found, use today's date
    if not target_date:
        target_date = today
        print(f"No future dates with data found. Using today's date: {target_date}")
    else:
        print(f"Using target date: {target_date}")
    
    # Update the date in the processed data
    target_date_str = target_date.strftime("%Y-%m-%d")
    processed_data["date"] = target_date_str
    
    # Collect all time slots and organize signups by time and location
    time_slots = set()
    signup_details = {}
    max_volunteers_by_slot = {}
    
    # Track which locations have data for the target date
    locations_with_data = set()
    
    # First pass: collect all time slots and calculate max volunteers
    for signup in signups:
        # Extract relevant information
        # Debug the fields we're trying to extract
        if DEBUG:
            print(f"\nProcessing slotitemid: {signup.get('slotitemid', 'unknown')}")
            print(f"  - Date fields: startdate={signup.get('startdate')}, startdatestring={signup.get('startdatestring')}")
            print(f"  - Time fields: starttime={signup.get('starttime')}, endtime={signup.get('endtime')}")
            print(f"  - Item: {signup.get('item', '')}")
            print(f"  - Status: {signup.get('status', '')}")
            print(f"  - Quantity: {signup.get('myqty', '')}")
        
        # Try to extract date from various possible fields
        signup_date_str = None
        if 'startdatestring' in signup and signup['startdatestring']:
            # Extract just the date part from the string (e.g., "2025-04-02 07:00 GMT")
            date_parts = signup['startdatestring'].split(' ')
            if date_parts:
                signup_date_str = date_parts[0]
        elif 'startdate' in signup and signup['startdate']:
            # Convert timestamp to date string if needed
            try:
                timestamp = int(signup['startdate'])
                signup_date_str = datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d")
            except (ValueError, TypeError):
                pass
        
        if not signup_date_str:
            print(f"  - Could not determine date for slotitemid {signup.get('slotitemid', '')}, skipping. Go to {API_DOCS} for more information.")
            continue

        if DEBUG:
            print(f"  - Extracted date: {signup_date_str}")
        
        # Extract location and time from the item field
        item = signup.get('item', '')
        location = None
        
        # Try to extract location
        for loc in LOCATIONS:
            if loc in item:
                location = loc
                break
        
        if not location:
            print(f"  - Could not determine location for slotitemid {signup.get('slotitemid', '')}, skipping. Go to {API_DOCS} for more information.")
            continue
            
        # Try to extract time slot using the new function
        time_slot = extract_time_from_item(item)
        
        if not time_slot:
            print(f"  - Could not determine time slot for slotitemid {signup.get('slotitemid', '')}, skipping. Go to {API_DOCS} for more information.")
            continue
            
        # Check if the signup is for the target date
        try:
            signup_date = datetime.datetime.strptime(signup_date_str, "%Y-%m-%d").date()
            if signup_date != target_date:
                if DEBUG:
                    print(f"  - Signup date {signup_date} does not match target date {target_date}, skipping. Go to {API_DOCS} for more information.")
                continue
            
            # Add this time slot to our set of time slots
            time_slots.add(time_slot)
            
            # Initialize the data structure for this time slot and location if needed
            if time_slot not in signup_details:
                signup_details[time_slot] = {}
                max_volunteers_by_slot[time_slot] = {}
            
            if location not in signup_details[time_slot]:
                signup_details[time_slot][location] = {
                    "volunteer_count": 0,
                    "max_volunteers": 0  # Will be calculated as sum of all myqty values
                }
                max_volunteers_by_slot[time_slot][location] = 0
            
            # Get the quantity for this signup
            qty = int(signup.get("myqty", 0))
            
            # Add to max_volunteers (total of all myqty values)
            signup_details[time_slot][location]["max_volunteers"] += qty
            max_volunteers_by_slot[time_slot][location] += qty
            
            # Only count as volunteer if firstname is not empty
            if signup.get("firstname", "").strip():
                signup_details[time_slot][location]["volunteer_count"] += qty
                if DEBUG:
                    print(f"  - Adding {qty} volunteer(s) for {signup.get('firstname')} {signup.get('lastname')}")
            
            # Add this location to our set of locations with data
            locations_with_data.add(location)
            
            print(f"  - Valid signup for {location} at {time_slot}")
        except (ValueError, TypeError) as e:
            print(f"  - Error processing signup: {e}")
            continue
    
    print(f"Locations with data for {target_date_str}: {', '.join(locations_with_data) if locations_with_data else 'None'}")
    
    # Create the final data structure
    for time_slot in sorted(time_slots):
        time_data = {
            "time": time_slot,
            "snackshacks": []
        }
        
        for location in locations_with_data:
            if time_slot in signup_details and location in signup_details[time_slot]:
                volunteer_count = signup_details[time_slot][location]["volunteer_count"]
                max_volunteers = signup_details[time_slot][location]["max_volunteers"]
            else:
                volunteer_count = 0
                max_volunteers = 0  # Default if not specified
            
            status = determine_status(volunteer_count, max_volunteers)
            
            # Create a signup URL specific to this location and time slot if possible
            signup_url = SIGNUP_URL_TEMPLATE
            
            snackshack_data = {
                "name": location,
                "status": status,
                "volunteers": f"{volunteer_count}/{max_volunteers}",
                "signup": signup_url
            }
            
            time_data["snackshacks"].append(snackshack_data)
            print(f"  {time_slot} - {location}: {volunteer_count}/{max_volunteers} volunteers, Status: {status}")
        
        processed_data["times"].append(time_data)
    
    # If no time slots were found, create a default structure with only locations that have data
    if not time_slots:
        print(f"No time slots found for {target_date_str}. Creating default structure.")
        default_times = ["9:00am-11:15am", "11:15am-1:30pm", "1:30pm-3:45pm", "4:30pm-6:30pm"]
        for time_slot in default_times:
            time_data = {
                "time": time_slot,
                "snackshacks": []
            }
            
            # If no locations have data, don't add any snackshacks
            if not locations_with_data:
                print(f"  {time_slot} - No locations with data")
            else:
                for location in locations_with_data:
                    snackshack_data = {
                        "name": location,
                        "status": "Closed",
                        "volunteers": "0/0",
                        "signup": SIGNUP_URL_TEMPLATE
                    }
                    
                    time_data["snackshacks"].append(snackshack_data)
                    print(f"  {time_slot} - {location}: 0/0 volunteers, Status: Closed")
            
            processed_data["times"].append(time_data)
    
    return processed_data

def update_json_file(data):
    """Update the snackshack.json file with new data."""
    # Create directory if it doesn't exist
    JSON_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if the file exists and read its current contents
    if JSON_FILE_PATH.exists():
        try:
            with open(JSON_FILE_PATH, 'r') as f:
                current_data = json.load(f)
                print(f"Successfully read existing data from {JSON_FILE_PATH}")
        except json.JSONDecodeError:
            print(f"Warning: Existing file {JSON_FILE_PATH} contains invalid JSON. It will be overwritten.")
            current_data = None
    else:
        print(f"File {JSON_FILE_PATH} does not exist. Creating a new file.")
        current_data = None
    
    # Write the data to the file
    with open(JSON_FILE_PATH, 'w') as f:
        json.dump(data, f, indent=4)
    
    print(f"Updated {JSON_FILE_PATH} with new data")

def main():
    """Main function to update the snackshack.json file."""
    try:
        print("Starting snackshack.json update process")
        
        # Get data from SignUpGenius
        signups_data = get_signupgenius_data()
        
        # Process the data
        processed_data = process_signups(signups_data)
        
        # Update the JSON file
        update_json_file(processed_data)
        
        print("Update process completed successfully")
        return 0
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
