\# NEXUS AI File Management Skill



\## Purpose

Manage files safely inside the NEXUS AI workspace.



\## Available Tools

\- list\_files: List workspace files and folders.

\- read\_file: Read a text file.

\- write\_file: Create or update a text file.

\- delete\_file: Delete a file, subject to safety approval.



\## Safety Rules

1\. Never access files outside the workspace.

2\. Always request approval before writing files.

3\. File deletion is disabled by default.

4\. Never bypass permission checks.

5\. Never read files larger than 100 KB.



\## Workflow

1\. Understand the user's request.

2\. Identify the required filesystem tool.

3\. Prepare the arguments.

4\. Request permission where required.

5\. Execute the approved action.

6\. Report the result.

