## Description: <br>
Automates, tests, and debugs browsers with Playwright, including locators, auto-waiting, traces, CI runs, and MCP browser control. <br>

This skill is ready for commercial/non-commercial use. <br>

## Publisher: <br>
[ivangdavila](https://clawhub.ai/user/ivangdavila) <br>

### License/Terms of Use: <br>
MIT-0 <br>


## Use Case: <br>
Developers and QA engineers use this skill to write, repair, debug, and migrate Playwright browser automation, including flaky tests, authentication setup, CI artifacts, accessibility checks, MCP browsing, and bounded extraction from rendered pages. <br>

### Deployment Geography for Use: <br>
Global <br>

## Known Risks and Mitigations: <br>
Risk: Browser automation can act on authenticated sessions, production systems, payment flows, deletion flows, and email sends. <br>
Mitigation: Prefer local or staging targets, require explicit user approval for production or destructive actions, and keep real accounts scoped to throwaway tenants. <br>
Risk: Playwright storage state, traces, videos, and reports can contain credentials, tokens, cookies, or personal data. <br>
Mitigation: Store auth state only in gitignored paths, avoid printing secrets, treat CI artifacts as sensitive, and cap retention for traces and videos. <br>
Risk: Scraping workflows can over-collect data or exceed the user's intended scope. <br>
Mitigation: Keep extraction bounded to the named target, use throttling, honor the user's stated limits, and avoid broad collection unless explicitly requested. <br>


## Reference(s): <br>
- [ClawHub skill page](https://clawhub.ai/ivangdavila/skills/playwright) <br>
- [Clawic Playwright skill page](https://clawic.com/skills/playwright) <br>


## Skill Output: <br>
**Output Type(s):** [text, markdown, code, shell commands, configuration, guidance] <br>
**Output Format:** [Markdown guidance with code blocks, shell commands, configuration snippets, and checklists] <br>
**Output Parameters:** [1D] <br>
**Other Properties Related to Output:** [May produce Playwright specs, configuration, automation scripts, MCP commands, test diagnostics, and scraping plans.] <br>

## Skill Version(s): <br>
1.0.4 (source: evidence release and SKILL.md frontmatter) <br>

## Ethical Considerations: <br>
Users should evaluate whether this skill is appropriate for their environment, review any generated or modified files before relying on them, and apply their organization's safety, security, and compliance requirements before deployment. <br>
