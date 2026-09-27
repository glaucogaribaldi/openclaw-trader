import os
import pickle
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import gspread

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def main():
    creds = None
    token_path = os.path.expanduser('~/.openclaw/google_sheets_token.pickle')
    
    if os.path.exists(token_path):
        try:
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        except Exception as e:
            print(f"Error loading existing token: {e}")
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"Error refreshing token: {e}")
                creds = None
        
        if not creds:
            client_secret_path = '/Users/zava/Downloads/client_secret_285175947655-med24b4s26b81emoqm72kgkerm5tncsb.apps.googleusercontent.com.json'
            print(f"Using client secret: {client_secret_path}")
            
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            # run_local_server will launch the default browser
            print("Launching authentication browser flow...")
            creds = flow.run_local_server(port=0, prompt='consent')
            
        # Save credentials
        os.makedirs(os.path.dirname(token_path), exist_ok=True)
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
            print("Token saved successfully!")
            
    try:
        gc = gspread.authorize(creds)
        sh = gc.open_by_key('13CwUUUSh8WLITy0gmmfaRjgtv0in2ZsK1cPy82LO84w')
        print("Success! Authenticated successfully and opened spreadsheet.")
        print("Worksheets found:")
        for worksheet in sh.worksheets():
            print(f"- {worksheet.title}")
    except Exception as e:
        print(f"Failed to open spreadsheet with credentials: {e}")

if __name__ == '__main__':
    main()
