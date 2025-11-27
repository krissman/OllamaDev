import os
from pathlib import Path
from utils import run_git_command # We import the utility function

class CodeAnalyzer:
    """
    Handles file reading, language detection, and context gathering
    (full code content or git diffs) for the LLM.
    """
    
    # Mapping of common file extensions to programming languages
    LANGUAGE_MAP = {
        '.py': 'python',
        '.java': 'java',
        '.php': 'php',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.html': 'html',
        '.css': 'css',
        '.md': 'markdown',
        '.json': 'json',
    }

    def __init__(self, project_root: str):
        """
        Initializes the analyzer with the project's root directory.
        
        Args:
            project_root: The absolute or relative path to the root of the project 
                          (which is assumed to be a Git repository).
        """
        self.project_root = Path(project_root).resolve()
        if not self.project_root.is_dir():
            raise FileNotFoundError(f"Project root directory not found: {project_root}")
        print(f"Analyzer initialized for project root: {self.project_root}")


    def _detect_language(self, filepath: Path) -> str:
        """
        Infers the programming language based on the file extension.
        
        Args:
            filepath: The Path object of the file.
            
        Returns:
            str: The language name (e.g., 'python', 'java', 'php') or 'text'.
        """
        suffix = filepath.suffix.lower()
        return self.LANGUAGE_MAP.get(suffix, 'text')


    def _get_git_diff(self, relative_path: str) -> str:
        """
        Retrieves the uncommitted changes (diff) for a specific file 
        relative to the project root.
        
        Args:
            relative_path: Path of the file relative to the Git repository root.

        Returns:
            str: The unified diff output, or an error message.
        """
        # Command: git diff --unified=1 --no-prefix <filepath>
        # --unified=1 keeps the context lines minimal, which is better for LLM token limits
        # --no-prefix removes a/ and b/ from file names in the diff headers
        command = ['diff', '--unified=1', '--no-prefix', relative_path]
        
        # Use the utility to run the command in the project root
        diff_content = run_git_command(command, cwd=str(self.project_root))
        
        return diff_content


    def _read_file_content(self, relative_path: str) -> str:
        """
        Reads the full content of a file.
        
        Args:
            relative_path: Path of the file relative to the project root.
            
        Returns:
            str: The file content, or an error message.
        """
        full_path = self.project_root / relative_path
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return f"FILE_ERROR: File not found at {full_path}"
        except Exception as e:
            return f"FILE_ERROR: Could not read file {full_path}. Reason: {e}"


    def get_context(self, relative_path: str, mode: str) -> dict:
        """
        Main method to gather the context for the LLM.
        
        Args:
            relative_path: The file path relative to the project root.
            mode: The context mode ('full' for content, 'diff' for uncommitted changes).
            
        Returns:
            dict: A structured dictionary containing the gathered context.
        """
        full_path = self.project_root / relative_path
        if not full_path.exists():
            return {
                'language': 'text',
                'filepath': relative_path,
                'content': f"ERROR: File '{relative_path}' does not exist in the project.",
                'mode': mode
            }
        
        language = self._detect_language(full_path)
        content = ""

        if mode == 'full':
            # For generation or documentation tasks
            content = self._read_file_content(relative_path)
            
        elif mode == 'diff':
            # For review or fixing tasks focused on changes
            content = self._get_git_diff(relative_path)
            if content.startswith("GIT_ERROR"):
                 print(f"Warning: Falling back to full content due to Git error.")
                 content = self._read_file_content(relative_path)
                 mode = 'full' # Change mode to reflect fallback

        else:
            content = f"ERROR: Invalid context mode '{mode}' requested."

        return {
            'language': language,
            'filepath': relative_path,
            'content': content,
            'mode': mode
        }

# Example Usage (for testing purposes):
# if __name__ == '__main__':
#     # NOTE: This only works if you run it inside a Git repository!
#     try:
#         # Use the current directory as the project root
#         analyzer = CodeAnalyzer(os.getcwd()) 
#         
#         # 1. Get full content for the current script
#         full_context = analyzer.get_context('analyzer.py', 'full')
#         print("\n--- FULL CONTEXT EXAMPLE ---")
#         print(f"Language: {full_context['language']}")
#         # print(f"Content:\n{full_context['content'][:500]}...")
#         
#         # 2. Get diff for the current script
#         diff_context = analyzer.get_context('analyzer.py', 'diff')
#         print("\n--- DIFF CONTEXT EXAMPLE ---")
#         print(f"Mode: {diff_context['mode']}")
#         print(f"Diff Content:\n{diff_context['content']}")
        
#     except FileNotFoundError as e:
#         print(e)
#     except Exception as e:
#         print(f"An unexpected error occurred: {e}")
