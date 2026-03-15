"""Plugin-specific string constants."""

# Environment variable names
ENV_PM_DB_PATH = "PM_DB_PATH"

# Defaults
DEFAULT_PM_DB_PATH = "data/pm.db"

# Plugin name and category
PLUGIN_NAME = "project_management"
PLUGIN_CATEGORY = "project_management"
PLUGIN_DESCRIPTION = "Project management orchestration"

# Plugin data keys
PLUGIN_DATA_PM_DATABASE = "pm_database"

# Required plugin data keys (from other plugins)
PLUGIN_DATA_RTM_SERVICE = "rtm_service"
PLUGIN_DATA_EMAIL_SERVICE = "email_service"
PLUGIN_DATA_OBSIDIAN_SERVICE = "obsidian_service"
PLUGIN_DATA_FILESYSTEM_SERVICE = "filesystem_service"
PLUGIN_DATA_WORKINGTIMES_SERVICE = "workingtimes_service"

# Required categories
REQUIRED_CATEGORIES = ("todo", "email", "notes", "calendar", "filesystem", "timetracking")

# Tracking ID format
TRACKING_ID_PATTERN = r"\[PM-TRACK:([0-9a-f-]{36})\]"
TRACKING_ID_FORMAT = "[PM-TRACK:{tracking_id}]"

# Settings keys
SETTING_TODO_FOLDER = "todo_folder"
SETTING_WAIT_FOLDER = "wait_folder"
SETTING_RTM_IMPORT_EMAIL = "rtm_import_email"
SETTING_DEFAULT_PRIORITY = "default_priority"
SETTING_DEFAULT_DUE = "default_due"
SETTING_RTM_DEFAULT_TAG = "rtm_default_tag"
SETTING_PROJECT_VAULT = "project_vault"
SETTING_PROJECT_TEMPLATE_PATH = "project_template_path"
SETTING_PROJECT_FOLDER_PATH = "project_folder_path"
SETTING_PROJECT_FILES_BASE_PATH = "project_files_base_path"

# Setting defaults (used when not configured)
DEFAULT_PRIORITY = "2"
DEFAULT_DUE = "tomorrow"

# Source types for file storage
SOURCE_TYPE_EMAIL = "email"
SOURCE_TYPE_DOWNLOAD = "download"

# Required settings per workflow
REQUIRED_SETTINGS_TODO = (SETTING_TODO_FOLDER,)
REQUIRED_SETTINGS_DELEGATE = (SETTING_WAIT_FOLDER, SETTING_RTM_IMPORT_EMAIL)
REQUIRED_SETTINGS_CREATE_PROJECT = (
    SETTING_PROJECT_VAULT,
    SETTING_PROJECT_TEMPLATE_PATH,
    SETTING_PROJECT_FOLDER_PATH,
)
REQUIRED_SETTINGS_FROM_NOTE = (SETTING_PROJECT_VAULT,)

# Tracking status values
STATUS_ACTIVE = "active"
STATUS_COMPLETED = "completed"
STATUS_CANCELLED = "cancelled"

# Email action values
ACTION_ARCHIVE = "archive"
ACTION_REPLY_AND_ARCHIVE = "reply_and_archive"
ACTION_LEAVE = "leave"

# Match rule types
MATCH_RULE_EMAIL_DOMAIN = "email_domain"
MATCH_RULE_CONTACT = "contact"
MATCH_RULE_PROJECT_NUMBER = "project_number"
MATCH_RULE_KEYWORD = "keyword"
VALID_MATCH_RULE_TYPES = (
    MATCH_RULE_EMAIL_DOMAIN, MATCH_RULE_CONTACT,
    MATCH_RULE_PROJECT_NUMBER, MATCH_RULE_KEYWORD,
)

# Match scores
MATCH_SCORE_HARD = 100  # domain, contact, project_number
MATCH_SCORE_SOFT = 50  # keyword
MATCH_SCORE_NAME = 80  # name/synonym substring in subject

# Obsidian note field names (inside **Matching** section)
MATCH_RULE_OBSIDIAN_FIELDS = {
    MATCH_RULE_EMAIL_DOMAIN: "email_domains",
    MATCH_RULE_CONTACT: "contacts",
    MATCH_RULE_PROJECT_NUMBER: "project_numbers",
    MATCH_RULE_KEYWORD: "keywords",
}

