# Scripts Directory

## Core Scripts (scripts/)

### Essential Utilities
- **backup_db.sh** - Database backup utility
- **deploy.sh** - Deployment script
- **export_db_to_excel.py** - Export database to Excel for analysis
- **inspect_db.py** - Database inspection and debugging tool
- **enhance_nihr_grants.py** - PDF/link enhancement for grants
- **generate_nihr_embeddings.py** - Generate embeddings for new grants
- **generate_grant_summaries.py** - Generate AI summaries for grants
- **convert_docx_to_txt.py** - Convert DOCX files to text
- **setup_slack_bot.sh** - Slack bot setup (if using Slack integration)

## Subdirectories

### tests/
All test scripts and validation tools:
- `test_*.py` - Unit and integration tests
- `analyze_*.py` - Analysis tools
- `monitor_*.py` - Monitoring utilities
- `validate_*.py` - Validation scripts

### sme/ (SME Knowledge System)
Scripts for managing Subject Matter Expert knowledge:
- `add_expert_example.py` - Add new expert examples
- `create_expert_examples_table.py` - Initialize expert examples table
- `view_expert_examples.py` - View existing expert examples
- `import_one_pager.py` - Import one-pager documents
- `debug_sme_knowledge.py` - Debug SME retrieval
- `setup_sme_knowledge.sh` - Setup SME knowledge system

### dev/ (Development Tools)
Development and analysis tools:
- `run_eval.py` - Run evaluation benchmarks
- `nihr_tab_aware_parsing.py` - NIHR tab parsing development
- `track_api_loading.py` - Track API startup performance
- `data_balance_report.md` - Data balance analysis

### archive/ (Historical/One-Time Scripts)
Scripts that have already been run or are no longer actively used:

#### archive/migrations/
Database migration scripts (already applied to production):
- `migrate_add_total_fund_gbp.py`
- `migrate_add_grant_summaries.py`
- `migrate_fix_timezones.py`
- `migrate_fix_prize_funding.py`
- `migrate_fix_upstream_funding.py`
- `migrate_clean_titles.py`
- `migrate_refine_funding_decimals.py`

Note: Keep these for reference but they should not be re-run on production.

#### archive/
- `reset_nihr_data.py` - Reset NIHR data (dev only)

### debug/
Debug and diagnostic scripts:
- `debug_stuck_grant.py` - Diagnose grant recommendation issues
- `fix_diversity.py` - Diversity fix reference implementation

---

## Quick Reference

**Need to:**
- Backup database? → `./backup_db.sh`
- Export data? → `python scripts/export_db_to_excel.py`
- Check database? → `python scripts/inspect_db.py`
- Generate embeddings? → `python scripts/generate_nihr_embeddings.py`
- Enhance grants with PDFs? → `python scripts/enhance_nihr_grants.py`
- Run tests? → `python tests/test_*.py`
- Add SME knowledge? → `python scripts/sme/add_expert_example.py`

---

**Last Updated**: November 18, 2025
