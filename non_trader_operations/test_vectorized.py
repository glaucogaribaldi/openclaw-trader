import subprocess
import time
import json

def run_as(prop):
    script = f'tell application "Contacts" to get {prop} of every person'
    p = subprocess.Popen(['osascript', '-e', script], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate()
    return out.decode('utf-8').strip()

def parse_as_list(text):
    # AppleScript lists are output as comma-separated values, e.g. "val1, val2, val3"
    # Or nested lists as "{val1, val2}, {val3}"
    # Since parsing this can be complex, let's look at JXA vectorized approach or a simpler way.
    pass

def main():
    start = time.time()
    # Let's see if we can use JXA vectorized properties.
    # We can write a JXA script that does the vectorized query, which returns standard JS arrays,
    # and then we can serialize it to JSON inside JS! That avoids any parsing issues and is extremely fast!
    jxa_vectorized = """
    var contacts = Application("Contacts");
    var people = contacts.people;
    
    var ids = people.id();
    var firstNames = people.firstName();
    var lastNames = people.lastName();
    var organizations = people.organization();
    var jobTitles = people.jobTitle();
    var notes = people.note();
    
    // For emails, phones, and addresses, let's fetch them in bulk for each person.
    // Wait, to do it efficiently without 1000 IPC calls, we can fetch all emails at once if JXA supports it:
    // var emails = people.emails.value(); 
    // Wait, if that fails, let's see how long a simplified loop takes if we only get what we need.
    // Or we can just run the loop on people but only for properties that are simple.
    // Let's test how fast the JXA loop is if we only fetch p.firstName(), p.lastName(), p.organization(), p.jobTitle()
    // and for emails/phones we use the vectorized properties if possible.
    """
    
    # Wait! Let's test if we can get emails of every person as a single nested list in AppleScript.
    script = 'tell application "Contacts" to get {id, first name, last name, organization, job title} of every person'
    # Let's run a test of JXA vectorized retrieval of emails
    jxa_test = """
    var contacts = Application("Contacts");
    var people = contacts.people();
    var results = [];
    for (var i = 0; i < people.length; i++) {
        var p = people[i];
        results.push({
            id: p.id(),
            first: p.firstName() || "",
            last: p.lastName() || ""
        });
    }
    JSON.stringify(results.slice(0, 5));
    """
    p = subprocess.Popen(['osascript', '-l', 'JavaScript'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(input=jxa_test.encode('utf-8'))
    print("JXA Test:", out.decode('utf-8'))

if __name__ == '__main__':
    main()
