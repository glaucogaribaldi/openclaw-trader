import os
import pickle
import gspread

def main():
    token_path = os.path.expanduser('~/.openclaw/google_sheets_token.pickle')
    with open(token_path, 'rb') as token:
        creds = pickle.load(token)
    
    gc = gspread.authorize(creds)
    sh = gc.open_by_key('13CwUUUSh8WLITy0gmmfaRjgtv0in2ZsK1cPy82LO84w')
    
    # Read Istruzioni tab
    istr_ws = sh.worksheet('Istruzioni')
    print("=== Istruzioni ===")
    all_vals = istr_ws.get_all_values()
    for row in all_vals[:20]:
        print(", ".join([v for v in row if v]))
        
    print("\n=== Sheets & Headers ===")
    for ws in sh.worksheets():
        if ws.title == 'Istruzioni':
            continue
        vals = ws.get_all_values()
        print(f"\nSheet: {ws.title}")
        if len(vals) >= 4:
            # Row 4 is index 3 (0-based)
            print("Row 4 headers:", [v for v in vals[3] if v])
        else:
            print("Fewer than 4 rows, rows found:")
            for i, r in enumerate(vals):
                print(f"Row {i+1}:", [v for v in r if v])

if __name__ == '__main__':
    main()
