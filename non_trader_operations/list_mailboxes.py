import subprocess
import json

def run_applescript(script):
    p = subprocess.Popen(['osascript', '-e', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    return out.decode('utf-8'), err.decode('utf-8')

def main():
    # Let's list accounts and their mailboxes
    script = """
    tell application "Mail"
        set accList to {}
        repeat with acc in accounts
            set accName to name of acc
            set mbList to {}
            repeat with mb in mailboxes of acc
                set mbName to name of mb
                set end of mbList to mbName
            end repeat
            set end of accList to {accName, mbList}
        repeat with mb in mailboxes
            set mbName to name of mb
            set end of accList to {"Global", mbName}
        end repeat
        return accList
    end tell
    """
    # Wait, let's do a simpler script that returns a clean string
    script = """
    tell application "Mail"
        set output to ""
        repeat with acc in accounts
            set accName to name of acc
            set output to output & "Account: " & accName & "\n"
            repeat with mb in mailboxes of acc
                set mbName to name of mb
                try
                    set msgCount to count of messages of mb
                    set output to output & "  Mailbox: " & mbName & " (" & msgCount & " messages)\n"
                on error
                    set output to output & "  Mailbox: " & mbName & " (error getting count)\n"
                end try
            end repeat
        end repeat
        repeat with mb in mailboxes
            set mbName to name of mb
            try
                set msgCount to count of messages of mb
                set output to output & "Global Mailbox: " & mbName & " (" & msgCount & " messages)\n"
            on error
                set output to output & "Global Mailbox: " & mbName & " (error getting count)\n"
            end try
        end repeat
        return output
    end tell
    """
    out, err = run_applescript(script)
    if err:
        print("Error:", err)
    else:
        print(out)

if __name__ == '__main__':
    main()
