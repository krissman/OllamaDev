import json
import time
from typing import Dict, Any, List, Optional
from pathlib import Path

# Import all core components
from analyzer import CodeAnalyzer
from prompts import PromptEngine
from ollama_client import OllamaClient
from editor import CodeEditor

# Define the structure for an Action Step expected from the Planning LLM
ActionStep = Dict[str, str]

class CodeAgent:
    """
    The Agent orchestrator that executes complex, multi-step, multi-file tasks.
    It follows an iterative Observe-Plan-Act loop.
    """

    def __init__(self, analyzer: CodeAnalyzer, client: OllamaClient, engine: PromptEngine, editor: CodeEditor):
        """Initializes the Agent with dependencies and state."""
        self.analyzer = analyzer
        self.client = client
        self.engine = engine
        self.editor = editor
        
        # Internal state to hold the current plan and accumulated context/data
        self.plan: List[ActionStep] = []
        self.state: Dict[str, Any] = {
            'context_files': {},  # Stores content of files read (for execution steps)
            'target_language': 'python', # Assume initial language for project, refined by analyzer
            'errors': []
        }
        self.project_root = self.analyzer.project_root

    def _generate_plan(self, goal: str, context_summary: str, model_name: str) -> Optional[List[ActionStep]]:
        """
        Calls the LLM with the Planning Prompt to generate a JSON Action Plan.
        """
        print("\n--- AGENT: GENERATING PLAN (LLM Call) ---")
        
        # 1. Prepare the planning payload
        payload = self.engine.create_planning_prompt(
            goal=goal,
            codebase_summary=context_summary,
            model_name=model_name
        )
        
        # 2. Call the LLM
        raw_json_plan = self.client.generate_content(payload)
        
        # 3. Parse the LLM's JSON response
        try:
            # The client cleans up markdown fences, so we expect raw JSON
            plan = json.loads(raw_json_plan)
            if not isinstance(plan, list):
                 # This is the error path the user encountered. Improved feedback here.
                 print("PLANNING ERROR: LLM returned non-list JSON. Expected array of steps.")
                 print(f"LLM Response Snippet:\n{raw_json_plan[:500]}...")
                 return None
            print(f"--- AGENT: PLAN GENERATED ({len(plan)} steps) ---")
            return plan
        except json.JSONDecodeError as e:
            print(f"PLANNING ERROR: Failed to decode LLM response into plan JSON. Error: {e}")
            print(f"Raw Response: {raw_json_plan[:300]}...")
            return None

    def _execute_step(self, step: ActionStep, model_name: str) -> bool:
        """
        Executes a single step from the generated plan.
        """
        action = step.get('action', '').upper()
        target = step.get('target', '')
        description = step.get('description', 'No description provided.')

        print(f"\n--- EXECUTING STEP: {action} on {target} ---")
        print(f"Description: {description}")

        success = False
        full_path = self.project_root / target # Resolve path early

        if action == 'GET_CONTEXT':
            # ACTION 1: Read a file and store its content in the agent's state
            print(f"  -> Reading context from file: {target}...")
            context = self.analyzer.get_context(target, mode='full')
            
            if not context['content'].startswith("FILE_ERROR"):
                self.state['context_files'][target] = context['content']
                self.state['target_language'] = context['language']
                success = True
                print(f"  -> Context stored for {target}.")
            else:
                print(f"  -> ERROR reading file: {context['content']}")
                self.state['errors'].append(f"Failed to read file: {target}")

        elif action == 'GENERATE_CODE' or action == 'MODIFY_CODE':
            # ACTIONS 2/3: Generate or Modify file content based on accumulated context
            
            full_context = self.analyzer.get_multiple_context(list(self.state['context_files'].keys()), self.state['context_files'])
            
            if not full_context:
                print("  -> ERROR: Cannot execute code action without context. Aborting step.")
                return False

            payload = self.engine.create_execution_prompt(
                task_description=description,
                accumulated_context=full_context,
                target_file=target,
                project_language=self.state['target_language'],
                model_name=model_name
            )

            print(f"  -> Calling LLM to {action.lower()} content for {target}...")
            raw_content = self.client.generate_content(payload)
            
            if raw_content.startswith("ERROR:"):
                print(f"  -> LLM/Client Error: {raw_content}")
                self.state['errors'].append(f"LLM failed to generate content for {target}")
                return False
            
            # Dispatch to editor (it handles modify vs create based on existence)
            if full_path.exists():
                success = self.editor._execute_modify(full_path, raw_content)
            else:
                success = self.editor._execute_create(full_path, raw_content)
            
            # Update agent state with the new/modified content
            if success:
                self.state['context_files'][target] = raw_content
                
        elif action == 'CREATE_DIR': # <-- NEW FOLDER ACTION
            success = self.editor._execute_create_dir(full_path)
            
        elif action == 'DELETE_DIR': # <-- NEW FOLDER ACTION
            # NOTE: We don't remove files from state context here, as files inside 
            # the deleted directory might still be relevant for planning/reporting.
            success = self.editor._execute_delete_dir(full_path)
        
        elif action == 'REPORT_SUCCESS':
            # ACTION 6: Final step
            print(f"  -> Final action completed. Agent task finished.")
            success = True
        
        else:
            print(f"  -> WARNING: Unknown action type '{action}'. Skipping step.")
            self.state['errors'].append(f"Unknown action: {action}")
        
        # Short delay for better log reading
        time.sleep(0.5) 
        return success

    def run_task(self, goal: str, model_name: str) -> bool:
        """
        Main entry point for the agent. Runs the entire Observe-Plan-Act loop.
        """
        self.state['errors'] = [] # Clear errors for new task
        self.state['context_files'] = {} # Clear context for new task
        
        print(f"\n=======================================================")
        print(f"AGENT STARTING TASK: {goal}")
        print(f"Project Root: {self.project_root}")
        print(f"Model: {model_name}")
        print(f"=======================================================")

        # 1. Observe (Gather the high-level codebase summary)
        print("\n--- AGENT: OBSERVING CODEBASE ---")
        codebase_summary = self.analyzer.get_project_summary()
        
        if codebase_summary.startswith("ERROR"):
            print(f"CRITICAL ERROR: Failed to get codebase summary. {codebase_summary}")
            return False

        # 2. Plan (Generate the steps)
        self.plan = self._generate_plan(goal, codebase_summary, model_name)
        
        if not self.plan:
            print("\nTASK FAILED: Plan generation failed. Aborting.")
            return False
            
        # 3. Act (Execute the plan iteratively)
        all_successful = True
        for i, step in enumerate(self.plan, 1):
            print(f"\n[STEP {i}/{len(self.plan)}] Executing plan step...")
            if not self._execute_step(step, model_name):
                print(f"PLAN EXECUTION FAILED at step {i}: {step.get('action')}. Aborting subsequent steps.")
                all_successful = False
                break
        
        # 4. Report
        print("\n=======================================================")
        if all_successful:
            print("AGENT TASK COMPLETED SUCCESSFULLY.")
        else:
            print("AGENT TASK FAILED TO COMPLETE.")
            print("Errors encountered:")
            for error in self.state['errors']:
                print(f"- {error}")
        print("=======================================================")
        
        return all_successful
