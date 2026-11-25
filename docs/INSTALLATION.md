# Installation Guide

## Windows
1. Install a supported Python version.
2. Open PowerShell in `C:\NEXUS-AI`.
3. Create a virtual environment if one does not already exist:
   `py -m venv .venv`
4. Activate it:
   `.\.venv\Scripts\Activate.ps1`
5. Install dependencies using the repository's dependency manifest, if present.
6. Install and start Ollama separately if local model inference is required.
7. Review local settings before starting NEXUS AI.

## Configuration
Keep local credentials in ignored files or secure storage. Never paste tokens into source files, commit them, or include them in logs.

## Verification
Run the test and compilation commands documented in the root README before launching the application.
