import json
from typing import Dict, Any, List

class PromptEngine:
    """
    Generates structured payloads for the Ollama API, including system prompts 
    and user queries, tailored to specific coding tasks and languages.
    """

    def __init__(self, ollama_url: str):
        """Initializes the PromptEngine with the target Ollama API URL."""
        self.ollama_url = ollama_url
        print(f"Prompt Engine initialized for base URL: {self.ollama_url}")


    def _create_ollama_payload(self, system_prompt: str, user_prompt: str, model_name: str, enforce_json: bool = False) -> Dict[str, Any]:
        """
        Creates the standard JSON payload structure for the Ollama /api/generate endpoint.
        """
        is_critical_task = enforce_json or "fix" in system_prompt.lower()
        temperature = 0.1 if is_critical_task else 0.7

        payload = {
            "model": model_name,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
            },
        }
        
        if enforce_json:
            # Use 'format': 'json' for Ollama to try to enforce JSON output
            payload['format'] = 'json' 
            
        return payload

    # --- AGENT PLANNING PROMPT (Updated with directory actions) ---
    def create_planning_prompt(self, goal: str, codebase_summary: str, model_name: str) -> Dict[str, Any]:
        """
        Generates a prompt to ask the LLM to create a multi-step action plan 
        based on the project structure and the high-level goal.
        """
        
        system_prompt = (
            "You are a world-class Code Agent Planner. Your task is to analyze the user's goal "
            "and the project file structure, then generate a precise, actionable plan. "
            "Your output MUST be ONLY a single JSON array of steps, wrapped in markdown fences (`json`). "
            "Each step MUST be an object with the properties: 'action', 'target', and 'description'.\n\n"
            "Action Types:\n"
            "1. 'GET_CONTEXT': Read the content of a file (e.g., a dependency or class definition) into the agent's memory. Target MUST be the file path.\n"
            "2. 'GENERATE_CODE': Create a brand new file (e.g., a test file) using the current context. Target MUST be the new file path.\n"
            "3. 'MODIFY_CODE': Alter the content of an existing file (e.g., add a new method). Target MUST be the file path.\n"
            "4. 'CREATE_DIR': Create a new directory or a nested directory structure. Target MUST be the directory path (e.g., 'src/api/v1').\n" # <--- NEW ACTION
            "5. 'DELETE_DIR': Delete an existing directory and all its contents. Target MUST be the directory path.\n" # <--- NEW ACTION
            "6. 'REPORT_SUCCESS': The final step to indicate the task is complete. Target MUST be empty ('').\n\n"
            "CRITICAL: The sequence must be logical. Start by getting necessary context before generating/modifying code."
        )

        user_prompt = (
            f"GOAL: {goal}\n\n"
            f"PROJECT FILE STRUCTURE:\n"
            f"```text\n{codebase_summary}\n```\n\n"
            f"Generate the JSON array of action steps to achieve the GOAL."
        )
        
        return self._create_ollama_payload(system_prompt, user_prompt, model_name, enforce_json=True)

    # --- (Rest of the file remains unchanged) ---
    def create_execution_prompt(self, task_description: str, accumulated_context: str, target_file: str, project_language: str, model_name: str) -> Dict[str, Any]:
        """
        Generates a prompt for the LLM to execute a single code generation/modification step 
        using all accumulated file context.
        """
        
        system_prompt = (
            f"You are a specialist {project_language.upper()} Developer. Your task is to perform a single, atomic coding operation. "
            f"Analyze the accumulated code context and the specific task description. "
            f"Your output MUST be ONLY the FULL, COMPLETE, AND CORRECT CONTENT for the target file '{target_file}'. "
            f"DO NOT include commentary, surrounding text, or markdown fences. The output must be ready to write to the file system."
        )

        user_prompt = (
            f"SPECIFIC TASK: {task_description}\n"
            f"TARGET FILE: {target_file}\n\n"
            f"ACCUMULATED CODE CONTEXT (Multiple Files):\n"
            f"{accumulated_context}\n\n"
            f"Generate ONLY the FULL content for the file '{target_file}'."
        )
        
        # Use a non-JSON payload for raw code output
        return self._create_ollama_payload(system_prompt, user_prompt, model_name, enforce_json=False)


    def create_review_prompt(self, context: Dict[str, str], model_name: str) -> Dict[str, Any]:
        """
        Generates a prompt for a comprehensive code review focused on changes (diff).
        """
        language = context['language']
        content = context['content']
        filepath = context['filepath']

        system_prompt = (
            f"You are a meticulous Senior Software Engineer specializing in {language.upper()}. "
            "Your task is to perform a detailed code review. Focus on security, performance, "
            "maintainability, and adherence to language-specific best practices. "
            "Provide your feedback in bullet points, referencing line numbers from the provided code context (the original file or the diff lines)."
            "DO NOT rewrite the entire file or provide corrected code unless the issue is critical."
        )

        user_prompt = (
            f"Please review the following code changes for the file `{filepath}` "
            f"which is a {language} project. The input is a unified diff, so only "
            f"focus your review on the lines prefixed with '+' or '-'.\n\n"
            f"```diff\n{content}\n```"
        )
        
        return self._create_ollama_payload(system_prompt, user_prompt, model_name)


    def create_fix_prompt(self, context: Dict[str, str], error_traceback: str, model_name: str) -> Dict[str, Any]:
        """
        Generates a prompt to fix a bug using the provided code and traceback.
        
        The LLM is strictly instructed to output a JSON object containing file actions 
        (modify, create, delete).
        """
        language = context['language']
        content = context['content']
        filepath = context['filepath']

        system_prompt = (
            f"You are an expert bug fixer for {language.upper()} codebases. Analyze the provided code and traceback. "
            "Your response MUST be ONLY a single JSON array that details the required file system actions. "
            "Do not include any commentary or surrounding text, and wrap the JSON in markdown fences."
            "The JSON array must contain one or more objects, each with the following properties: "
            "  - 'action': 'modify', 'create', or 'delete'. "
            "  - 'filepath': The path to the file (relative to the project root). "
            
            "**CRITICAL RULE for 'modify' action:** The content MUST be the **FULL, COMPLETE, AND CORRECTED CONTENT of the target file**. "
            "For 'create', content is the full new file content. For 'delete', content is empty."
        )

        user_prompt = (
            f"The following {language} file `{filepath}` is causing an error. "
            f"Traceback:\n```\n{error_traceback}\n```\n\n"
            f"Current File Content:\n"
            f"```{language}\n{content}\n```"
            f"\n\nGenerate the JSON array of actions to fix this error."
        )
        
        return self._create_ollama_payload(system_prompt, user_prompt, model_name, enforce_json=True)


    def create_generate_prompt(self, context: Dict[str, str], user_request: str, model_name: str) -> Dict[str, Any]:
        """
        Generates a prompt for new code generation (e.g., writing a new function) 
        in the original single-file mode.
        """
        language = context['language']
        surrounding_code = context['content']

        system_prompt = (
            f"You are a helpful coding assistant for {language.upper()}. "
            "Write the requested code snippet cleanly and idiomatically. "
            "Enclose your complete code response in a single markdown code block with the correct language tag."
        )

        user_prompt = (
            f"Based on the following surrounding code context (a {language} project):\n"
            f"```{language}\n{surrounding_code}\n```\n\n"
            f"Please complete the following request:\n{user_request}"
        )
        
        return self._create_ollama_payload(system_prompt, user_prompt, model_name)
