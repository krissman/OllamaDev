import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from utils import run_git_command # We import the utility function

class CodeAnalyzer:
    """
    Handles file reading, language detection, and context gathering
    (full code content or git diffs) for the LLM.
    
    UPDATED for multi-file context and project summary generation.
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
        '.kt': 'kotlin',
        '.cs': 'C#',
        '.sql': 'T-SQL',
    }
    
    # Files/directories to ignore during project summary
    IGNORE_PATTERNS = ['.git', '__pycache__', '.env', 'node_modules', '*.log']

    def __init__(self, project_root: str):
        """
        Initializes the analyzer with the project's root directory.
        """
        self.project_root = Path(project_root).resolve()
        if not self.project_root.is_dir():
            raise FileNotFoundError(f"Project root directory not found: {project_root}")
        print(f"Analyzer initialized for project root: {self.project_root}")


    def _detect_language(self, filepath: Path) -> str:
        """
        Infers the programming language based on the file extension.
        """
        suffix = filepath.suffix.lower()
        return self.LANGUAGE_MAP.get(suffix, 'text')


    def _get_git_diff(self, relative_path: str) -> str:
        """
        Retrieves the uncommitted changes (diff) for a specific file 
        relative to the project root.
        """
        # Command: git diff --unified=1 --no-prefix <filepath>
        command = ['diff', '--unified=1', '--no-prefix', relative_path]
        diff_content = run_git_command(command, cwd=str(self.project_root))
        return diff_content


    def _read_file_content(self, relative_path: str) -> str:
        """
        Reads the full content of a file.
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
        Main method to gather the context for the LLM (single file).
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
            content = self._read_file_content(relative_path)
            
        elif mode == 'diff':
            content = self._get_git_diff(relative_path)
            if content.startswith("GIT_ERROR"):
                 print(f"Warning: Falling back to full content due to Git error.")
                 content = self._read_file_content(relative_path)
                 mode = 'full'
        else:
            content = f"ERROR: Invalid context mode '{mode}' requested."

        return {
            'language': language,
            'filepath': relative_path,
            'content': content,
            'mode': mode
        }

    def get_project_summary(self) -> str:
        """
        Generates a high-level summary of the codebase structure (file list).
        This is used primarily for the LLM planning step.
        """
        print("  -> Generating project file list...")
        summary = ["Project File Structure (relative paths):"]
        
        for root, dirs, files in os.walk(self.project_root):
            # Prune ignored directories
            dirs[:] = [d for d in dirs if d not in self.IGNORE_PATTERNS and not d.startswith('.')]
            
            relative_root = Path(root).relative_to(self.project_root)
            
            for f in files:
                # Prune ignored files
                if any(f.endswith(p.lstrip('*')) for p in self.IGNORE_PATTERNS if p.startswith('*')) or f in self.IGNORE_PATTERNS:
                    continue
                    
                relative_path = relative_root / f
                if str(relative_path) == '.': # Skip the root itself if it appears
                    continue

                summary.append(f"- {relative_path}")
                
        if len(summary) == 1:
            return "ERROR: No code files found in the project root."
            
        return "\n".join(summary)


    def get_multiple_context(self, file_paths: List[str], file_contents: Dict[str, str]) -> str:
        """
        Combines content from multiple files (already read and stored in file_contents) 
        into a single, clean markdown block for the LLM execution step.
        
        Args:
            file_paths: Ordered list of file paths to include.
            file_contents: Dictionary of {filepath: content} from the agent's state.
            
        Returns:
            str: A formatted string containing all file contexts.
        """
        if not file_paths:
            return ""

        combined_context = []
        
        # Detect a common language for the entire context block (use 'python' if ambiguous)
        primary_language = 'text'
        for path in file_paths:
            if path in file_contents:
                lang = self._detect_language(Path(path))
                if lang != 'text':
                    primary_language = lang
                    break
        
        for path in file_paths:
            content = file_contents.get(path)
            if content:
                # Use a comment/delimiter to clearly separate files
                combined_context.append(f"\n/* --- FILE: {path} ({self.LANGUAGE_MAP.get(Path(path).suffix.lower(), 'text').upper()}) --- */\n")
                combined_context.append(content)
        
        # Wrap the whole block in a markdown code fence for the LLM
        return f"```{primary_language}\n" + "\n".join(combined_context) + "\n```"