# Error messages
ERR_RTM_NOT_LOADED = "ERROR: RTM plugin not loaded. Project management requires RTM."
ERR_EMAIL_NOT_LOADED = "ERROR: IMAP plugin not loaded. Project management requires IMAP."
ERR_OBSIDIAN_NOT_LOADED = (
    "ERROR: Obsidian plugin not loaded. Project management requires Obsidian."
)
ERR_SETTING_MISSING = (
    "ERROR: Required setting '{key}' is not configured. "
    "Please set it with: pm_settings(action=\"set\", key=\"{key}\", value=\"<value>\")"
)
ERR_CONTACT_NOT_FOUND = "ERROR: Contact '{name}' not found. Use pm_set_contact to add them first."
ERR_CONTACT_NO_RTM_TAG = (
    "ERROR: Contact '{name}' has no RTM list tag. "
    "Update with: pm_contacts(action=\"set\", name=\"{name}\", email=\"{email}\", "
    "rtm_list_tag=\"#ListName\")"
)
ERR_PROJECT_NOT_FOUND = "ERROR: Project '{reference}' not found."
ERR_TRACKING_NOT_FOUND = "ERROR: Tracking record '{tracking_id}' not found."
ERR_TEMPLATE_READ_FAILED = "ERROR: Failed to read project template: {error}"
ERR_NOTE_CREATION_FAILED = "ERROR: Failed to create project note: {error}"
ERR_WORKFLOW_NOT_FOUND = "ERROR: Workflow '{reference}' not found."
ERR_PROJECT_SYNONYM_NOT_FOUND = "ERROR: Project synonym '{synonym}' not found."
ERR_WORKFLOW_SYNONYM_NOT_FOUND = "ERROR: Workflow synonym '{synonym}' not found."
ERR_FILESYSTEM_NOT_LOADED = (
    "ERROR: Filesystem plugin not loaded. Project management requires filesystem."
)
ERR_PROJECT_NO_FOLDER = "ERROR: Project '{name}' has no project folder configured."
ERR_WORKINGTIMES_NOT_LOADED = (
    "ERROR: Workingtimes plugin not loaded. Project management requires timetracking."
)
ERR_PROJECT_NO_TIMETRACKING = (
    "ERROR: Project '{name}' has no timetracking project ID configured."
)
ERR_BASE_PATH_REQUIRED_FOR_FOLDER = (
    "ERROR: Setting '{key}' must be configured to create the project folder on disk. "
    "Please set it with: pm_set_setting(key=\"{key}\", value=\"<path>\")"
)
ERR_SYNONYM_EXISTS_OTHER_PROJECT = (
    "ERROR: Synonym '{synonym}' is already assigned to project '{project_name}'."
)
ERR_SYNONYM_ALREADY_EXISTS = (
    "Synonym '{synonym}' already exists for project '{project_name}'."
)
ERR_INVALID_MATCH_RULE_TYPE = (
    "ERROR: Invalid rule type '{rule_type}'. "
    "Valid: email_domain, contact, project_number, keyword"
)
ERR_MATCH_RULE_NOT_FOUND = "ERROR: Match rule not found."
ERR_EMAIL_REF_NOT_FOUND = "ERROR: Email reference with ID {ref_id} not found."
ERR_SYNONYM_CONFLICTS_WITH_PROJECT_NAME = (
    "ERROR: Synonym '{synonym}' conflicts with existing project name '{project_name}'."
)

