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
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from the script directory for local runs
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent
ENV_FILE_PATH = SCRIPT_DIR / ".env"
load_dotenv(ENV_FILE_PATH)

# SignUpGenius API credentials
SIGNUP_ID = os.getenv("SIGNUP_ID", "").strip()
API_KEY = os.getenv("API_KEY", "").strip()
SIGNUP_URL = os.getenv("SIGNUP_URL", "").strip()
# Test date for debugging
TEST_DATE = os.getenv("TEST_DATE", "").strip()
# Debug mode
DEBUG = os.getenv("DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

# Constants
BASE_URL = "https://api.signupgenius.com/v2/k"
API_DOCS = "https://developer.signupgenius.com/developer/keybaseddocs"
REQUEST_TIMEOUT_SECONDS = 30
MAX_FETCH_ATTEMPTS = 4
INITIAL_RETRY_DELAY_SECONDS = 2

# The Pacific time of the day that we should pull the next day's data
ROLLOVER_TIME = "20:00"

# Calculate the path to the JSON file
JSON_FILE_PATH = REPO_ROOT / "data" / "snackshack.json"

# Snack shack locations
LOCATIONS = ["Madison", "Garfield", "Minor's Classic"]


class UpstreamDataUnavailable(Exception):
    """Raised when SignUpGenius data cannot be reliably retrieved."""


def redact_text(value):
    """Redact sensitive values from logs."""
    if not value:
        return ""

    redacted = str(value)
    sensitive_values = [API_KEY, SIGNUP_ID]
    for sensitive in sensitive_values:
        if sensitive:
            redacted = redacted.replace(sensitive, "********")
    return redacted


def body_snippet(text, limit=300):
    """Return a trimmed and redacted one-line snippet for logging."""
    cleaned = " ".join((text or "").split())
    if len(cleaned) > limit:
        cleaned = f"{cleaned[:limit]}..."
    return redact_text(cleaned)


def log_failure_details(response, reason):
    """Log useful but redacted response diagnostics."""
    status = response.status_code if response is not None else "n/a"
    content_type = response.headers.get("Content-Type", "unknown") if response is not None else "unknown"
    response_text = response.text if response is not None else ""
    snippet = body_snippet(response_text)
    print(
        f"{reason}. HTTP status={status}, content-type={content_type}, "
        f"body-snippet='{snippet}'"
    )

def validate_config():
    """Ensure required environment variables are present."""
    missing = [
        name for name, value in (
            ("SIGNUP_ID", SIGNUP_ID),
            ("API_KEY", API_KEY),
            ("SIGNUP_URL", SIGNUP_URL),
        ) if not value
    ]

    if not missing:
        return True

    print(
        "Error: Missing required environment variables: "
        + ", ".join(missing)
    )
    print(
        "Set them in scripts/update_snackshack_json/.env for local runs or provide "
        "them through GitHub Actions. The public signup link should come from the "
        "SIGNUPGENIUS_SIGNUP_URL repository variable."
    )
    return False

def get_signupgenius_data():
    """Fetch signup data from SignUpGenius API."""
    print(f"Fetching data from SignUpGenius API for signup ID: {SIGNUP_ID}")

    report_endpoint = f"/signups/report/all/{SIGNUP_ID}/"
    url = f"{BASE_URL}{report_endpoint}?user_key={API_KEY}"
    headers = {"Accept": "application/json"}
    print(f"API URL: {url.replace(API_KEY, '********')}")

    retry_delay_seconds = INITIAL_RETRY_DELAY_SECONDS
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            response = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT_SECONDS)
        except requests.exceptions.RequestException as e:
            print(
                f"Attempt {attempt}/{MAX_FETCH_ATTEMPTS}: network error while fetching "
                f"SignUpGenius API data: {e}"
            )
            if attempt == MAX_FETCH_ATTEMPTS:
                raise UpstreamDataUnavailable("Network failure calling SignUpGenius API") from e
            print(f"Retrying in {retry_delay_seconds} seconds")
            time.sleep(retry_delay_seconds)
            retry_delay_seconds *= 2
            continue

        if 500 <= response.status_code <= 599:
            print(f"Attempt {attempt}/{MAX_FETCH_ATTEMPTS}: transient upstream 5xx response")
            log_failure_details(response, "SignUpGenius returned a transient 5xx response")
            if attempt == MAX_FETCH_ATTEMPTS:
                raise UpstreamDataUnavailable(
                    f"SignUpGenius API returned repeated 5xx responses ({response.status_code})"
                )
            print(f"Retrying in {retry_delay_seconds} seconds")
            time.sleep(retry_delay_seconds)
            retry_delay_seconds *= 2
            continue

        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError as e:
            log_failure_details(response, "SignUpGenius returned a non-retryable HTTP error")
            raise

        if not response.text or not response.text.strip():
            print(f"Attempt {attempt}/{MAX_FETCH_ATTEMPTS}: empty response body from SignUpGenius")
            log_failure_details(response, "SignUpGenius returned an empty response body")
            if attempt == MAX_FETCH_ATTEMPTS:
                raise UpstreamDataUnavailable("SignUpGenius returned repeated empty responses")
            print(f"Retrying in {retry_delay_seconds} seconds")
            time.sleep(retry_delay_seconds)
            retry_delay_seconds *= 2
            continue

        try:
            data = response.json()
        except json.JSONDecodeError as e:
            print(f"Attempt {attempt}/{MAX_FETCH_ATTEMPTS}: non-JSON response from SignUpGenius")
            log_failure_details(response, "SignUpGenius returned non-JSON response data")
            if attempt == MAX_FETCH_ATTEMPTS:
                raise UpstreamDataUnavailable("SignUpGenius returned repeated non-JSON responses") from e
            print(f"Retrying in {retry_delay_seconds} seconds")
            time.sleep(retry_delay_seconds)
            retry_delay_seconds *= 2
            continue

        print("Successfully retrieved data from SignUpGenius API")

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

    raise UpstreamDataUnavailable("Failed to retrieve SignUpGenius data after retries")

