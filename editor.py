import os
import json
import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional

# Assuming utils.py is available for shell command execution
try:
    from utils import run_git_command
except ImportError:
    # Define a simplified placeholder if utils.py is not available in test environment
    def run_git_command(command_parts, cwd='.'):
        """Placeholder for actual run_git_command from utils.py"""
        print(f"[Placeholder] Executing: git {' '.join(command_parts)} in {cwd}")
        # We will use direct subprocess for the critical git apply command below
        return f"Placeholder executed: {' '.join(command_parts)}"


class CodeEditor:
    """
    Handles parsing LLM-generated JSON action lists and safely executing 
    file system changes (create, delete, modify via git apply).
    """

    def __init__(self, project_root: str):
        """
        Initializes the editor with the project's root directory.
        """
        self.project_root = Path(project_root).resolve()
        if not self.project_root.is_dir():
            raise FileNotFoundError(f"Project root directory not found: {project_root}")
        print(f"Editor initialized for project root: {self.project_root}")

    def _parse_actions(self, json_string: str) -> Optional[List[Dict[str, str]]]:
        """
        Parses the LLM's raw JSON output into a list of action dictionaries.
        """
        try:
            actions = json.loads(json_string)
            if not isinstance(actions, list):
                print("JSON Error: Expected a JSON array of actions, received an object.")
                return None
            return actions
        except json.JSONDecodeError as e:
            print(f"JSON Parsing Error: Failed to decode LLM response into actions. Error: {e}")
            print(f"Raw Response: {json_string[:200]}...")
            return None

    def _execute_modify(self, filepath: Path, diff_content: str) -> bool:
        """
        Applies a unified diff patch to an existing file using 'git apply'.
        """
        relative_path = filepath.relative_to(self.project_root)
        print(f"  -> Action: MODIFY {relative_path}")
        
        # 1. Temporarily save the diff to a file
        diff_tmp_path = self.project_root / f".{relative_path.name}.tmp.patch"
        
        try:
            with open(diff_tmp_path, 'w', encoding='utf-8') as f:
                f.write(diff_content)
            
            # 2. Use `git apply` for robust, standard patch application
            # We use subprocess directly here for critical error checking.
            result = subprocess.run(
                ['git', 'apply', '--unidiff-zero', str(diff_tmp_path)],
                cwd=str(self.project_root), 
                capture_output=True, 
                text=True, 
                check=False 
            )
            
            if result.returncode == 0:
                print(f"  -> SUCCESS: Patch applied to {relative_path}.")
                return True
            else:
                print(f"  -> ERROR: Failed to apply patch to {relative_path}.")
                print(f"     Git Stderr:\n{result.stderr}")
                return False

        except Exception as e:
            print(f"  -> CRITICAL ERROR during patch application: {e}")
            return False
            
        finally:
            # 3. Clean up the temporary diff file
            if diff_tmp_path.exists():
                os.remove(diff_tmp_path)

    def _execute_create(self, filepath: Path, content: str) -> bool:
        """
        Creates a new file with the provided content, ensuring parent directories exist.
        """
        relative_path = filepath.relative_to(self.project_root)
        print(f"  -> Action: CREATE {relative_path}")
        
        if filepath.exists():
            print(f"  -> ERROR: Cannot create file, {relative_path} already exists. Skipping.")
            return False
            
        try:
            # Create parent directories if they don't exist
            filepath.parent.mkdir(parents=True, exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"  -> SUCCESS: File created at {relative_path}.")
            return True
        except Exception as e:
            print(f"  -> ERROR: Failed to create file {relative_path}. Reason: {e}")
            return False

    def _execute_delete(self, filepath: Path) -> bool:
        """
        Deletes a file, confirming it exists before attempting removal.
        """
        relative_path = filepath.relative_to(self.project_root)
        print(f"  -> Action: DELETE {relative_path}")

        if not filepath.exists():
            print(f"  -> WARNING: File {relative_path} does not exist. Skipping deletion.")
            return True # Consider successful if the file is already gone
            
        try:
            os.remove(filepath)
            print(f"  -> SUCCESS: File deleted at {relative_path}.")
            return True
        except Exception as e:
            print(f"  -> ERROR: Failed to delete file {relative_path}. Reason: {e}")
            return False

    def apply_multi_action_fix(self, raw_json_response: str) -> bool:
        """
        Main method to process and apply the LLM's structured multi-file actions.

        Args:
            raw_json_response: The raw JSON string from the LLM via OllamaClient.

        Returns:
            bool: True if all critical actions were applied successfully, False otherwise.
        """
        
        actions = self._parse_actions(raw_json_response)
        if not actions:
            print("Action processing aborted due to JSON error.")
            return False

        print(f"\n--- PROPOSED MULTI-FILE ACTIONS ({len(actions)} total) ---")
        
        # 1. Preview Actions
        successful_actions = 0
        
        for i, action in enumerate(actions, 1):
            act = action.get('action', 'unknown').lower()
            path = action.get('filepath', 'UNKNOWN_PATH')
            
            if not path or act not in ['modify', 'create', 'delete']:
                print(f"[{i}/{len(actions)}] INVALID action object: {action}")
                continue
                
            print(f"[{i}/{len(actions)}] {act.upper()}: {path}")

        print("\n---------------------------------------------------------")
        user_input = input("Apply ALL proposed changes? (y/N): ").strip().lower()

        if user_input != 'y':
            print("Action application cancelled by user. Files unchanged.")
            return False

        # 2. Execute Actions
        print("\n--- EXECUTING ACTIONS ---")
        all_successful = True
        
        for action in actions:
            act = action.get('action', '').lower()
            relative_path = action.get('filepath', '')
            content = action.get('content', '')
            
            if not relative_path: continue

            full_path = self.project_root / relative_path

            success = False
            if act == 'modify':
                # Note: Content must be the unified diff string
                success = self._execute_modify(full_path, content)
            elif act == 'create':
                # Note: Content must be the full file content
                success = self._execute_create(full_path, content)
            elif act == 'delete':
                success = self._execute_delete(full_path)
            else:
                print(f"  -> WARNING: Unknown action '{act}' skipped for {relative_path}.")

            if not success:
                all_successful = False
                print(f"  -> FAILURE detected for action {act} on {relative_path}. Continuing...")

        return all_successful