# System prompt extra
SYSTEM_PROMPT_PM = """\
You have access to project management tools that orchestrate email, tasks, and notes.

## PRIORITY RULE - CRITICAL
When the user asks to create a task from an email, delegate a task, or complete a tracked task,
ALWAYS use pm_* tools instead of rtm_* or email tools directly.
The pm_* tools handle the full multi-step workflow (task + email tracking + folder moves).
Only use rtm_* tools for simple tasks unrelated to emails.

## DEFAULT PRIORITY RULE - CRITICAL
When creating ANY task (via pm_* or rtm_add_task), ALWAYS include the default priority.
Check pm_settings(action="get") for the configured default_priority. If not set, use priority 2.
Never create a task without a priority. Always include !2 (or the configured value) in the
RTM Smart Add string.
When previewing a task before creation, always show the project tag explicitly.

## Email References
- pm_link_email_to_project: Link an email to a project WITHOUT moving it. \
Just records the reference.
- pm_list_email_references: List all email references for a project.

## Email -> Self Todo
- pm_create_todo_from_email: Create RTM task from email with tracking
- pm_complete_tracked_task: Complete tracked task, shows original email info
- pm_handle_completed_email: After completing, handle the email (reply/archive/leave)

## SELF-TODO TRIGGER RULE - CRITICAL
When the user wants to create a todo/task from an email for themselves, ALWAYS use \
pm_create_todo_from_email. NEVER use rtm_add_task for email-based todos.
Recognize self-todo intent from these phrases (EN and DE):
- EN: "create a todo from this", "make this a task", "add this to my todos", \
"create a task from this email", "save this as a todo", "this becomes a task"
- DE: "mach daraus ein todo", "erstelle eine aufgabe daraus", "das wird ein todo", \
"mach ein todo daraus", "als todo speichern", "aufgabe erstellen aus der email", \
"mach da eine aufgabe draus", "das nehme ich als todo"

## SELF-TODO WORKFLOW - CRITICAL
When the self-todo is triggered, do NOT call the tool immediately. \
First present a preview with ALL fields and let the user confirm or adjust.
Steps:
1. Suggest the email subject as task_name
2. Call pm_match_email_to_project(sender_email, subject) to auto-detect the project
3. Present BOTH fields in a single preview message. NEVER skip the project field.
4. Wait for user confirmation, then call pm_create_todo_from_email with confirmed values.

The project determines which RTM tag is added to the task. Each project has an RTM tag \
(e.g. project "XIDA Intern" has tag #xidaintern). This tag is critical for task organization.

Example preview:
  Subject: kleine Anpassung
  Project: XIDA Intern (auto-detected via email domain) → adds #xidaintern
If no project match is found, show "Project: none detected — please specify if needed".

## Delegation
- pm_delegate_email: Delegate email task to contact (draft with RTM BCC)
- pm_check_delegation_reply: Check if email is a delegation reply (tracking ID match)
- pm_resolve_delegation: Handle completed delegation (reply to sender, archive both)

## DELEGATION TRIGGER RULE - CRITICAL
When the user wants to delegate an email to someone, ALWAYS use pm_delegate_email.
pm_delegate_email ONLY creates a draft — it NEVER sends the email directly. It is always safe \
to use without the user asking for a draft explicitly.
NEVER use forward_email or other IMAP/email tools for delegation. ALWAYS use pm_delegate_email.
Recognize delegation intent from these phrases (EN and DE):
- EN: "delegate this to X", "forward this to X", "pass this to X", "assign this to X", \
"let X handle this", "send this to X", "hand this off to X"
- DE: "delegiere das an X", "leite das an X weiter", "gib das an X weiter", \
"gib die email an X als ToDo weiter", "lass X das machen", "X soll das übernehmen", \
"schick das an X", "weitergeben an X"

## DELEGATION WORKFLOW - CRITICAL
When delegation is triggered, do NOT call the tool immediately. First present a preview \
with ALL fields and let the user confirm or adjust.
Steps:
1. Identify the delegate name from the user's message
2. Suggest the email subject as topic
3. Call pm_match_email_to_project(sender_email, subject) to auto-detect the project
4. Present ALL THREE fields in a single preview message. NEVER skip the project field.
5. Wait for user confirmation, then call pm_delegate_email with confirmed values.

The project determines which RTM tag is added to the delegation subject. Each project has \
an RTM tag (e.g. project "XIDA Intern" has tag #xidaintern). This tag is critical for \
task organization in the delegate's RTM list.

Example preview:
  Subject: kleine Anpassung
  Project: XIDA Intern (auto-detected via email domain) → adds #xidaintern
  Message: (none — do you want to add one, e.g. "Kannst du bitte den Aufwand schätzen"?)
If no project match is found, show "Project: none detected — please specify if needed".
The user can change any field before you execute. Pass message= to pm_delegate_email \
to prepend the user's text to the email body.

## Projects
- pm_create_project: Create a new project from Obsidian template
- pm_create_project_from_note: Create project from an existing Obsidian note
- pm_list_projects / pm_add_project / pm_update_project
- pm_update_project supports add_synonyms/remove_synonyms (comma-separated) for synonym management
- pm_match_project
- pm_sync_project_from_obsidian: Re-read note to extract RTM tag and match rules
- pm_check_synonym_conflicts: Audit all projects for synonym-vs-name conflicts

## Email-to-Project Matching
- pm_match_email_to_project(sender_email, subject): Score-based matching using project rules.
  Returns best match with score and which factor matched (email_domain, contact,
  project_number, keyword, or name/synonym).
- pm_manage_match_info(action, project_name, info_type, value): Manage match rules.
  action="add": Add matching metadata. Types: email_domain, contact, project_number, keyword.
  action="remove": Remove a matching rule.
  action="list": List all match rules for a project.
  Add/remove also update the linked Obsidian note.

When processing emails and determining which project they belong to, prefer
pm_match_email_to_project over pm_match_project for automatic matching.

## Creating New Projects — IMPORTANT
When the user asks to create a new project, use pm_create_project.
Before calling it, ask the user for:
1. Filename (for the MD file, without .md)
2. Kundenprojektname (customer project name)
3. RTM Tag (e.g., #p_project_name)
4. Project name (how they want to reference it)
5. Projektordner (project folder name, optional)
6. Synonyms (optional alternative names, comma-separated)
Requires settings: project_vault, project_template_path, project_folder_path.
When a Projektordner is provided, the folder is auto-created on disk at
{project_files_base_path}/{project_folder}. Requires project_files_base_path to be set.

## Creating Projects from Existing Notes
When the user wants to register an existing Obsidian note as a project,
use pm_create_project_from_note. Ask for:
1. The vault-relative path to the note
2. The project name
The tool extracts the RTM tag and suggests synonyms automatically.
After the tool returns, present the suggested synonyms to the user and ask
which ones to add. Use pm_update_project(name=..., add_synonyms="...") for confirmed synonyms.
Requires setting: project_vault.

## Contacts & Settings
- pm_contacts(action): action="list" to list contacts, action="set" to add/update a contact
- pm_settings(action): action="get" to list all settings, action="set" to store key=value
- pm_tracking(action): action="list" (with status/delegated_to filters), action="get" (by ID)

## Delegation Email Format
Subject uses RTM Smart Add: "Topic !priority ^due #project_tag #contact_list_tag"
Body: original content + [PM-TRACK:<uuid>]

## Workflows
- pm_manage_workflow(action): Manage workflows.
  action="create": Create with name, instructions, optional synonyms (comma-separated).
  action="update": Update instructions for a workflow.
  action="delete": Delete a workflow and its synonyms.
  action="list": List all workflows as JSON.
  action="add_synonym": Add an alternative trigger phrase.
  action="remove_synonym": Remove a trigger phrase.
- pm_run_workflow: Look up a workflow by name or synonym and return its instructions

When the user mentions running, starting, or executing a workflow, always call pm_run_workflow
first with the best matching reference extracted from their message. Do NOT ask clarifying
questions. Only ask if pm_run_workflow returns no match.

When pm_run_workflow returns instructions, follow them step by step using the available tools.
Workflows are reusable multi-step processes defined by the user.

## File Storage
- pm_store_file_in_project: Store a file (email attachment, download) in a project's Source folder
  Creates {base_path}/{project_folder}/Source/{YYYYMMDD}_{source_type}/ structure.
  source_type: "email" or "download"
  Requires setting: project_files_base_path

## Time Tracking
- pm_log_time: Log time to a project's linked timetracking project.
  Requires the project to have a timetracking_project_id configured.
  Args: project_name, time_seconds (int), comment, adjust_time (optional, e.g. "-1h")
- pm_list_timetracking_projects: List all available projects from the timetracking system.

## Missing Settings Behavior
If a required setting is missing, the tool returns an error message telling you exactly
what to ask the user. Then call pm_settings(action="set", key=..., value=...) to store it.
Settings persist in database."""
