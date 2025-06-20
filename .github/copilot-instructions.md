<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

This is a Home Assistant integration project for the 'pawfit' pet tracker. Use Home Assistant integration best practices, config flow (UI), and device tracker platform patterns. Only one account per instance, but multiple trackers per account. No YAML config, UI-only.

- When generating code, always expose the following attributes for each tracker entity: location accuracy, last time seen, and battery level.
- Credentials (username/password) must be stored locally and validated against the Pawfit API during config flow.
- Use a DataUpdateCoordinator for polling and updating tracker data.
- Reference the Context7 MCP regularly to read Home Assistant and integration documentation relevant to the implementation.
- Ask the user for clarification if the requirements are not clear or if additional features are needed beyond the initial scope.
- When making requests to the Pawfit API, always use the BASE_URL constant to build the URL and include the USER_AGENT constant in the request headers.
- After making changes, write a helpful commit message and run git push to update the repository.