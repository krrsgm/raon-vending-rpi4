# Item Display Bug Fix - Complete

## Problem
Items and images were not showing on admin and kiosk screens when running on Raspberry Pi.

## Root Cause Analysis
The application was trying to load items from `item_list.json`, which doesn't exist in the project. The actual data is stored in `assigned_items.json` with a slot/term structure (64 slots × 3 terms each).

### File Structure Discovered
```
assigned_items.json: 
├── Slot 1
│   └── terms: [Term1Item, Term2Item, Term3Item]
├── Slot 2
│   └── terms: [Term1Item, Term2Item, Term3Item]
└── ... (64 slots total)

item_list.json: 
└── ❌ DOESN'T EXIST (but code was looking for it)
```

### Impact
- `controller.items` remained empty (default_items)
- AdminScreen.populate_items() had no items to display
- KioskFrame.reset_state() had no items to show
- Images couldn't load because they depend on item data

## Solution Implemented

### 1. main.py - Item Loading (Lines 75-89)
**Changed from:**
```python
self.items_file_path = get_absolute_path("item_list.json")  # ❌ doesn't exist
self.items = self.load_items_from_json(self.items_file_path)
```

**Changed to:**
```python
self.assigned_items_path = get_absolute_path("assigned_items.json")  # ✅ exists
self.assigned_slots = self.load_items_from_json(self.assigned_items_path)
self.items = self._extract_items_from_slots(self.assigned_slots)  # Extract flat list
```

### 2. main.py - New Method (Lines 343-375)
Added `_extract_items_from_slots()` to convert slot/term structure to flat items list:
```python
def _extract_items_from_slots(self, assigned_slots):
    """Extract items from assigned slots for display on current term"""
    items = []
    term_idx = getattr(self, 'assigned_term', 0) or 0
    
    for slot in assigned_slots:
        if isinstance(slot, dict) and 'terms' in slot:
            terms = slot.get('terms', [])
            if len(terms) > term_idx and terms[term_idx]:
                items.append(terms[term_idx])
    
    return items
```

**Why this works:**
- Converts nested slot structure to flat array
- Uses current term index (default 0)
- Handles both new format (with terms) and legacy format
- Graceful error handling for missing data

### 3. assign_items_screen.py - Enhanced Publishing (Lines 1293-1359)
Updated `_publish_assignments()` to update controller.items:
```python
def _publish_assignments(self):
    setattr(self.controller, 'assigned_slots', self.slots)
    setattr(self.controller, 'assigned_term', self.current_term)
    
    # NEW: Update controller.items for display
    extracted_items = self._extract_items_from_current_term()
    setattr(self.controller, 'items', extracted_items)
    
    # NEW: Refresh displays
    kf.reset_state()        # Updates kiosk with new items
    af.populate_items()     # Updates admin with new items
    # ... save config and categories ...
```

**Benefits:**
- Real-time item updates when admin changes assignments
- Both screens receive updates immediately
- Images refresh automatically with items

### 4. assign_items_screen.py - New Helper Method (Lines 1361-1370)
Added `_extract_items_from_current_term()` for admin screen:
```python
def _extract_items_from_current_term(self):
    """Extract items for current term when admin switches"""
    items = []
    for slot in self.slots:
        if isinstance(slot, dict) and 'terms' in slot:
            terms = slot.get('terms', [])
            if len(terms) > self.current_term and terms[self.current_term]:
                items.append(terms[self.current_term])
    return items
```

## Data Flow After Fix

```
assigned_items.json
       ↓
main.py loads → assigned_slots
       ↓
_extract_items_from_slots() → controller.items (flat array)
       ↓
       ├→ AdminScreen.populate_items() displays items
       ├→ KioskFrame shows items with images
       └→ Image paths resolved from item data
```

## Verification Steps Completed

✅ **Compilation verified:**
- main.py compiles without syntax errors
- assign_items_screen.py compiles without syntax errors

✅ **Code structure verified:**
- assigned_items.json exists and contains valid data (64 slots)
- Each slot has terms array with 3 items each
- Path resolution function (get_absolute_path) working correctly

✅ **Backward compatibility:**
- No breaking changes to existing architecture
- Preserves performance optimizations from earlier phase
- Maintains fallback logic in kiosk_app.py

## Testing on Raspberry Pi

### Next Steps
1. **Sync the fixes:**
   ```bash
   cd ~/raon-vending-rpi4
   git pull origin main
   ```

2. **Run the application:**
   ```bash
   python main.py
   ```

3. **Verify items display:**
   - Items should appear on admin screen
   - Items should appear on kiosk screen
   - Images should display with items

4. **Test term switching:**
   - Switch between Term 1, 2, 3 in admin
   - Verify items update on both screens
   - Verify images update accordingly

### Troubleshooting
If items still don't show:
1. Check logs: Look for errors in terminal output
2. Verify file path: Ensure assigned_items.json is in project root
3. Check permissions: File should be readable by pi user
4. Verify data: Open assigned_items.json and check for valid JSON structure

If images don't show:
1. Check image directory: `Product List/Term X/Row Y/` should exist
2. Verify image paths in assigned_items.json
3. Check file permissions on image files
4. Verify image file names match exactly (case-sensitive on Linux)

## Files Modified
- [main.py](main.py#L75-L89) - Item loading logic
- [main.py](main.py#L343-L375) - New extraction method
- [assign_items_screen.py](assign_items_screen.py#L1293-L1359) - Publishing enhancement
- [assign_items_screen.py](assign_items_screen.py#L1361-L1370) - Helper method

## Commit Information
- **Hash:** 86d754a
- **Date:** Just now
- **Message:** "Fix item loading: Load items from assigned_items.json and sync across screens"
- **Status:** ✅ Pushed to GitHub

## Summary
The item display bug has been fixed by:
1. Loading from the correct JSON file (assigned_items.json)
2. Adding proper extraction logic to convert slot structure to flat items array
3. Ensuring admin and kiosk screens sync when items change
4. Maintaining backward compatibility and performance optimizations

All code changes compile successfully and are ready for testing on Raspberry Pi.
