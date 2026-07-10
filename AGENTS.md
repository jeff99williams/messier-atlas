# Project working preferences

- Always use the project's local Python environment in `.venv`.
- Projects almost always run in a container; ask whether the user wants the application containerized.
- Projects almost always run as Azure web applications, so account for behavioral differences between local and Azure environments.
- Local browser testing is allowed without asking first.
- After working on an application, leave its local development server running so the user can test it. Report the URL in the final response.
- When the user says to "make a note," update the applicable `AGENTS.md` with that information.
