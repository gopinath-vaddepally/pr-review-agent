# Comment Thread Status Fix

## Issue
Comments were being posted without explicit status, and resolved issues weren't properly marked with the correct status.

## What Was Fixed

### 1. New Comments Set to "Active"
**Before:**
```python
thread = CommentThread()
thread.comments = [Comment(content=comment["content"])]
# No status set - defaults to unknown
```

**After:**
```python
thread = CommentThread()
thread.comments = [Comment(content=comment["content"])]
thread.status = CommentThreadStatus.ACTIVE  # Explicitly set to Active
```

### 2. Resolved Issues Set to "Fixed"
**Before:**
```python
thread.status = CommentThreadStatus.FIXED
# Update thread
self.git_client.update_thread(...)
logger.info(f"  ✅ Resolved: {file_path}:{line_num}")
```

**After:**
```python
thread.status = CommentThreadStatus.FIXED
# Update thread
self.git_client.update_thread(...)
logger.info(f"  ✅ Resolved: {file_path}:{line_num} (Status: Fixed)")
```

## Azure DevOps Comment Thread Statuses

Azure DevOps supports these thread statuses:

| Status | Value | When to Use | Visible In |
|--------|-------|-------------|------------|
| **Active** | 1 | New issues found | Active tab |
| **Pending** | 2 | Waiting for response | Active tab |
| **Fixed** | 3 | Issue resolved | Resolved tab |
| **Won't Fix** | 4 | Intentionally not fixing | Resolved tab |
| **Closed** | 5 | Discussion closed | Resolved tab |
| **Unknown** | 0 | Default (avoid) | Unknown tab |

## How It Works Now

### Creating New Comments
```python
# When posting a new issue
thread.status = CommentThreadStatus.ACTIVE

# Result in Azure DevOps:
# - Appears in "Active" tab
# - Shows as requiring attention
# - Developer can respond or mark as resolved
```

### Resolving Issues
```python
# When AI detects issue is fixed
thread.status = CommentThreadStatus.FIXED

# Result in Azure DevOps:
# - Moves to "Resolved" tab
# - Shows green checkmark
# - Adds "✅ Issue Resolved" comment
```

## Testing

### Test New Comments
1. Create PR with issues
2. Wait for review
3. Check Azure DevOps PR
4. Verify comments appear in **Active** tab
5. Check dropdown shows "Active" status

### Test Resolution
1. Fix an issue from previous PR
2. Push update to PR
3. Wait for incremental review
4. Check Azure DevOps PR
5. Verify fixed issue moved to **Resolved** tab
6. Check dropdown shows "Fixed" status
7. Verify "✅ Issue Resolved" comment appears

## Logs to Watch

### New Comment Posted
```
INFO - Posting inline comment on /src/UserController.java:17 (Status: Active)
INFO - Posted comment 1/5
```

### Issue Resolved
```
INFO - Checking previous issues for resolution...
INFO -   ✅ Resolved: UserController.java:17 (Status: Fixed)
INFO - Issue resolution check complete: checked 5, resolved 1, kept 4 open
```

## Benefits

✅ **Clear Status** - Comments explicitly marked as Active
✅ **Proper Organization** - Active vs Resolved tabs work correctly
✅ **Better UX** - Developers see clear status in dropdown
✅ **Audit Trail** - Can track when issues were resolved
✅ **Compliance** - Proper status for quality gates

## Related Files

- `app/real_review.py` - `_post_comment()` method
- `app/real_review.py` - `_check_and_resolve_previous_issues()` method

## Azure DevOps API Reference

```python
from azure.devops.v7_1.git.models import CommentThreadStatus

# Available statuses
CommentThreadStatus.UNKNOWN = 0
CommentThreadStatus.ACTIVE = 1
CommentThreadStatus.PENDING = 2
CommentThreadStatus.FIXED = 3
CommentThreadStatus.WONT_FIX = 4
CommentThreadStatus.CLOSED = 5
```

## Future Enhancements

### Allow Manual Status Changes
- Detect when developer manually changes status
- Respect manual overrides
- Don't auto-resolve if marked "Won't Fix"

### Status-Based Metrics
- Track resolution time per issue
- Calculate fix rate
- Generate quality reports

### Custom Status Workflows
- Allow teams to define custom statuses
- Map to Azure DevOps statuses
- Support different workflows per project
