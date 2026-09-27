import subprocess
import json
import time

def run_applescript(script):
    p = subprocess.Popen(['osascript', '-e', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    return out.decode('utf-8'), err.decode('utf-8')

def main():
    # Let's write an AppleScript to dump first 5 contacts with their details
    script = """
    tell application "Contacts"
        set contactList to {}
        set plist to {}
        set max_contacts to 5
        set total_p to count of people
        if total_p < max_contacts then
            set max_contacts to total_p
        end if
        
        repeat with i from 1 to max_contacts
            set p to person i
            set p_id to id of p
            set p_first to first name of p
            if p_first is missing value then set p_first to ""
            set p_last to last name of p
            if p_last is missing value then set p_last to ""
            set p_org to organization of p
            if p_org is missing value then set p_org to ""
            set p_title to job title of p
            if p_title is missing value then set p_title to ""
            
            -- emails
            set email_list to {}
            repeat with em in emails of p
                set end of email_list to value of em
            end repeat
            
            -- phones
            set phone_list to {}
            repeat with ph in phones of p
                set end of phone_list to value of ph
            end repeat
            
            set end of plist to p_id & "||" & p_first & "||" & p_last & "||" & p_org & "||" & p_title & "||" & (email_list as string) & "||" & (phone_list as string)
        end repeat
        return plist
    end tell
    """
    start = time.time()
    out, err = run_applescript(script)
    end = time.time()
    print(f"Time taken: {end - start:.2f} seconds")
    if err:
        print("Error:", err)
    else:
        print("Output:\n", out)

if __name__ == '__main__':
    main()
