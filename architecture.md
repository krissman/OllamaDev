# **OllamaDev: Local Code Assistant System Plan**

The goal of OllamaDev is to create a set of integrated Python tools that can interact with a local codebase, analyze it, and use an Ollama-hosted Large Language Model (LLM) for automated coding tasks (generation, review, fixing).

This system operates entirely locally, maximizing privacy and leveraging local computational resources.

## **1\. System Architecture Overview**

The system is designed with a clear separation of concerns: File I/O, LLM Communication, and Prompt Engineering.

The process follows a loop: **Context Gathering \-\> LLM Inference (Prompting) \-\> Output Application.**

### **Core Components:**

1. **User Interface (CLI/IDE Integration):** The point of interaction. (Initial draft will focus on simple CLI scripts).  
2. **Code Analyzer & Context Builder (analyzer.py):** Handles file reading, syntax analysis, and preparing relevant code snippets for the LLM.  
3. **Ollama Client (ollama\_client.py):** Manages the communication with the local Ollama API (HTTP requests).  
4. **Prompt Engine (prompts.py):** Stores and formats the specific instructions (system and user prompts) for the LLM.  
5. **Code Editor & Diff Utility (editor.py):** Responsible for parsing the LLM's suggested code and applying changes (e.g., generating and applying a patch/diff).

## **2\. Python Script Components**

### **2.1. ollama\_client.py (API Communication)**

This script encapsulates all interactions with the local Ollama HTTP API. It handles the POST requests to the /api/generate endpoint.

**Key Responsibilities:**

* **Connection:** Establish and maintain a connection to the Ollama server (e.g., http://localhost:11434).  
* **Request Formatting:** Accept a structured prompt object (text, system instruction) and format it into the required JSON payload for Ollama.  
* **Error Handling:** Manage network errors, model loading failures, and Ollama server unavailability.  
* **Streaming (Optional but Recommended):** Process the response stream chunk by chunk, especially for large code generation tasks.

**Required Libraries:** requests

### **2.2. analyzer.py (Context Builder)**

This is the "intelligence" layer that determines what code the LLM needs to see. Providing the *right* context is crucial for quality output.

**Key Responsibilities:**

* **File Reader:** Read the target file content.  
* **Context Discovery:**  
  * Identify surrounding function/class definitions.  
  * Read relevant imported files/modules (e.g., if the user is writing a function that uses a class defined elsewhere).  
  * Handle large files by only including the relevant lines (e.g., the function being fixed/reviewed plus 5 lines before and after).  
* **Context Formatting:** Package the code snippets into a clean, markdown-formatted block for injection into the main prompt.

**Required Libraries:** os, potentially ast (for advanced Python syntax parsing).

### **2.3. editor.py (Change Application)**

This component handles the output phase, converting the LLM's text response into actionable file changes.

**Key Responsibilities:**

* **Output Parsing:** The LLM should be instructed to output changes in a specific, parsable format (ideally a unified diff or patch format, as this is robust).  
* **Diff Generation/Application:**  
  * If the LLM provides raw code, editor.py calculates the diff against the original file.  
  * If the LLM provides a diff, editor.py uses a library to apply the patch to the file safely.  
* **Confirmation:** Present the generated diff to the user for confirmation before overwriting the file.

**Required Libraries:** difflib (built-in, useful for generating simple diffs), or external tools for patch application if needed.

### **2.4. prompts.py (The Brains)**

This script houses the specific instructions that guide the LLM's behavior. High-quality prompts are the key to a good "Codex" experience.

**Example Prompt Templates (F-string placeholders indicated):**

| Task | System Instruction (Ollama System Prompt) | User Query Template (User Prompt) |
| :---- | :---- | :---- |
| **Code Review** | "You are an expert Senior Python Developer specializing in security and performance. Provide detailed, actionable feedback on the user's code. Do not rewrite the code unless necessary." | "Review the following Python code for best practices, security flaws, and performance issues. Context: {Code Context}. Target Code: python\\n{Target Code}\\n" |
| **Code Fixing** | "You are an expert Python debugger. You must analyze the provided traceback and code, and provide a unified diff showing ONLY the necessary changes to fix the error." | "The following Python code failed with this traceback: |


