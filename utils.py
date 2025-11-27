import subprocess
import os

def run_git_command(command_parts, cwd='.'):
    """
    Executes a git command within the specified directory (cwd) and returns stdout.

    Args:
        command_parts (list): List of strings representing the Git command and its arguments.
                              Example: ['diff', 'my_file.py']
        cwd (str): The directory to run the command in (typically the project root).

    Returns:
        str: The standard output of the command, or an error message if the command fails.
    """
    try:
        # Prepend 'git' to the command list to form the full execution command
        full_command = ['git'] + command_parts
        
        # Use subprocess.run for robust command execution
        result = subprocess.run(
            full_command, 
            cwd=cwd, 
            capture_output=True, 
            text=True, 
            check=True,  # Raises subprocess.CalledProcessError for non-zero exit codes
            encoding='utf-8'
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        # Log the error and return the stderr content
        print(f"ERROR: Git command failed in {cwd}: {' '.join(full_command)}")
        print(f"Stderr: {e.stderr.strip()}")
        return f"GIT_ERROR: {e.stderr.strip()}"
    except FileNotFoundError:
        return "ERROR: Git command not found. Ensure Git is installed and in PATH."

# Example usage (for testing, would be removed in final version):
# if __name__ == '__main__':
#     # This assumes you are in a Git repo for testing
#     diff_output = run_git_command(['diff', 'HEAD', 'utils.py'])
#     print(f"Diff Output:\n{diff_output}")
