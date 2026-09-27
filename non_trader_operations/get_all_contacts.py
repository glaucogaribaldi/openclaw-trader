import subprocess
import json
import time

def fetch_contacts_jxa():
    jxa_script = """
    var contacts = Application("Contacts");
    var people = contacts.people();
    var results = [];
    
    // Fetch all people and their details
    for (var i = 0; i < people.length; i++) {
        var p = people[i];
        
        // Emails
        var emails = p.emails();
        var email_list = [];
        for (var j = 0; j < emails.length; j++) {
            email_list.push({
                value: emails[j].value() || "",
                label: emails[j].label() || ""
            });
        }
        
        // Phones
        var phones = p.phones();
        var phone_list = [];
        for (var j = 0; j < phones.length; j++) {
            phone_list.push({
                value: phones[j].value() || "",
                label: phones[j].label() || ""
            });
        }
        
        // Addresses
        var addresses = p.addresses();
        var addr_list = [];
        for (var j = 0; j < addresses.length; j++) {
            var addr = addresses[j];
            addr_list.push({
                street: addr.street() || "",
                city: addr.city() || "",
                state: addr.state() || "",
                zip: addr.zip() || "",
                country: addr.country() || "",
                label: addr.label() || ""
            });
        }
        
        results.push({
            id: p.id(),
            firstName: p.firstName() || "",
            lastName: p.lastName() || "",
            organization: p.organization() || "",
            jobTitle: p.jobTitle() || "",
            note: p.note() || "",
            emails: email_list,
            phones: phone_list,
            addresses: addr_list,
            groups: []
        });
    }
    
    // Fetch all groups and map members to group names
    var groups = contacts.groups();
    var group_map = {};
    for (var g = 0; g < groups.length; g++) {
        var group = groups[g];
        var g_name = group.name() || "";
        var g_people = group.people();
        for (var p_idx = 0; p_idx < g_people.length; p_idx++) {
            var p_id = g_people[p_idx].id();
            if (!group_map[p_id]) {
                group_map[p_id] = [];
            }
            group_map[p_id].push(g_name);
        }
    }
    
    // Add groups to people
    for (var i = 0; i < results.length; i++) {
        var pid = results[i].id;
        if (group_map[pid]) {
            results[i].groups = group_map[pid];
        }
    }
    
    JSON.stringify(results);
    """
    
    p = subprocess.Popen(['osascript', '-l', 'JavaScript'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(input=jxa_script.encode('utf-8'))
    if err and err.strip():
        print("JXA Error:", err.decode('utf-8'))
        return []
    
    try:
        return json.loads(out.decode('utf-8'))
    except Exception as e:
        print("JSON parse error:", e)
        print("Raw output sample:", out.decode('utf-8')[:500])
        return []

def main():
    start = time.time()
    contacts = fetch_contacts_jxa()
    end = time.time()
    print(f"Fetched {len(contacts)} contacts in {end - start:.2f} seconds.")
    if contacts:
        print("Sample contact:", json.dumps(contacts[0], indent=2))

if __name__ == '__main__':
    main()
