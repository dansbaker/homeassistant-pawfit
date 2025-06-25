<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

This is a Home Assistant integration project for the 'pawfit' pet tracker. Use Home Assistant integration best practices, config flow (UI), and device tracker platform patterns. Only one account per instance, but multiple trackers per account. No YAML config, UI-only.

## Development Guidelines

- When generating code, always expose the following attributes for each tracker entity: location accuracy, last time seen, and battery level.
- Credentials (username/password) must be stored locally and validated against the Pawfit API during config flow.
- Use a DataUpdateCoordinator for polling and updating tracker data.
- Reference the Context7 MCP regularly to read Home Assistant and integration documentation relevant to the implementation.
- Ask the user for clarification if the requirements are not clear or if additional features are needed beyond the initial scope.
- When making requests to the Pawfit API, always use the BASE_URL constant to build the URL and include the USER_AGENT constant in the request headers.

## Task Management & Official Integration Progress

**Primary Reference**: `OFFICIAL_INTEGRATION_REQUIREMENTS.md`

### Task Workflow (MANDATORY):
1. **Before starting any task**: Check the current Sprint and task priority in the requirements document
2. **During development**: Follow Home Assistant patterns and add comprehensive type hints
3. **After each task completion**:
   - Run all tests: `python -m pytest tests/ -v` (create tests/ directory if needed)
   - Run syntax check: `python3 -m py_compile custom_components/pawfit/*.py`
   - Update task status in `OFFICIAL_INTEGRATION_REQUIREMENTS.md` (mark with ✅ and add completion notes)
   - Git commit with format: `feat/fix/docs: [Sprint X] Task description (#issue)`
   - Push changes to feature branch

### Current Status: Sprint 1 - Foundation (Week 1-2)
**Active Tasks Priority:**
1. Phase 1.1: Code Structure & Standards (add type hints, fix PEP 8)
2. Phase 4.1: Set up pytest testing framework  
3. Phase 1.2: Integration Manifest Compliance
4. Phase 5.1-5.4: Entity Implementation Standards

### Quality Standards:
- **Type Hints**: Add to ALL functions, methods, and class attributes
- **Testing**: Write tests for EVERY new function/class
- **Documentation**: Add docstrings following Google/Sphinx format
- **Error Handling**: Use specific exceptions, not generic Exception
- **Async Patterns**: Use proper async/await throughout

### Git Workflow:
- Create feature branches: `sprint-1-foundation`, `sprint-2-testing`, etc.
- Commit frequently with descriptive messages
- Reference task numbers from requirements document
- Push to remote after each completed task

### Integration Target:
- **Goal**: Official Home Assistant integration (Silver tier quality minimum)
- **Timeline**: 12 weeks, 6 sprints
- **External Library**: Must extract API client to separate PyPI package
- **Test Coverage**: Minimum 90% required

### Community Engagement:
- Join Home Assistant Discord #devs_integrations channel
- Post integration progress and ask for guidance
- Follow Architecture Decision Records (ADRs)
- Submit PR draft early for community feedback