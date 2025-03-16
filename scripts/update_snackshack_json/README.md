# Snack Shack JSON Updater

This script updates the `data/snackshack.json` file with data from SignUpGenius. It fetches volunteer signup information for today (Pacific time) and updates the JSON file with the current status of each snack shack location.

## Setup

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your SignUpGenius credentials:
   ```
   SIGNUP_ID=your_signup_id
   API_KEY=your_user_key
   ```

   You can obtain these credentials from your SignUpGenius account:
   - The `SIGNUP_ID` is the unique identifier for your signup form
   - The `API_KEY` is your API key from SignUpGenius

## Usage

Run the script:
```bash
python update.py
```

This will:
1. Fetch data from SignUpGenius for today's date (Pacific time)
2. Process the data to determine the status of each snack shack location
3. Update the `data/snackshack.json` file with the current information

## SignUpGenius response

The SignUpGenius API returns a JSON object with the following structure:

```json
{
  "data": {
    "customquestions": [
      {
        "customfieldid": 0,
        "title": "string"
      }
    ],
    "signups": [
      {
        "address1": "string",
        "address2": "string",
        "amountpaid": "string",
        "city": "string",
        "country": "string",
        "customfields": [
          {
            "customfieldid": 0,
            "value": "string"
          }
        ],
        "enddate": 0,
        "enddatestring": 0,
        "endtime": 0,
        "firstname": "string",
        "signupid": 0,
        "item": "string",
        "lastname": "string",
        "myqty": 0,
        "phone": "string",
        "phonetype": "string",
        "startdate": 0,
        "startdatestring": 0,
        "starttime": 0,
        "state": "string",
        "status": "string",
        "zipcode": "string",
        "itemmemberid": 0,
        "slotitemid": 0
      }
      // ... more signups
    ]
  },
  "message": [
    "string"
  ],
  "success": false
}
```

## data/snackshack.json JSON Structure

The script maintains the following JSON structure:

```json
{
    "date": "YYYY-MM-DD",
    "times": [
        {
            "time": "10:00 AM",
            "snackshacks": [
                {
                    "name": "Madison",
                    "status": "Grill open",
                    "volunteers": "3/4",
                    "signup": "https://signup.com/go/your_signup_id"
                },
                {
                    "name": "Garfield",
                    "status": "Limited",
                    "volunteers": "1/4",
                    "signup": "https://signup.com/go/your_signup_id"
                }
            ]
        },
        // Additional time slots...
    ]
}
```

## Status Determination

The status of each snack shack is determined by the number of volunteers:
- "Need Volunteers" - 0 volunteers
- "Limited" - 1-2 volunteers (half or less capacity)
- "Grill open" - 3 volunteers (more than half capacity)
- "Fully Open" - 4 volunteers (full capacity)

## Automation

This script can be scheduled to run every 15 minutes using github actions to keep the snack shack information up to date.
