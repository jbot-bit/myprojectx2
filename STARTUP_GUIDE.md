# Quick Startup Guide

## Batch Files for Easy Project Access

### 🚀 start_claude.bat (PROJECT VALIDATOR)
**Double-click this to validate your project before working**

What it does:
1. Activates Python virtual environment
2. Runs critical sync test (`test_app_sync.py`)
3. Shows git status
4. Displays project reminders
5. Confirms project is safe to work on

**IMPORTANT**: If sync test fails, the script will STOP and show errors. Do NOT proceed until you fix the mismatch between `gold.db` and `config.py`.

**To start Claude Code:** After validation passes, open a terminal in your project folder and run `claude`

### ✓ check_sync.bat (QUICK VALIDATION)
**Use this anytime to verify project integrity**

What it does:
- Runs `test_app_sync.py` to check database/config synchronization
- Returns pass/fail status
- Does NOT start Claude Code

**Use this:**
- After updating validated_setups database
- After modifying trading_app/config.py
- Before starting trading apps
- Anytime you want to verify project state

## Why This Matters

### Drift Prevention
These scripts prevent dangerous drift between:
- `gold.db` → `validated_setups` table (MGC ORB filters, RR values)
- `trading_app/config.py` → `MGC_ORB_SIZE_FILTERS` dictionary

**If these get out of sync:**
- Apps use WRONG filters
- Accept/reject wrong trades
- **REAL MONEY LOSSES in live trading**

### Claude Code Authority
When you launch via `start_claude.bat`:
- Claude loads `CLAUDE.md` (project instructions)
- Sees validated sync test results
- Understands current git branch/status
- Knows all critical project context
- Can prevent you from making dangerous changes

## Daily Workflow

1. **Validate project**: Double-click `start_claude.bat` to run sync checks
2. **Start Claude**: Open terminal and run `claude` in your project folder
3. **Make changes**: Work with Claude on strategies/configs
4. **After changes**: Claude will automatically run `test_app_sync.py`
5. **Quick check**: Double-click `check_sync.bat` anytime
6. **Before trading**: Always verify sync test passes

**Note:** If you're already in Claude Code (like right now!), you don't need to launch it again. Just run `start_claude.bat` or `check_sync.bat` to validate your project.

## Troubleshooting

**"Failed to activate virtual environment"**
- Ensure venv exists at project root
- Recreate: `python -m venv venv`

**"Sync test FAILED"**
- Read error messages carefully
- Fix mismatches between database and config.py
- See CLAUDE.md section: "Database and Config Synchronization"
- Never proceed until ALL TESTS PASS

**"Already in Claude Code"**
- You don't need to launch Claude again if you're already using it
- The batch files are for validation, not launching
- Just double-click `check_sync.bat` to validate anytime

## File Locations

```
myprojectx2_cleanpush/
├── start_claude.bat          ← Double-click to validate project
├── check_sync.bat            ← Quick validation
├── test_app_sync.py          ← Critical sync test
├── CLAUDE.md                 ← Project instructions
├── gold.db                   ← Database
├── trading_app/
│   ├── config.py            ← Must match database
│   └── ...
└── venv/                     ← Python environment
```

## Remember

**After ANY changes to strategies, database, or config files, ALWAYS run:**
```bash
python test_app_sync.py
```

**DO NOT PROCEED if this test fails.**

Your batch files automate this for you, but you can also run it manually anytime.
