import json
from typing import Dict, Any

class PromptEngine:
    """
    Generates structured payloads for the Ollama API, including system prompts 
    and user queries, tailored to specific coding tasks and languages.
    """

    def __init__(self, ollama_url: str):
        """Initializes the PromptEngine with the target Ollama API URL."""
        self.ollama_url = ollama_url
        print(f"Prompt Engine initialized for base URL: {self.ollama_url}")


    def _create_ollama_payload(self, system_prompt: str, user_prompt: str, model_name: str) -> Dict[str, Any]:
        """
        Creates the standard JSON payload structure for the Ollama /api/generate endpoint.
        """
        is_critical_task = "fix" in system_prompt.lower() or "review" in system_prompt.lower()
        temperature = 0.2 if is_critical_task else 0.7

        return {
            "model": model_name,
            "prompt": user_prompt,
            "system": system_prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 4096,
            },
        }

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

        # --- REVISED SYSTEM PROMPT TO DEMAND FULL CONTENT ONLY FOR MODIFY ---
        system_prompt = (
            f"You are an expert bug fixer for {language.upper()} codebases. Analyze the provided code and traceback. "
            "Your response MUST be ONLY a single JSON array that details the required file system actions. "
            "Do not include any commentary or surrounding text, and wrap the JSON in markdown fences."
            "The JSON array must contain one or more objects, each with the following properties: "
            "  - 'action': 'modify', 'create', or 'delete'. "
            "  - 'filepath': The path to the file (relative to the project root). "
            
            "**CRITICAL RULE for 'modify' action:** The content MUST be the **FULL, COMPLETE, AND CORRECTED CONTENT of the target file**. "
            "DO NOT include diff headers, hunk headers, or any structural elements like `--- a/` or `@@`."
            
            "For 'create', content is the full new file content. For 'delete', content is empty."
        )

        user_prompt = (
            f"The following {language} file `{filepath}` is causing an error. "
            f"Traceback:\n```\n{error_traceback}\n```\n\n"
            f"Current File Content:\n"
            f"```{language}\n{content}\n```"
            f"\n\nGenerate the JSON array of actions to fix this error."
        )
        
        return self._create_ollama_payload(system_prompt, user_prompt, model_name)


    def create_generate_prompt(self, context: Dict[str, str], user_request: str, model_name: str) -> Dict[str, Any]:
        """
        Generates a prompt for new code generation (e.g., writing a new function).
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
