# Cleanup Checklist

All files have been **copied** to organized locations. Originals remain in place.

## ✅ Once Verified, Safe to Delete:

### Documentation (Root `docs/` folder)
After verifying the essential 8 docs are sufficient, you can delete:
```bash
# Already archived - safe to delete after verification
cd docs
rm GPT-5.1-MIGRATION.md
rm GPT-5.1-QUICK-START.md
rm CHANGELOG-GPT-5.1.md
rm GRANT-FILTERING-FIX.md
rm FIX_RESOURCE_EXTRACTION_BUG.md
rm README_NIHR_FIXES.md
rm SME-KNOWLEDGE-RETRIEVAL.md
rm IMPLEMENTATION_GUIDE.md
rm IMPLEMENTATION_SUMMARY.md
rm IMPLEMENTATION_COMPLETE.md
rm COMPLETE_IMPLEMENTATION_SUMMARY.md
rm INTEGRATION_GUIDE.md
rm QUICK_FIX_REFERENCE.md
rm QUICK_REFERENCE.md
rm BEFORE_AFTER_COMPARISON.md
rm NEXT_STEPS.md
```

### Scripts (Root `scripts/` folder)
After verifying organized subdirectories work:
```bash
# Test files (now in tests/)
cd scripts
rm test_*.py
rm analyze_embeddings.py
rm analyze_enhancement_results.py
rm check_data_balance.py
rm monitor_*.py
rm validate_enhancement.py
rm verify_nihr_tab_resources.py

# Migrations (now in scripts/archive/migrations/)
rm migrate_*.py
rm reset_nihr_data.py

# SME scripts (now in scripts/sme/)
rm add_expert_example.py
rm create_expert_examples_table.py
rm view_expert_examples.py
rm import_one_pager.py
rm debug_sme_knowledge.py
rm setup_sme_knowledge.sh

# Dev tools (now in scripts/dev/)
rm run_eval.py
rm nihr_tab_aware_parsing.py
rm data_balance_report.md
rm track_api_loading.py
```

## ⚠️ Keep These Files (Essential):

### Root Directory
- ✅ README.md
- ✅ start.sh, start_api.sh, start_ui.sh
- ✅ grants.db (and backup files)

### docs/ (8 essential files)
- ✅ README.md
- ✅ QUICK_START.md
- ✅ claude_code_quick_start.md
- ✅ FOR_CLAUDE_CODE.md
- ✅ EMBEDDING_GENERATION_GUIDE.md
- ✅ intelligent_link_following_implementation.md
- ✅ MASTER_IMPLEMENTATION_GUIDE.md
- ✅ archive/ (entire folder)

### scripts/ (9 core utilities)
- ✅ README.md
- ✅ backup_db.sh
- ✅ deploy.sh
- ✅ enhance_nihr_grants.py
- ✅ generate_nihr_embeddings.py
- ✅ export_db_to_excel.py
- ✅ inspect_db.py
- ✅ generate_grant_summaries.py
- ✅ convert_docx_to_txt.py
- ✅ setup_slack_bot.sh
- ✅ All subdirectories: tests/, sme/, dev/, debug/, archive/

## 📋 Verification Steps:

1. **Test organized structure works:**
   ```bash
   python tests/test_nihr_query.py
   python scripts/sme/view_expert_examples.py
   ./scripts/backup_db.sh
   ```

2. **Verify documentation is accessible:**
   ```bash
   cat docs/README.md
   cat scripts/README.md
   ```

3. **Once comfortable, run cleanup:**
   ```bash
   # Backup first!
   ./scripts/backup_db.sh
   
   # Then delete originals (carefully!)
   # See commands above
   ```

## 🔄 Alternative: Git Cleanup

If using git, you can remove from git but keep locally:
```bash
git rm docs/GPT-5.1-*.md
git rm docs/*IMPLEMENTATION*.md
git rm scripts/test_*.py
git rm scripts/migrate_*.py
# etc...
git commit -m "Archive unnecessary docs and reorganize scripts"
```

---

**Created**: November 18, 2025
**Status**: Ready for verification and cleanup
