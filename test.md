version: "1.0"

# Global default settings (can be overridden per task)
defaults:
  model: sonnet  # Options: sonnet, opus, haiku (for prompt tasks)
  agent: claude  # Options: claude, codex (agent type to use for prompt tasks)
  execution_mode: sequential # Options: sequential, parallel
  branch_strategy: separate  # Options: separate (create new branches), main (work on main)
  auto_push: false  # Whether to push to remote after successful task completion
  abort_on_failure: true  # Abort all remaining tasks if one fails

tasks:
  - name: Make code changes
    type: prompt  # Optional, defaults to "prompt"
    prompt: |
      make changes to this project so that instead of specifying execution_mode of parallel or sequential
      we specify exectuion_step with a number value instead. all tasks with execution_step of 1 will execute in parallel
      all tasks with execution_step of 2 will also execute in parallle but only after step 1 is complete
    model: opus # Override default model

  - name: Run tests
    type: command
    depends_on:
      - Make code changes
    command: uv run pytest tests/ -v
    working_directory: .  # Optional: specify working directory
    timeout: 600  # Optional: timeout in seconds (default: 300)