# Common Workflows

## Set Up a New Project

```
1. get_status()
   → confirm dispatcher is running

2. create_organization(name="my_project", workspace_path="/absolute/path/to/project")
   → creates isolated workspace

3. create_agent(organization="my_project", name="lead", instructions_path="/path/to/lead.md")
   → root agent (no boss); tasks auto-route here

4. create_agent(organization="my_project", name="researcher",
               instructions_path="/path/to/researcher.md", boss="lead")
   → subordinate agent

5. create_task(title="Implement feature X", organization="my_project",
              description="Detailed requirements...")
   → auto-queued to "lead"; dispatcher picks it up
```

## Monitor Progress

```
get_status()
  → overall health, active workers, total cost

list_tasks(organization="my_project", status="in_progress")
  → what's running right now

get_task("MYPR-0001")
  → full timeline: all comments and run summaries

list_runs("MYPR-0001")
  → execution history per run

get_run("<run_id>")
  → step-by-step: reasoning, tool calls, output
```

## Steer or Intervene on a Task

```
# Redirect to a specific agent
add_comment(task_id="MYPR-0001", body="This needs research first @researcher")

# Take over a running task
preempt_task(task_id="MYPR-0001")
  → task becomes open, assigned to user

# Give feedback and re-queue
add_comment(task_id="MYPR-0001", body="Good start, also handle edge cases @lead")

# Retry a failed task with a different agent
retry_task(task_id="MYPR-0001", assignee="lead")
```

## Complete or Clean Up

```
# A task was assigned to user after an agent finished — review and close it
get_task("MYPR-0001")                 # read the timeline first
complete_task(task_id="MYPR-0001")   # mark done

# Cancel work that's no longer needed
cancel_task(task_id="MYPR-0002")     # irreversible

# Reopen a completed task for more work
reopen_task(task_id="MYPR-0001")     # status → open, assignee → user
add_comment(task_id="MYPR-0001", body="Also add pagination @lead")
```

## Write Effective Agent Instructions

Agent instructions are a plain markdown file. Key things to include:

- The agent's role and expertise
- What it should do when it receives a task
- Which other agents exist and when to route to them (using `@name`)
- When to escalate to `@user`

Example (`lead.md`):
```markdown
# lead

You are the lead developer for the payments service.

When you receive a task, plan the work and either implement it directly
or delegate to a specialist using @mentions in your final comment.

Your team:
- @backend_dev — API and database implementation
- @test_writer — writing and running tests

Escalate to @user when you need clarification on requirements or when
a task is complete and ready for review.
```

## Tips

- Always call `get_status()` first to confirm the dispatcher is running.
- Read the full timeline with `get_task()` before intervening — understand context before acting.
- The dispatcher automatically picks up `open` tasks assigned to agents. Tasks assigned to `user` are paused.
- Cost is tracked per-run and aggregated at task, agent, and organization levels.
- `preempt_task` is the only way to stop a running task — it cannot be canceled mid-run directly.
- `cancel_task` is irreversible. Prefer `preempt_task` + `complete_task` if you just want to stop work gracefully.
