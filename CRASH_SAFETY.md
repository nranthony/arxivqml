# Crash Safety & Data Durability Guide

This document explains how the arxivqml system protects against data corruption and crashes.

## MongoDB Safety (Built-in)

### **ACID Guarantees**

MongoDB provides **Durability** through journaling (enabled by default):

- **Journaling**: Writes operations to journal before applying to data
- **Atomic Operations**: Single-document updates are all-or-nothing
- **Crash Recovery**: Replays journal on restart

### **What's Protected**

✅ **Single document updates** - `update_one()`, `insert_one()` are atomic
✅ **No partial writes** - Documents are never half-updated
✅ **Auto-recovery** - MongoDB replays journal on restart after crash

### **What's NOT Protected**

⚠️ **Batch operations** - If script crashes mid-loop, some papers updated, some not
**Impact**: Low - just re-run migration script (idempotent operations)

---

## JSON File Safety (Custom Implementation)

### **The Problem**

Standard file writes are NOT crash-safe:

```python
# ❌ UNSAFE - File can be corrupted mid-write
with open('keywords.json', 'w') as f:
    json.dump(data, f)
```

**If crash happens during write:**
- File truncated or corrupted
- Invalid JSON syntax
- App won't start (can't load mappings)

### **Our Solution: Atomic Writes**

Implemented in `database.py:save_keyword_mappings()`:

```python
# ✅ SAFE - Atomic write with backup
def save_keyword_mappings(data, json_path):
    1. Create backup: keywords.json → keywords.json.bak
    2. Write to temp: .keywords_XXX.json.tmp
    3. Atomic rename: temp → keywords.json (overwrites)
```

**Protection:**
- ✅ Backup created before write
- ✅ Atomic rename (OS-level operation)
- ✅ Never corrupts existing file
- ✅ Auto-fallback to `.bak` if corruption detected

---

## Error Handling

### **1. JSON Loading** (`load_keyword_mappings`)

```python
Try: Load keywords.json
  ↓ JSON corrupted?
Try: Load keywords.json.bak (backup)
  ↓ Backup also corrupted?
Fallback: Use empty mappings (safe default)
```

### **2. Database Updates** (`normalize_paper_keywords`)

```python
For each paper:
  Try: Normalize and update keywords
  Catch: Log error, continue with next paper
Return: (updated_count, error_count)
```

**Result**: Partial failures don't stop entire migration

### **3. Streamlit Merge UI**

```python
Try:
  - Save mappings (atomic write)
  - Update database
  - Show success
Catch:
  - Show error message
  - Inform user: "keywords.json.bak is safe"
```

---

## Crash Scenarios & Recovery

### **Scenario 1: Crash During Migration**

**What happens:**
- MongoDB: Some papers updated, some not
- JSON file: Protected by atomic write

**Recovery:**
```bash
# Just re-run migration (idempotent)
python migrate_keywords.py
```

**Why safe:**
- Normalization is idempotent (same input → same output)
- Already-normalized papers: No change (skipped)
- Remaining papers: Get normalized

---

### **Scenario 2: Crash During JSON Write**

**What happens:**
- Temp file write interrupted
- Original `keywords.json` untouched
- Backup `keywords.json.bak` intact

**Recovery:**
```bash
# Automatic - app detects corruption and uses backup
streamlit run arxivqml/app.py
```

**Or manual:**
```bash
# Restore from backup
cp keywords.json.bak keywords.json
```

---

### **Scenario 3: Power Failure**

**MongoDB:**
- Journal replays on restart
- Data consistent to last committed operation

**JSON Files:**
- Atomic write ensures no corruption
- Backup available if needed

**Recovery:**
```bash
# MongoDB auto-recovers on restart
# No action needed

# Check data integrity
python migrate_keywords.py
```

---

## File Backup System

### **Automatic Backups**

Every time `save_keyword_mappings()` is called:

1. **Before write**: `keywords.json` → `keywords.json.bak`
2. **During write**: New data → `.keywords_XXX.json.tmp`
3. **Atomic replace**: Temp file → `keywords.json`

### **Backup Locations**

```
arxivqml/
├── keywords.json           # Current (always valid)
├── keywords.json.bak       # Previous version (auto-created)
└── .keywords_*.json.tmp    # Temp files (auto-cleaned)
```

### **Manual Backup (Recommended)**

For extra safety before major operations:

```bash
# Before running migration
cp keywords.json keywords.json.$(date +%Y%m%d-%H%M%S)

# Results in: keywords.json.20251007-143022
```

---

## Best Practices

### **For Users**

1. **Run migration in test mode first**
   ```bash
   # Optional: Create manual backup
   cp keywords.json keywords.json.backup

   # Run migration
   python migrate_keywords.py
   ```

2. **Check errors**
   - Watch for "Errors encountered: X" in output
   - If errors > 0, review logs before proceeding

3. **Backup before bulk operations**
   - Before merging many keywords in UI
   - Before editing keywords.json manually

### **For Developers**

1. **Never write files directly**
   ```python
   # ❌ Don't do this
   with open('file.json', 'w') as f:
       json.dump(data, f)

   # ✅ Use atomic write
   database.save_keyword_mappings(data)
   ```

2. **Always handle exceptions**
   ```python
   try:
       result = database.normalize_paper_keywords(collection, mappings)
   except Exception as e:
       print(f"Error: {e}")
       # Handle gracefully
   ```

3. **Make operations idempotent**
   - Re-running should be safe
   - Check before modifying

---

## Recovery Checklist

If something goes wrong:

- [ ] Check MongoDB is running: `mongosh` or check logs
- [ ] Check if `keywords.json.bak` exists
- [ ] Try re-running migration: `python migrate_keywords.py`
- [ ] Check error count in output
- [ ] If JSON corrupted: `cp keywords.json.bak keywords.json`
- [ ] If still broken: Check issue tracker or restore from manual backup

---

## Technical Details

### **Atomic Rename Operation**

**Unix/Linux/macOS:**
```python
os.rename(temp, target)  # Atomic - overwrites target
```
✅ Truly atomic - kernel guarantees no partial writes

**Windows:**
```python
os.remove(target)        # Delete old file first
os.rename(temp, target)  # Then rename
```
⚠️ Not atomic, but file lock prevents corruption (file can't be deleted if open)

### **fsync() Call**

```python
f.flush()              # Flush Python buffer
os.fsync(f.fileno())   # Force OS to write to disk
```

Forces immediate disk write (bypasses OS cache) - ensures durability even in power failure.

---

## Summary

| Component | Protection | Recovery |
|-----------|-----------|----------|
| **MongoDB Data** | Built-in journaling | Automatic on restart |
| **keywords.json** | Atomic write + backup | Auto-fallback to .bak |
| **Migration** | Per-paper error handling | Re-run script |
| **Streamlit UI** | Try-catch with user feedback | Manual retry |

**Bottom line:** System is crash-resistant. Data corruption extremely unlikely. Recovery is straightforward.
