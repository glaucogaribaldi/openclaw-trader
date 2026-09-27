import subprocess
import json
import time

def main():
    start = time.time()
    jxa_script = """
    var contacts = Application("Contacts");
    var people = contacts.people;
    
    // Bulk fetch simple properties
    var ids = people.id();
    var firstNames = people.firstName();
    var lastNames = people.lastName();
    var organizations = people.organization();
    var jobTitles = people.jobTitle();
    var notes = people.note();
    
    // Bulk fetch multi-value lists
    var emails = people.emails.value();
    var phones = people.phones.value();
    
    // Bulk fetch addresses
    // JXA: people.addresses is a list of lists of address objects.
    // Let's see if we can get properties of addresses.
    var streets = [];
    var cities = [];
    var countries = [];
    try {
        streets = people.addresses.street();
        cities = people.addresses.city();
        countries = people.addresses.country();
    } catch(e) {
        // Fallback or ignore
    }
    
    // Bulk fetch groups
    var groups = contacts.groups();
    var group_map = {};
    for (var g = 0; g < groups.length; g++) {
        var group = groups[g];
        var g_name = group.name() || "";
        try {
            var g_ids = group.people.id();
            for (var p_idx = 0; p_idx < g_ids.length; p_idx++) {
                var pid = g_ids[p_idx];
                if (!group_map[pid]) {
                    group_map[pid] = [];
                }
                group_map[pid].push(g_name);
            }
        } catch(e) {}
    }
    
    var results = [];
    for (var i = 0; i < ids.length; i++) {
        var pid = ids[i];
        results.push({
            id: pid,
            firstName: firstNames[i] || "",
            lastName: lastNames[i] || "",
            organization: organizations[i] || "",
            jobTitle: jobTitles[i] || "",
            note: notes[i] || "",
            emails: emails[i] || [],
            phones: phones[i] || [],
            streets: streets[i] || [],
            cities: cities[i] || [],
            countries: countries[i] || [],
            groups: group_map[pid] || []
        });
    }
    
    JSON.stringify(results);
    """
    
    p = subprocess.Popen(['osascript', '-l', 'JavaScript'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(input=jxa_script.encode('utf-8'))
    end = time.time()
    print(f"Time taken: {end - start:.2f} seconds")
    if err and err.strip():
        print("Error:", err.decode('utf-8'))
    else:
        contacts = json.loads(out.decode('utf-8'))
        print(f"Fetched {len(contacts)} contacts.")
        print("Sample with emails/phones/groups/addresses:")
        found = False
        for c in contacts:
            if len(c['emails']) > 0 or len(c['phones']) > 0:
                print(json.dumps(c, indent=2))
                found = True
                break
        if not found and contacts:
            print(json.dumps(contacts[0], indent=2))

if __name__ == '__main__':
    main()
