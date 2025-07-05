# Avakin: Your AI Partner for Planning, Building, and Modifying Code.

Tired of wrestling with vague prompts and getting code that doesn't match your vision? Avakin is a complete, local-first AI development environment that understands that great software starts with a great plan. It introduces a unique two-phase workflow: a creative **Plan** mode and a technical **Build** mode, letting you go from a simple idea to a complete, multi-file application with unparalleled precision.

Stop trying to write the perfect prompt. Instead, have a conversation.

<div align="center">
  <img src="src/ava/assets/AvAkin.gif" alt="Avakin In Action" width="100%"/>
</div>
<br>
<div align="center">
  <a href="https://buymeacoffee.com/snowballkori" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>
</div>
<br>
<div align="center">
  <img src="https://img.shields.io/badge/version-1.2.1-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/platform-windows-informational.svg" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-success.svg" alt="License">
</div>

## The Avakin Workflow: Plan, then Build

Avakin splits the development process into two distinct, powerful phases.

### **Phase 1: Plan with Aura (Your Creative Partner)** 🎨
Toggle into **Plan Mode** and chat with Aura, your creative AI assistant. Don't worry about technical jargon. Just talk about your idea. Aura will:
- **Ask clarifying questions** to understand your core goals.
- **Brainstorm features** and suggest technical approaches.
- **Analyze images or diagrams** you provide for context.
- **Collaboratively produce a detailed technical blueprint** for the AI coding team.

### **Phase 2: Build with Precision (The AI Engineering Team)** 🛠️
Once you're happy with the plan, toggle into **Build Mode**. Avakin's team of specialized AI agents (Architect, Coder, Reviewer) takes over, turning the blueprint into reality. This team will:
- **Scaffold an entire multi-file application** based on the blueprint.
- **Surgically modify existing codebases** with pinpoint accuracy.
- **Intelligently debug errors** with a single click, understanding the full project context.

This unique workflow ensures the final code is not just functional, but a true reflection of your refined vision.

## Core Features

⚡️ **Intelligent Development Cycle:**
   - **Project Scaffolding:** Go from a single sentence to a complete, runnable, multi-file project in seconds.
   - **Surgical Code Modification:** Make complex, context-aware changes to existing codebases using natural language.
   - **One-Click Debugging:** When your code fails, a "Review & Fix" button appears. Avakin analyzes the full project context, git history, and error traceback to provide a precise, intelligent fix.

🧠 **Deep Project Understanding (Dual-Context RAG):**
   - **Project-Specific Knowledge:** Feed Avakin your project's GDD, specific documentation, or existing files to give it deep, contextual understanding *for that project*. Each project gets its own isolated knowledge base.
   - **Global Knowledge Base:** Augment Avakin with a separate, global library of code examples, best practices, or any text-based knowledge to enhance its general expertise (path configured via `GLOBAL_RAG_DB_PATH` in your `.env` file).

🔌 **Powered by Your Choice of LLMs (Local First):**
   - **Full Local Control with Ollama:** Run powerful open-source models (like Llama 3, Mistral, CodeLlama) directly on your machine using [Ollama](https://ollama.com/). Avakin automatically discovers and integrates with your running Ollama instance.
   - **Cloud Model Integration:** Seamlessly connect to your OpenAI, Google Gemini, and Anthropic API keys.
   - **Customizable AI Team:** Configure which LLM (local or cloud) you want for each role. Use a massive model for architecture and a fast, cheap model for chat. You are in control.

🔐 **100% Local & Private:**
   - When using Ollama, your code, your prompts, and your knowledge bases never leave your machine.

🔌 **Extensible Plugin System:**
   - Avakin is built on a robust plugin architecture. Extend its capabilities, add new agents, or integrate with other tools. (More example plugins are on the way!)

## Why Avakin Exists

I built Avakin out of necessity. After a decade of teaching myself to code, I wanted something I could use in my everyday workflow—something that didn't cost a subscription on top of expensive API calls. With Avakin, I can build clients efficient, secure, and robust applications in a fraction of the time it would take with traditional methods.

## Getting Started (Running from Source)

Avakin is designed to be run directly from source, giving you full control.

**Prerequisites:**
*   Python 3.10 or newer.
*   Git.
*   **(Strongly Recommended for Local LLMs)** [Ollama](https://ollama.com/) installed and running. Download your desired models (e.g., `ollama pull llama3`).

**1. Clone the Repository**
```bash
    git clone https://github.com/carpsesdema/AvA_Kintsugi.git
    cd AvA_Kintsugi
```
**2. Install Dependencies**
* It's highly recommended to use a Python virtual environment.
```bash
* # Create and activate a virtual environment (optional but recommended)
    python -m venv .venv
    # On Windows:
    .venv\Scripts\activate
    # On macOS/Linux:
    # source .venv/bin/activate
       
    # Install the required packages
    pip install -r src/ava/requirements.txt
   ```

**3. Configure API Keys & RAG (Optional but Recommended):**
Create a file named .env in the root of the AvA_Kintsugi project directory.
Add your API keys if you plan to use cloud models:
```bash
# .env file content
OPENAI_API_KEY="sk-..."
GEMINI_API_KEY="your_gemini_api_key"
ANTHROPIC_API_KEY="sk-ant-..."

# For the Global RAG Database (Optional but Recommended for full power)
# Path to a directory where your global knowledge base (e.g., code examples)
# will be stored. Create this directory if it doesn't exist.
GLOBAL_RAG_DB_PATH="C:/YourKnowledgeBases/AvakinGlobalRAG" 
# Example for Linux/macOS: GLOBAL_RAG_DB_PATH="/Users/yourname/AvakinGlobalRAG"
```
* If you don't create a .env file or add cloud API keys, Avakin will rely solely on your local Ollama models.
* If GLOBAL_RAG_DB_PATH is not set, the global RAG features will be less effective.

**4. Launch!**
*Run the main application script from the root directory of the project:
```bash
  python -m src/ava/main.py
```

You're ready to go! Configure your desired models in Avakin's "Configure AI Models" dialog.
Support Avakin's Mission
Avakin is a labor of love from a solo developer. If this tool helps you build something amazing, saves you time, or just makes your coding life a little easier, please consider supporting its development. Every little bit helps me keep the lights on and continue making Avakin more powerful for everyone.
You can support the project via Buy Me a Coffee!
Contributing
Found a bug or have a feature request? Please open an issue! Pull requests are also welcome.
License
Avakin is licensed under the MIT License.
<p align="center">
<em>Now, go build something amazeballs!.</em>
</p>
```