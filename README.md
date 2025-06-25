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
  <img src="https://img.shields.io/badge/version-1.0.1-blue.svg" alt="Version">
  <img src="https://img.shields.io/badge/platform-windows-informational.svg" alt="Platform">
  <img src="https://img.shields.io/badge/license-MIT-success.svg" alt="License">
</div>

Tired of the endless cycle of expensive API calls, context window limitations, and AI tools that don't truly understand your project's architecture?

Avakin is a complete, AI-powered development environment that runs entirely on your local machine. It's not just a chatbot; it's a team of specialized AI agents—an Architect, a Coder, a Reviewer, and a Validator—working together to bring your ideas to life. From a single prompt, Avakin can scaffold an entire multi-file application, surgically modify existing codebases, and intelligently debug errors with a single click.

## Core Features

-   ⚡️ **Instant Project Scaffolding:** Go from a single sentence to a complete, runnable, multi-file Python project in seconds. Avakin designs the architecture, plans the files, and writes the code.
-   ✍️ **Surgical Code Modification:** Make complex, context-aware changes to existing codebases using natural language.
-   🪄 **One-Click Debugging:** When your code fails, a "Review & Fix" button appears. Avakin analyzes the full project context, git history, and error traceback to provide a precise, intelligent fix.
-   🧠 **Your Personal RAG:** Augment Avakin's knowledge by connecting it to a local RAG (Retrieval-Augmented Generation) server. Feed it your documentation, existing projects, or any text-based knowledge to improve its context-awareness.
-   🔌 **Extensible Plugin System:** Avakin is built on a robust plugin architecture. Extend its capabilities, add new agents, or integrate with other tools.
-   🔐 **100% Local & Private:** Your code and your API keys never leave your machine. Avakin uses a local-first approach, giving you complete control and privacy without sacrificing power.
-   🤖 **Customizable AI Team:** Configure which LLM (local or cloud-based) you want for each role. Use a massive model for architecture and a fast, cheap model for chat. You are in control.

## Why Avakin Exists

I built Avakin out of necessity. After a decade of teaching myself to code while working physically demanding jobs, I hit the same walls so many other self-taught developers face: the tools were too expensive, the industry was too exclusive, and the path to turning a passion into a profession felt impossible.

Avakin is my answer.

It's a tool forged in fire, designed to give individual developers and small teams the power of an entire AI workforce without the crippling cost. It's for the talented developer grinding after hours, the student with a brilliant idea but no budget, and anyone who believes that your talent shouldn't be limited by your wallet.

This is a tool for the underdog, by an underdog. It's my hope that it gives you the freedom to build your escape, your masterpiece, your future.

## Getting Started (Running from Source)

Avakin is designed to be run directly from source, giving you full control.

### 1. Clone the Repository

First, clone the project to your local machine:

    ```bash
    git clone https://github.com/carpsesdema/AvA_Kintsugi.git
    cd AvA_Kintsugi
## 2. Install Dependencies
   It's highly recommended to use a Python virtual environment.
   # Create and activate a virtual environment (optional but recommended)
   python -m venv .venv
   source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
    
## 3. Install the required packages
   pip install -r src/ava/requirements.txt
   # Create and activate a virtual environment (optional but recommended)
   python -m venv .venv
   source .venv/bin/activate  # On Windows, use: .venv\Scripts\activate
    
   # Install the required packages
   pip install -r src/ava/requirements.txt
   # .env file content
   OPENAI_API_KEY="sk-..."
   GEMINI_API_KEY="abc..."
   ANTHROPIC_API_KEY="xyz-..."
## 4. Launch!
Run the main application script from the root directory of the project:
## 5. python src/ava/main.py
You're ready to go!
Quick Usage
To Create a New Project: Simply describe what you want to build in the chat prompt and hit send.
To Fix an Error: Run your code from the integrated terminal. When an error appears, click the "Review & Fix Code" button.
Support Avakin's Mission
Avakin is a labor of love from a solo developer. If this tool helps you build something amazing, saves you time, or just makes your coding life a little easier, please consider supporting its development. Every little bit helps me keep the lights on and continue making Avakin more powerful for everyone.
You can support the project via Buy Me a Coffee!
Contributing
Found a bug or have a feature request? Please open an issue!
License
Avakin is licensed under the MIT License.
<p align="center">
<em>Now, go build something incredible.</em>
</p>
```