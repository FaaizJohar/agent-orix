<div align="center">

<img src="https://files.catbox.moe/r1sys4.png" alt="Agent Orix Mascot" width="280" />

# AGENT ORIX
### Interactive Terminal AI • Multi-Action Agent Engine • Local-First Intelligence

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tools](https://img.shields.io/badge/Registered%20Tools-46-green.svg)](#registered-developer-tools)
[![Workflows](https://img.shields.io/badge/Domain%20Workflows-3%20Active-magenta.svg)](#multi-step-domain-workflows)
[![Security](https://img.shields.io/badge/HMAC%20Approval-Enforced-red.svg)](#security-and-human-approval-barrier)

```text
  ___  ____  _____ _   _ _____    ___  ____  _____  __
 / _ \|  _ \|_   _| \ | |_   _|  / _ \|  _ \|_   _\ \/ /
| | | | |_) | | | |  \| | | |   | | | | |_) | | |  \  / 
| |_| |  _ < _| |_| |\  | | |   | |_| |  _ < _| |_ /  \ 
 \___/|_| \_\_____|_| \_| |_|    \___/|_| \_\_____/_/\_\
```

**Agent Orix** is a practical, production-grade, interactive terminal-based AI agent designed for developer workflows, complex codebase operations, document synthesis, and multi-step tasks. Powered by the **Cavrix Intelligence Engine (CIE)** and local LLM execution, Agent Orix combines high-speed deterministic routing, bounded multi-action planning, and a cryptographic human approval barrier for safe execution on local machines.

</div>

---

## 🌟 Key Features

- 💬 **Interactive Terminal Chat (`orix` / `orix chat`)**: Conversational REPL with rich markdown formatting, streaming, live status spinners, session continuity, and in-terminal slash commands.
- ⚡ **Multi-Action Agent Engine**: 46 registered developer tools and 3 multi-step automated workflows covering document extraction, codebase repair, and research verification.
- 🛡️ **Cryptographic Human Approval Barrier**: High-risk consequential actions (file writing, shell execution, desktop actions) require human authorization verified via HMAC-SHA256 replay-protected tokens.
- 🧠 **Anti-Sycophancy & Truth Preservation**: Built-in verification engine prevents sycophantic hallucinations and factually incorrect concessions.
- 💾 **Persistent Session Continuity**: Bounded conversation memory with automatic secret redaction (`sk-live-...`, tokens, passwords masked automatically).
- 🌐 **Remote Client Mode (`orix connect`)**: Connect to remote, authenticated CIE instances across devices without exposing private infrastructure.
- 🩺 **Built-in System Diagnostics (`orix doctor`)**: Instant verification of Python environment, host RAM/disk, Ollama service, model integrity, tool registry, and HMAC tokens.

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
       |   CIE Deterministic Router |                    |    Remote CIE Backend      |
       +-------------+--------------+                    |    (FastAPI / Bearer Auth) |
                     |                                   +----------------------------+
       +-------------v--------------+
       | Anti-Sycophancy Gate       |
       +-------------+--------------+
                     |
       +-------------v--------------+
       | Adaptive Planner & Engine  |
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

- Python 3.10 or higher (64-bit)
- [Ollama](https://ollama.com/) running locally with target model `cavrix-code:latest` (or compatible model).

### 2. Installation

Clone the repository and install in editable mode:

```bash
git clone https://github.com/FaaizJohar/agent-orix.git
cd agent-orix

# Install dependencies and console script
pip install -e .
```

*Windows Users:* You can immediately run `.\orix.bat` or `.\orix.ps1` from the project directory without installation!

### 3. Verify System Health

Run the diagnostic suite to ensure all dependencies, tools, and models are operational:

```bash
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

## 💻 CLI Command Reference

| Command | Description |
|---|---|
| `orix` or `orix chat` | Launch interactive terminal chat session |
| `orix run "<prompt>"` | Single-shot natural language instruction execution |
| `orix doctor` | Run comprehensive system diagnostics |
| `orix status` | View runtime metrics, memory, model, and tool status |
| `orix tools list` | View table of all 46 registered tools with permissions |
| `orix config` | Display active settings with secrets safely redacted |
| `orix sessions list` | List past conversation sessions and message history |
| `orix sessions clear <id>` | Delete a saved session |
| `orix connect <url>` | Test connection and latency to a remote CIE server |
| `orix --version` | Output version information |
| `orix --help` | View full command options |

### Launch Interactive Chat

```bash
# Default interactive chat
orix

# Resume an existing session
orix chat --session-id session_1793025452

# Suppress ASCII banner for clean scripting
orix chat --no-banner

# Display full mascot ASCII art
orix chat --mascot
```

### In-Chat Slash Commands

While in interactive mode, type slash commands directly into the prompt:

- `/help` - Show available commands
- `/tools` - List registered skills and tools
- `/status` - Display engine and session status
- `/doctor` - Run system diagnostics
- `/history` - View recent message turns
- `/workflow <doc|code|research> <target>` - Execute multi-step domain workflow
- `/clear` - Clear terminal screen and start fresh context
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
