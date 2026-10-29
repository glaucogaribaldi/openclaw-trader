## Description: <br>
Delegates complex coding, research, and autonomous tasks between Clawdbot and Agent Zero with bidirectional messaging, file attachments, task breakdown, and progress reporting. <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[dowingard](https://clawhub.ai/user/dowingard) <br>

### License/Terms of Use: <br>
MIT <br>


## Use Case: <br>
Developers and operators use this skill to delegate complex coding, research, and long-running autonomous work from Clawdbot to Agent Zero. Agent Zero can report progress, ask questions, invoke Clawdbot tools, and create tracked task breakdown files. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: Agent Zero receives broad delegated control through the bridge and can send messages or tool requests back through Clawdbot. <br>
Mitigation: Install only when that delegation is intended, use a dedicated low-privilege gateway token when possible, and review Agent Zero requests before relying on them. <br>
Risk: Gateway and file-sharing paths can expose local services, attachments, secrets, or regulated data if configured too broadly. <br>
Mitigation: Prefer localhost or a private Docker network, avoid exposing the gateway on all interfaces, review every file passed with --attach, avoid sending secrets or regulated data, and reset context between unrelated tasks. <br>


## Reference(s): <br>
- [Agent Zero](https://github.com/frdel/agent-zero) <br>
- [Clawdbot](https://github.com/clawdbot/clawdbot) <br>
- [ClawHub skill page](https://clawhub.ai/dowingard/skills/agent-zero-bridge) <br>


## Skill Output: <br>
**Output Type(s):** [text, markdown, shell commands, configuration, guidance] <br>
**Output Format:** [Markdown guidance, shell commands, JSON status responses, and generated Markdown task files.] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [May read user-selected attachment files, persist an Agent Zero context ID, and create notebook task project files.] <br>

## Skill Version(s): <br>
1.0.0 (source: ClawHub release metadata) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>
