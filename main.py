import os
import sys
import argparse
from pathlib import Path
from typing import Optional

# --- Project Imports (Assumed to be in the same directory) ---
try:
    from config import OLLAMA_GENERATE_ENDPOINT, DEFAULT_MODEL
    from analyzer import CodeAnalyzer
    from prompts import PromptEngine
    from ollama_client import OllamaClient
    from editor import CodeEditor
except ImportError as e:
    print(f"Error importing required modules: {e}")
    print("Ensure all files (config.py, utils.py, analyzer.py, prompts.py, ollama_client.py, editor.py) are in the same directory.")
    sys.exit(1)


def setup_components(project_root: str):
    """Initializes all core components."""
    try:
        root_path = Path(project_root)
        if not (root_path / ".git").is_dir():
            print(f"Warning: Project root '{project_root}' does not appear to be a Git repository.")

        analyzer = CodeAnalyzer(project_root)
        engine = PromptEngine(OLLAMA_GENERATE_ENDPOINT)
        client = OllamaClient(OLLAMA_GENERATE_ENDPOINT)
        editor = CodeEditor(project_root)
        return analyzer, engine, client, editor
    except FileNotFoundError as e:
        print(f"Error setting up components: {e}")
        sys.exit(1)

def run_fix(args):
    """
    Handles the 'fix' command. 
    It requests a JSON array of actions (modify, create, delete) from the LLM 
    and applies them via the CodeEditor.
    """
    print(f"\n[OllamaDev] Running fix for {args.filepath}...")
    
    analyzer, engine, client, editor = setup_components(args.root)

    # 1. Get original content for context (needed for the LLM to generate the diff/actions)
    context = analyzer.get_context(args.filepath, mode='full')
    original_content = context['content']
    
    if original_content.startswith("FILE_ERROR"):
        print(f"Error: Could not read file content. Aborting.")
        return

    # 2. Generate the fix prompt
    print(f"Generating multi-action JSON prompt for bug fix (Language: {context['language']})...")
    
    traceback = args.traceback if args.traceback else input("Enter traceback/bug description: ")
    if not traceback:
        print("Fix command requires a traceback or description. Aborting.")
        return

    # This prompt instructs the LLM to return a JSON array of actions
    payload = engine.create_fix_prompt(context, traceback, args.model)

    # 3. Call the LLM
    print(f"Sending request to Ollama ({args.model})...")
    # This output is expected to be a raw JSON string (cleaned of markdown fences)
    json_actions_output = client.generate_content(payload)

    if json_actions_output.startswith("ERROR:"):
        print(f"LLM/Client Error: {json_actions_output}")
        return

    # 4. Apply the multi-action fix using the new editor method
    print("\n--- LLM Response Received ---")
    if editor.apply_multi_action_fix(json_actions_output):
        print("\nFix applied successfully (multi-action transaction complete).")
    else:
        print("\nFix application failed or was cancelled.")


def run_review(args):
    """Handles the 'review' command."""
    print(f"\n[OllamaDev] Running review for {args.filepath}...")
    
    analyzer, engine, client, _ = setup_components(args.root)
    
    # 1. Get context (prefer diff for review)
    # The analyzer will fall back to 'full' content if the file is untracked
    context = analyzer.get_context(args.filepath, mode='diff')
    
    if context['content'].startswith("GIT_ERROR"):
        print(f"Warning: Falling back to reviewing full file content.")
        context['mode'] = 'full'

    # 2. Generate the review prompt
    print(f"Generating review prompt (Mode: {context['mode']}, Language: {context['language']})...")
    
    # If mode is 'full', we instruct the user to review the entire file.
    if context['mode'] == 'full':
        review_request = "Review the entire file for quality and best practices."
        # Use the generate prompt template for full review
        payload = engine.create_generate_prompt(context, review_request, args.model)
    else:
        # Use the specialized review prompt for diffs
        payload = engine.create_review_prompt(context, args.model)

    # 3. Call the LLM
    print(f"Sending request to Ollama ({args.model})...")
    review_output = client.generate_content(payload)
    
    # 4. Display the review
    print("\n--- CODE REVIEW RESULTS ---")
    print(review_output)
    print("-----------------------------\n")

def run_generate(args):
    """Handles the 'generate' command."""
    print(f"\n[OllamaDev] Running code generation for {args.filepath}...")
    
    analyzer, engine, client, _ = setup_components(args.root)
    
    # 1. Get context (surrounding code for generation)
    # We use 'full' mode, but only the surrounding content is relevant to the LLM
    context = analyzer.get_context(args.filepath, mode='full')
    
    # 2. Generate the generation prompt
    print(f"Generating generation prompt (Language: {context['language']})...")
    
    # We ask the user for the specific request if not provided
    user_request = args.request if args.request else input("Enter code generation request (e.g., 'Write a function to hash a password'): ")
    if not user_request:
        print("Generation command requires a request. Aborting.")
        return

    payload = engine.create_generate_prompt(context, user_request, args.model)
    
    # 3. Call the LLM
    print(f"Sending request to Ollama ({args.model})...")
    generated_code = client.generate_content(payload)

    # 4. Display the generated code
    print("\n--- GENERATED CODE ---")
    print(generated_code)
    print("----------------------\n")
    print(f"Generated code is for reference and has NOT been written to {args.filepath}.")


def main():
    parser = argparse.ArgumentParser(
        description="OllamaDev: Local Code Assistant powered by Ollama and Git context.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    # Global Arguments
    parser.add_argument(
        '--root', 
        type=str, 
        default=os.getcwd(), 
        help="Root directory of the project (must be a Git repo). Defaults to current directory."
    )
    parser.add_argument(
        '--model', 
        type=str, 
        default=DEFAULT_MODEL, 
        help=f"Ollama model name to use. Default: {DEFAULT_MODEL}"
    )

    subparsers = parser.add_subparsers(dest='command', required=True)

    # --- FIX Command ---
    fix_parser = subparsers.add_parser('fix', help='Fixes a bug in a file(s) by generating structured actions (modify, create, delete).')
    fix_parser.add_argument('filepath', type=str, help='The primary file path (relative to root) to fix/provide context for.')
    fix_parser.add_argument(
        '--traceback', 
        type=str, 
        default=None, 
        help='Optional: Paste the full error traceback for better context. If omitted, input will be requested.'
    )
    fix_parser.set_defaults(func=run_fix)

    # --- REVIEW Command ---
    review_parser = subparsers.add_parser('review', help='Reviews a file or its uncommitted changes (diff).')
    review_parser.add_argument('filepath', type=str, help='The file path (relative to root) to review.')
    review_parser.set_defaults(func=run_review)

    # --- GENERATE Command ---
    generate_parser = subparsers.add_parser('generate', help='Generates new code (e.g., a function) based on existing context.')
    generate_parser.add_argument('filepath', type=str, help='The file path where the new code will be inserted (used for context).')
    generate_parser.add_argument(
        '--request', 
        type=str, 
        default=None, 
        help='Optional: The specific request for the LLM. If omitted, input will be requested.'
    )
    generate_parser.set_defaults(func=run_generate)


    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
