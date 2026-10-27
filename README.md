<div align="center">

<img src="assets/orix-mascot.png" alt="Agent Orix Mascot" width="280" />

# AGENT ORIX
### CavrixCode Agent Orix • Conversational Terminal AI • Multi-Action Agent Engine • Local-First Intelligence

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Conversational Scenarios](https://img.shields.io/badge/Conversational%20Scenarios-13%2F13%20Verified-brightgreen.svg)](#verified-conversational-scenarios)
[![Tools](https://img.shields.io/badge/Registered%20Tools-46-green.svg)](#registered-developer-tools)
[![Workflows](https://img.shields.io/badge/Domain%20Workflows-3%20Active-magenta.svg)](#multi-step-domain-workflows)
[![Security](https://img.shields.io/badge/HMAC%20Approval-Enforced-red.svg)](#security-and-human-approval-barrier)

```text
.eeeeee...eeeeee..eeeeee.eeeeeee..eeeeeeeee.....eeeeee..eeeeeee..eee.eee..eee....
@@@@@@@@:@@@@@@@@:@@@@@@:@@@@@@@@:@@@@@@@@@::::@@@@@@@@:@@@@@@@@:@@@:@@@::@@@::::
%%%--%%%-%%%------%%%----%%%--%%%----%%%-------%%%--%%%-%%%--%%%-%%%-%%%--%%%----
&&&&&&&&+&&&++++++&&&&&++&&&++&&&++++&&&+++++++&&&++&&&+&&&&&&&++&&&++&&&&&&+++++
||||||||*|||*||||*|||||**|||**|||****|||*******|||**|||*||||||***|||**||||||*****
!!!==!!!=!!!==!!!=!!!====!!!==!!!====!!!=======!!!==!!!=!!!=!!!==!!!=!!!==!!!====
:::##:::#::::::::#::::::#:::##:::####:::#######::::::::#:::##:::#:::#:::##:::####
...@@...@@......@@......@...@@...@@@@...@@@@@@@@......@@...@@...@...@...@@...@@@@
```

**Agent Orix** is a practical, conversational terminal-based AI assistant designed for real developer workflows, complex codebase operations, document synthesis, and multi-step tasks.

> **Conversation-First, Not Command-Driven:**  
> You do **not** need to memorize commands or flags. Just open Orix and talk to it in natural human language—like chatting with a senior engineer who has direct, safe access to your workspace tools.

</div>

---

## 💬 The Conversational Experience

When you launch `orix`, you are greeted by an interactive conversational partner:

```text
======================================================================
AGENT ORIX - Your AI-powered workspace
Type your request naturally, or use /help for optional shortcuts.
======================================================================

Hey! I'm Orix. What are we working on today?

You > explain this project to me

Orix >
 [Inspecting workspace...]
 [Reading important files...]
 [Analyzing project architecture...]

This repository is **Agent Orix**, a local-first conversational terminal AI engine.
It features:
- A conversational intent interpreter that executes real workspace actions from plain English.
- 46 registered developer tools spanning AST validation, git, document extraction, and file inspection.
- A cryptographic HMAC approval gate for modifying files or executing shell commands.
- 3 domain workflows for automated document intelligence, code repair, and research verification.

You > run the tests

Orix >
 [Locating test suites...]
 [Running pytest suite...]

Tests completed:
- tests/test_conversational_scenarios.py: 13 passed
- tests/test_phase18_orix_cli.py: 11 passed
Total: 24 passed in 18.2s. All systems green!

You > update the version in pyproject.toml to 1.1.0

Orix >
 [Generating diff for pyproject.toml...]

[Approval Request] Consequential Action Required
Tool: file_write_bounded
Target: pyproject.toml
Action: Update version to "1.1.0"
Token: 9e4f2b18...

Allow this action? [y/N]: y
 [Applying bounded file modification...]
pyproject.toml successfully updated to version 1.1.0.
```

---

## 🌟 Key Capabilities

- 🗣️ **Natural Language Intent Parsing**: Ask Orix to inspect repos, find bugs, trace functions, summarize documents, or run tests using everyday language.
- 🔄 **Contextual Follow-ups**: Seamlessly resolves conversational references like *"Do the first one"*, *"Explain that error"*, or *"Can you fix that too?"*.
- ⏱️ **Real-Time Step-by-Step Progress**: Transparent progress feedback (`[Inspecting workspace...]`, `[Reading important files...]`, `[Tracing application flow...]`) so you always know what Orix is doing.
- 🛡️ **Cryptographic Human Approval Barrier**: Consequential actions (file writing, shell execution, destructive tasks) require explicit user consent validated by HMAC-SHA256 replay-protected tokens.
- 🛑 **Graceful Interruptions & Recovery**: Safe handling of `Ctrl+C` cancellation, tool timeouts, and non-fatal runtime errors with contextual explanations.
- 🔒 **Zero-Trust File Containment**: Strict boundary checks prevent access outside authorized project directories, preventing path traversal attacks.
- 💾 **Session Continuity with Secret Redaction**: Conversation memory persists across sessions, while API keys, tokens, and passwords are automatically redacted.
- 🩺 **Built-in System Diagnostics (`orix doctor`)**: Instant verification of Python environment, host RAM/disk, Ollama service, model integrity, tool registry, and security gates.

---

## 🧪 Verified Conversational Scenarios

Agent Orix includes a comprehensive test suite (`tests/test_conversational_scenarios.py`) validating **13 distinct end-to-end conversational workflows**:

| Scenario | Objective | Status |
|---|---|---|
| **Scenario 1** | Normal conversation & multi-turn dialogue | Verified (PASS) |
| **Scenario 2** | Complex codebase inspection & explanation ("explain this project") | Verified (PASS) |
| **Scenario 3** | Contextual follow-up resolution ("explain the second file") | Verified (PASS) |
| **Scenario 4** | Autonomous file inspection with tool selection | Verified (PASS) |
| **Scenario 5** | File modification with cryptographic human approval prompt | Verified (PASS) |
| **Scenario 6** | Autonomous test runner & diagnostic reporting | Verified (PASS) |
| **Scenario 7** | Clean task interruption (`Ctrl+C` / cancel without corruption) | Verified (PASS) |
| **Scenario 8** | Runtime failure graceful recovery & transparent reporting | Verified (PASS) |
| **Scenario 9** | Unauthorized filesystem containment & path traversal defense | Verified (PASS) |
| **Scenario 10** | Rejection and containment of destructive operations (`rm -rf`) | Verified (PASS) |
| **Scenario 11** | Conversation session restoration and history recall | Verified (PASS) |
| **Scenario 12** | Remote authentication, bearer validation, and permission checks | Verified (PASS) |
| **Scenario 13** | Standalone installation, clean import readiness, and zero missing deps | Verified (PASS) |

---

## 🏗️ Architecture Overview

```
                                  +-----------------------+
                                  |   Agent Orix CLI      |
                                  |   (orix / orix chat)  |
                                  +-----------+-----------+
                                              |
                     +------------------------+------------------------+
                     |                                                 |
             [ Local Execution ]                               [ Remote Mode ]
                     |                                                 |
       +-------------v--------------+                    +-------------v--------------+
       |   Conversational Agent     |                    |    Remote CIE Backend      |
       |  (Natural Intent Parser)   |                    |    (FastAPI / Bearer Auth) |
       +-------------+--------------+                    +----------------------------+
                     |
       +-------------v--------------+
       | Anti-Sycophancy Gate       |
       +-------------+--------------+
                     |
       +-------------v--------------+
       | Dynamic Skill Selector     |
       +-------------+--------------+
                     |
       +-------------+------------------------------------+
       |                                                  |
+------v---------------------+                     +------v---------------------+
| 46 Registered Tools        |                     | 3 Domain Workflows         |
| (Code, Git, Search, Web)   |                     | (Doc, Codebase, Research)  |
+--------------+-------------+                     +--------------+-------------+
               |                                                  |
       +-------v--------------------------------------------------v-+
       |      Cryptographic Human Approval Gate (HMAC-SHA256)       |
       +----------------------------+-------------------------------+
                                    |
                            [ Safe Workspaces ]
```

---

## 🚀 Getting Started

### 1. Prerequisites

- **Python 3.10+ (64-bit)** ([python.org](https://www.python.org/downloads/)) - Ensure *"Add python.exe to PATH"* is checked during installation.
- **[Ollama](https://ollama.com/)** running locally with target model `cavrix-code:latest` (or your preferred local model).

---

### 2. Windows One-Click Installation (Recommended)

No complicated virtual environment setup or command-line gymnastics required:

1. **Clone or Download the Repository**:
   ```cmd
   git clone https://github.com/FaaizJohar/agent-orix.git
   cd agent-orix
   ```

2. **Run the One-Click Installer**:
   Double-click `Install-Orix.bat` (or run `.\Install-Orix.bat` from Command Prompt / PowerShell).

   **What `Install-Orix.bat` does automatically:**
   - Detects and verifies Python 3.10+ (64-bit).
   - Creates an isolated virtual environment (`.venv`) so your system Python is untouched.
   - Installs all dependencies in editable mode (`pip install -e .`).
   - Verifies the local Ollama service and `cavrix-code:latest` model (without downloading massive weights silently).
   - Generates the `run-orix.bat` desktop launcher and an optional Desktop shortcut.

3. **Start Conversing**:
   Double-click `run-orix.bat` or your Desktop shortcut!

> **Uninstallation**: Double-click `Uninstall-Orix.bat` at any time to cleanly remove `.venv`, generated launchers, and Desktop shortcuts.

---

### 3. Manual / Cross-Platform Installation (Linux & macOS)

For Linux, macOS, or manual setup:

```bash
git clone https://github.com/FaaizJohar/agent-orix.git
cd agent-orix

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies in editable mode
pip install -e .

# Run diagnostics
orix doctor
```

---

### 4. Verify System Health

Run the diagnostic suite to ensure all dependencies, tools, and models are operational:

```bash
# Using launcher
run-orix.bat doctor

# Or directly
orix doctor
```

Output:
```text
                         Agent Orix System Diagnostics                         
┌──────────┬────────────────────────────────┬─────────────────────────────────┐
│  Status  │ Component                      │ Details                         │
├──────────┼────────────────────────────────┼─────────────────────────────────┤
│   PASS   │ Python Version                 │ 3.11.9 (64-bit) - Supported     │
│   PASS   │ System Memory (RAM)            │ 5.90 GB total (Available: OK)   │
│   PASS   │ Disk Space (Current Drive)     │ 169.37 GB free                  │
│   PASS   │ Model Invariant (SHA-256)      │ Verified bitwise: 4A9F433D4E... │
│   PASS   │ Ollama Local Service           │ Online (cavrix-code:latest)     │
│   PASS   │ CIE Tool Registry              │ 46 registered tools available   │
│   PASS   │ Truth & Anti-Sycophancy Guard  │ Initialized                     │
│   PASS   │ HMAC Action Approval Engine    │ Active with replay protection   │
└──────────┴────────────────────────────────┴─────────────────────────────────┘
┌─────────────────────────────────────────────────────────────────────────────┐
│ [OK] All core systems operational and release-ready.                        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 💻 Usage Reference

### Launch Interactive Conversational Terminal

```bash
# Default interactive chat
orix

# Resume an existing session
orix chat --session-id <session_id>

# Run in script mode with single instruction
orix run "Summarize recent git commits"
```

### Optional Convenience Slash Commands

Commands are strictly optional conveniences. Everything can be requested in plain English:

- `/help` - Show quick cheat-sheet
- `/tools` - List registered skills and tools
- `/status` - Display engine and session status
- `/doctor` - Run system diagnostics
- `/history` - View recent message turns
- `/workflow <doc|code|research> <target>` - Directly trigger a domain workflow
- `/clear` - Clear terminal screen and reset context
- `/exit` or `/quit` - Cleanly exit the session

---

## 🛠️ Registered Developer Tools

Agent Orix includes **46 built-in developer tools**:

- **Code & Syntax**: `python_ast_validate`, `json_validate`, `yaml_validate`, `markdown_check`, `markdown_to_text`
- **Git & Version Control**: `git_status`, `git_diff_summary`, `file_tree_inspect`
- **File System & Search**: `file_read_text`, `file_search_text`, `file_write_bounded`
- **Document Intelligence**: `markitdown_convert`, `document_extract_text`, `paddleocr_detect`
- **Web & Extraction**: `crawl4ai_extract`, `web_fetch`, `web_search_rag`
- **Agent Capabilities**: `hermes_format_tool_call`, `swerex_execute`, `lightrag_query_graph`, `dspy_compile_signature`

Filter tools directly from the terminal:
```bash
orix tools list --category code
orix tools list --json-output
```

---

## 🔄 Multi-Step Domain Workflows

Agent Orix orchestrates complex end-to-end tasks with bounded checkpoints and state validation:

1. **Workflow A: Document Intelligence (`DOCUMENT_INTELLIGENCE`)**
   - High-throughput conversion of Markdown, PDF, HTML, DOCX, and XLSX using Microsoft MarkItDown.
   - Structural section identification and executive summary generation.

2. **Workflow B: Codebase Repair (`CODEBASE_REPAIR`)**
   - Isolated file inspection, AST validation, bounded patch application, and automatic rollback on syntax failure.

3. **Workflow C: Research & Verification (`RESEARCH_VERIFICATION`)**
   - Multi-source evidence gathering, cross-referencing, and factual grounding with citation preservation.

---

## 🔒 Security and Human Approval Barrier

Agent Orix adheres to a strict zero-trust local execution model:

- **Path Containment**: File access is strictly bound to authorized workspace directories. Path traversal attempts (`../../`) are blocked.
- **HMAC-SHA256 Action Tokens**: Every consequential action (writing files, executing shell tasks) produces an action-bound cryptographic token `H(secret, tool_name, arguments)`.
- **Replay Protection**: Approval tokens are consumed upon execution and stored in an in-memory set to prevent token reuse or replay attacks.
- **Secret Scrubbing**: API keys (`sk-...`, tokens, passwords) are automatically redacted in both UI rendering and on-disk session persistence.

---

## 📄 License

Agent Orix is open-source software licensed under the [MIT License](LICENSE).