def determine_status(volunteer_count, max_volunteers):
    """Determine the status based on volunteer count."""
    if volunteer_count == 0:
        return "Need Volunteers"
    # If the volunteer count is at least max_volunteers, the grill is fully open
    elif volunteer_count >= max_volunteers:
        return "Fully Open"
    # Three volunteers is enough to open the grill for the current schedule format
    elif volunteer_count >= 3:
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

def extract_signup_date(signup, timezone):
    """Extract the signup date in Pacific time from a signup record."""
    if signup.get("startdatestring"):
        date_parts = signup["startdatestring"].split(" ")
        if date_parts:
            try:
                return datetime.datetime.strptime(date_parts[0], "%Y-%m-%d").date()
            except ValueError:
                return None

    if signup.get("startdate"):
        try:
            timestamp = int(signup["startdate"])
            return datetime.datetime.fromtimestamp(timestamp, tz=timezone).date()
        except (ValueError, TypeError, OSError):
            return None

    return None

def process_signups(signups_data):
    """Process the signups data and organize by time and location."""

    # Get the current date in Pacific time
    pacific = pytz.timezone('US/Pacific')
    # set the current date to today's date. If the current time is past the rollover time, set the current date to tomorrow
    current_date = datetime.datetime.now(pacific).date()
    if datetime.datetime.now(pacific).time() > datetime.datetime.strptime(ROLLOVER_TIME, "%H:%M").time():
        current_date = current_date + datetime.timedelta(days=1)
    current_str = current_date.strftime("%Y-%m-%d")
    
    # If TEST_DATE is set, use that instead
    if TEST_DATE:
        try:
            current_date = datetime.datetime.strptime(TEST_DATE, "%Y-%m-%d").date()
            current_str = TEST_DATE
            print(f"Using test date: {current_str}")
        except ValueError:
            print(f"Invalid TEST_DATE format: {TEST_DATE}. Using today's date instead.")
    
    print(f"Processing signups for today: {current_str}")
    
    # Initialize data structure
    processed_data = {
        "date": current_str,
        "locations": []
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
        signup_date = extract_signup_date(signup, pacific)
        if signup_date:
            available_dates.add(signup_date)
    
    # Sort the available dates
    sorted_dates = sorted(available_dates)
    
    # Find the target date (today or the first date after today with data)
    target_date = None
    for date in sorted_dates:
        if date >= current_date:
            target_date = date
            break
    
    # If no future dates are found, use today's date
    if not target_date:
        target_date = current_date
        print(f"No future dates with data found. Using today's date: {target_date}")
    else:
        print(f"Using target date: {target_date}")
    
    # Update the date in the processed data
    target_date_str = target_date.strftime("%Y-%m-%d")
    processed_data["date"] = target_date_str
    
    # Organize signups by time and location
    signup_details = {}
    
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
        
        signup_date = extract_signup_date(signup, pacific)

        if not signup_date:
            print(f"  - Could not determine date for slotitemid {signup.get('slotitemid', '')}, skipping. Go to {API_DOCS} for more information.")
            continue

        if DEBUG:
            print(f"  - Extracted date: {signup_date}")
        
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
            if signup_date != target_date:
                if DEBUG:
                    print(f"  - Signup date {signup_date} does not match target date {target_date}, skipping. Go to {API_DOCS} for more information.")
                continue
            
            # Initialize the data structure for this time slot and location if needed
            if time_slot not in signup_details:
                signup_details[time_slot] = {}
            
            if location not in signup_details[time_slot]:
                signup_details[time_slot][location] = {
                    "volunteer_count": 0,
                    "max_volunteers": 0  # Will be calculated as sum of all myqty values
                }
            
            # Get the quantity for this signup
            qty = int(signup.get("myqty", 0))
            
            # Add to max_volunteers (total of all myqty values)
            signup_details[time_slot][location]["max_volunteers"] += qty
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
    
    # Build the final output grouped by location
    locations_data = {}
    for location in locations_with_data:
        locations_data[location] = {"location": location, "times": []}
    
    # Populate times for each location
    for time_slot, locations in signup_details.items():
        for location, location_data in locations.items():
            if location in locations_with_data:
                volunteer_count = location_data["volunteer_count"]
                max_volunteers = location_data["max_volunteers"]
                status = determine_status(volunteer_count, max_volunteers)
                volunteer_string = f"{volunteer_count}/{max_volunteers}"
                
                # Add time data to the location
                time_data = {
                    "time": time_slot,
                    "status": status,
                    "volunteers": volunteer_string,
                    "signup": SIGNUP_URL
                }
                
                locations_data[location]["times"].append(time_data)
                print(f"  {location} - {time_slot}: {volunteer_string} volunteers, Status: {status}")
    
    # Add locations to the processed data
    for location in sorted(locations_data.keys()):
        processed_data["locations"].append(locations_data[location])
    
    # If no locations with data were found, create a default structure
    if not locations_with_data:
        print(f"No locations with data found for {target_date_str}. Creating default structure.")
        default_locations = LOCATIONS
        default_times = ["9:00am-11:15am", "11:15am-1:30pm", "1:30pm-3:45pm", "4:30pm-6:30pm"]
        
        for location in default_locations:
            location_data = {
                "location": location,
                "times": []
            }
            
            for time_slot in default_times:
                time_data = {
                    "time": time_slot,
                    "status": "Need Volunteers",
                    "volunteers": "0/0",
                    "signup": SIGNUP_URL
                }
                
                location_data["times"].append(time_data)
                print(f"  {location} - {time_slot}: 0/0 volunteers, Status: Need Volunteers")
            
            processed_data["locations"].append(location_data)
    
    return processed_data

def update_json_file(data):
    """Update the snackshack.json file with new data."""
    # Create directory if it doesn't exist
    JSON_FILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    # Check if the file exists and read its current contents
    if JSON_FILE_PATH.exists():
        try:
            with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                json.load(f)
                print(f"Successfully read existing data from {JSON_FILE_PATH}")
        except json.JSONDecodeError:
            print(f"Warning: Existing file {JSON_FILE_PATH} contains invalid JSON. It will be overwritten.")
    else:
        print(f"File {JSON_FILE_PATH} does not exist. Creating a new file.")
    
    # Write the data to the file
    with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)
        f.write("\n")
    
    print(f"Updated {JSON_FILE_PATH} with new data")


def has_last_known_good_json():
    """Return True when data/snackshack.json exists and parses as JSON."""
    if not JSON_FILE_PATH.exists():
        print(f"No fallback file available at {JSON_FILE_PATH}")
        return False

    try:
        with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
            json.load(f)
        print(f"Preserving last known good data in {JSON_FILE_PATH}")
        return True
    except json.JSONDecodeError:
        print(f"Fallback file exists but is invalid JSON: {JSON_FILE_PATH}")
        return False

def main():
    """Main function to update the snackshack.json file."""
    try:
        print("Starting snackshack.json update process")
        print(f"JSON file path: {JSON_FILE_PATH}")

        if not validate_config():
            return 1
        
        try:
            # Get data from SignUpGenius
            signups_data = get_signupgenius_data()
        except UpstreamDataUnavailable as e:
            print(f"Warning: {e}")
            if has_last_known_good_json():
                print("Completed with fallback data due to SignUpGenius upstream instability")
                return 0
            print("No valid fallback data available; failing update")
            return 1
        
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
