# Avakin

### Build, Modify, and Debug at the Speed of Thought.

![Avakin In Action](https://github.com/carpsesdema/Avakin/raw/master/Kapture%202024-06-19%20at%2018.06.15.gif)

<div align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-blue.svg" alt="Version">
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
    
    ## Getting Started
    
    ### 1. Download
    
    Grab the latest release from the **Releases** page. Download the `Avakin_Launcher.exe` and the main application folder.
    
    ### 2. Installation
    
    1.  Create a folder for your application (e.g., `C:\Avakin`).
    2.  Place `Avakin_Launcher.exe` inside this folder.
    3.  Place the `main` folder (containing `main.exe` and other files) inside this folder.
    
    Your final folder structure should look like this:
    
    ```
    C:\Avakin\
    ├── Avakin_Launcher.exe
    └── main\
        ├── main.exe
        └── ... (all other application files)
    ```
    
    ### 3. Configure Your API Keys (Important!)
    
    Avakin reads your API keys from your system's environment variables. This is the most secure way to manage your keys without hardcoding them.
    
    Here’s how to set them up on Windows:
    
    1.  Press the **Windows Key**, type `env`, and click on "Edit the system environment variables".
    2.  In the "System Properties" window that opens, click the **Environment Variables...** button at the bottom.
    3.  In the "User variables" section (the top box), click **New...**.
    4.  A new window will pop up.
        -   For the **Variable name**, enter `OPENAI_API_KEY`.
        -   For the **Variable value**, paste your actual key (e.g., `sk-...`).
        -   Click **OK**.
    5.  Repeat step 4 for all the other API keys you want to use. Here are the most common ones:
        -   `GEMINI_API_KEY`
        -   `ANTHROPIC_API_KEY`
        -   (Optional) `DEEPSEEK_API_KEY`
    6.  Once you've added all your keys, click **OK** on the "Environment Variables" window, and then **OK** on the "System Properties" window to save everything.
    
    **IMPORTANT NOTE:** You must close and restart Avakin Launcher (and any open command prompts) for these new settings to take effect!
    
    #### Alternative Method for Developers (.env file)
    
    If you are running from source or prefer using `.env` files, you can create a file named `.env` in the root of the project (the same folder as `main.py`). Avakin will automatically load it.
    
    ```dotenv
    # .env file content
    OPENAI_API_KEY="sk-..."
    GEMINI_API_KEY="abc..."
    ANTHROPIC_API_KEY="xyz-..."
    ```
    
    ### 4. Launch!
    
    Run `Avakin_Launcher.exe`. It will check for updates and then launch the main application. You're ready to go!
    
    ## Quick Usage
    
    -   **To Create a New Project:** Simply describe what you want to build in the chat prompt and hit send.
    -   **To Fix an Error:** Run your code from the integrated terminal. When an error appears, click the "Review & Fix Code" button.
    
    ## Support Avakin's Mission
    
    Avakin is a labor of love from a solo developer. If this tool helps you build something amazing, saves you time, or just makes your coding life a little easier, please consider supporting its development. Every little bit helps me keep the lights on and continue making Avakin more powerful for everyone.
    
    ## Contributing
    
    Found a bug or have a feature request? Please open an issue!
    
    ## License
    
    Avakin is licensed under the [MIT License](LICENSE).
    
    <p align="center">
      <em>Now, go build something incredible.</em>
    </p>