# README.md
# Avakin

### Build, Modify, and Debug at the Speed of Thought.

<div align="center">
  <a href="https://buymeacoffee.com/snowballkori" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>
</div>
<br>
<div align="center">
  <img src="src/ava/assets/AvAkin.gif" alt="Avakin In Action" width="100%"/>
</div>

<div align="center">
  <img src="https://img.shields.io/badge/version-1.1.2-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/platform-windows-informational.svg" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-success.svg" alt="License">
</div>

Tired of the endless cycle of expensive API calls, context window limitations, and AI tools that don't truly understand your project's architecture?

Avakin is a complete, AI powered development environment that runs entirely on your local machine. It's not just a chatbot, it's a team of specialized AI agents. An Architect, a Coder, a Reviewer, and a Validator. Working together to bring your ideas to life. From a single prompt, Avakin can scaffold an entire multi-file application, surgically modify existing codebases, and intelligently debug errors with a single click.

## Core Features

   ⚡️ **Instant Project Scaffolding:** Go from a single sentence to a complete, runnable, multi-file Python project in seconds. Avakin designs the architecture, plans the files, and writes the code.
   
   ✍️ **Surgical Code Modification:** Make complex, context-aware changes to existing codebases using natural language.
   
   🪄 **One-Click Debugging:** When your code fails, a "Review & Fix" button appears. Avakin analyzes the full project context, git history, and error traceback to provide a precise, intelligent fix.
   
   🧠 **Dual-Context RAG Power:**
        *   **Project-Specific Knowledge:** Feed Avakin your project's GDD, specific documentation, or existing files to give it deep, contextual understanding *for that project*. Each project gets its own isolated knowledge base.
        *   **Global Knowledge Base:** Augment Avakin with a separate, global library of code examples, best practices, or any text-based knowledge to enhance its general Python expertise (path configured via `GLOBAL_RAG_DB_PATH` in your `.env` file or system environment).
   
   🔌 **Using Local LLMs with Ollama:**
        *   **Full Local Control:** Run powerful open-source models (like Llama 3, Mistral, CodeLlama, Phi, etc.) directly on your machine using [Ollama](https://ollama.com/).
        *   **Easy Setup:**
            1. Install Ollama(https://ollama.com/) and ensure it's running.
            2. Pull the models you want in your terminal of preference: `ollama pull llama3`, `ollama pull codellama`, etc.
            3. Avakin automatically discovers your running Ollama models.
            4. In Avakin's "Configure AI Models" dialog, select your desired Ollama models for each AI agent role (Architect, Coder, Chat, Reviewer).
        *   **Privacy & Offline:** Your prompts and code are processed locally, never leaving your system when using Ollama models.

   🔌 **Extensible Plugin System:** Avakin is built on a robust plugin architecture. Extend its capabilities, add new agents, or integrate with other tools. (More example plugins are on the way!)
   
   🔐 **100% Local & Private:** Your code and your API keys never leave your machine when using local LLMs. Avakin uses a local-first approach, giving you complete control and privacy without sacrificing power.
   
   🤖 **Customizable AI Team:** Configure which LLM (local via Ollama, or cloud-based) you want for each role. Use a massive model for architecture and a fast, cheap model for chat. You are in control.

## Why Avakin Exists

I built Avakin out of necessity. After a decade of teaching myself to code I wanted something I could use in my everyday workflow. Something that didnt cost a subscription, on top of API calls. 

With Avakin, I can build clients efficient, secure, robust python applications in a fraction of the time it would take with traditional methods.

## Getting Started (Running from Source)

Avakin is designed to be run directly from source, giving you full control.

**Prerequisites:**
*   Python 3.10 or newer.
*   Git.
*   **(Strongly Recommended for Local LLMs)** [Ollama](https://ollama.com/) installed and running. Download your desired models (e.g., `ollama pull llama3`).

**1. Clone the Repository**

First, clone the project to your local machine:
```bash
git clone https://github.com/carpsesdema/AvA_Kintsugi.git
cd AvA_Kintsugi
```
2. Install Dependencies
It's highly recommended to use a Python virtual environment.
   # Create and activate a virtual environment (optional but recommended)
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   # source .venv/bin/activate
       
   # Install the required packages
```bash
   pip install -r src/ava/requirements.txt
```
3. Configure API Keys & RAG (Optional but Recommended):
Create a file named .env in the root of the AvA_Kintsugi project directory (next to README.md).
Add your API keys if you plan to use cloud models:
```env
# .env file content
OPENAI_API_KEY="sk-..."
GEMINI_API_KEY="your_gemini_api_key"
ANTHROPIC_API_KEY="sk-ant-..."
# DEEPSEEK_API_KEY="your_deepseek_api_key"
# For the Global RAG Database (Optional but Recommended for full power)
# Path to a directory where your global knowledge base (e.g., code examples)
# will be stored by ChromaDB. Create this directory if it doesn't exist.
GLOBAL_RAG_DB_PATH="C:/YourKnowledgeBases/AvakinGlobalRAG" 
# Example for Linux/macOS: GLOBAL_RAG_DB_PATH="/Users/yourname/AvakinGlobalRAG"
```
If you don't create a .env file or don't add cloud API keys, Avakin will rely solely on your local Ollama models.
If GLOBAL_RAG_DB_PATH is not set, the global RAG features will be less effective until populated.
4. Launch!
Run the main application script from the root directory of the project:
```bash
python -m src/ava/main.py
```
You're ready to go! Configure your Ollama models in Avakin's settings if you haven't already.
Quick Usage
Create a New Project: Simply describe what you want to build in the chat prompt (ensure "Build" mode is toggled) and hit send.
Fix an Error: Run your code from the integrated terminal. When an error appears, click the "Review & Fix Code" button.
Add to RAG:
Project Knowledge: Use the "Add Project Files to RAG" or "Add External File to Project" buttons in the sidebar.
Global Knowledge: Use the "Add Global Docs" button to select a directory of code examples or documents to populate your GLOBAL_RAG_DB_PATH.
Support Avakin's Mission
Avakin is a labor of love from a solo developer. If this tool helps you build something amazing, saves you time, or just makes your coding life a little easier, please consider supporting its development. Every little bit helps me keep the lights on and continue making Avakin more powerful for everyone.
You can support the project via Buy Me a Coffee!
Contributing
Found a bug or have a feature request? Please open an issue! Pull requests are also welcome.
License
Avakin is licensed under the MIT License.
<p align="center">
<em>Now, go build something incredible.</em>
</p>
