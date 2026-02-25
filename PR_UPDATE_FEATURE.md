# PR Update Review Feature

## Overview

Enhanced the Azure DevOps PR Review Agent to intelligently handle PR updates with incremental reviews and issue tracking.

## What's New

### 1. Incremental Review on PR Updates

**Event Detection:**
- Now handles both `git.pullrequest.created` and `git.pullrequest.updated` webhook events
- Automatically detects when a PR is updated with new commits

**Smart Change Detection:**
- Tracks PR iterations using Azure DevOps API
- Compares current iteration with last reviewed iteration
- Reviews ONLY the newly added/changed files
- Avoids re-reviewing unchanged code

### 2. Issue Resolution Tracking

**Automatic Issue Verification:**
When a PR is updated, the system:
1. **Retrieves all previous comments** from the PR
2. **Checks each issue** against the new code using AI
3. **Marks issues as resolved** if the code was fixed
4. **Keeps unresolved issues visible** if they still exist

**AI-Powered Resolution Check:**
- Uses Groq/Anthropic AI to verify if issues were addressed
- Compares original issue description with current code
- Adds "✅ Issue Resolved" comment when fixed
- Marks thread status as FIXED in Azure DevOps

### 3. Comment Deduplication

**Prevents Duplicate Feedback:**
- Checks existing comment locations (file + line number)
- Skips posting comments that already exist
- Logs skipped duplicates for observability

### 4. State Persistence

**Tracks Review History:**
- Saves last reviewed iteration to local file storage
- Format: `.pr_state_{repository_id}_{pr_id}.json`
- Enables incremental reviews across system restarts

## How It Works

### Full Review (New PR)
```
Developer creates PR
    ↓
Webhook: git.pullrequest.created
    ↓
System reviews ALL changed files
    ↓
Posts inline comments on issues
    ↓
Saves iteration 1 as "last reviewed"
```

### Incremental Review (PR Update)
```
Developer pushes new commits
    ↓
Webhook: git.pullrequest.updated
    ↓
System loads last reviewed iteration
    ↓
Compares iteration N-1 vs iteration N
    ↓
Gets ONLY newly changed files
    ↓
Checks if previous issues were fixed
    ├─ Fixed → Mark as resolved ✅
    └─ Not fixed → Keep visible ⚠️
    ↓
Reviews new changes with AI
    ↓
Filters duplicate comments
    ↓
Posts only new issues
    ↓
Saves iteration N as "last reviewed"
```

## Example Workflow

### Scenario: Developer Fixes Security Issue

**Initial PR (Iteration 1):**
```java
// ProductController.java - Line 45
String query = "SELECT * FROM products WHERE id = " + productId;
```

**AI Comment:**
> ⚠️ **Security Issue:** SQL injection vulnerability
> **Suggested Fix:** Use parameterized queries

---

**Developer Updates PR (Iteration 2):**
```java
// ProductController.java - Line 45
String query = "SELECT * FROM products WHERE id = ?";
PreparedStatement stmt = connection.prepareStatement(query);
stmt.setString(1, productId);
```

**System Actions:**
1. ✅ Detects PR update event
2. 🔍 Compares iteration 1 vs 2
3. 📝 Finds ProductController.java was changed
4. 🤖 AI checks if SQL injection was fixed → YES
5. ✅ Marks original thread as RESOLVED
6. 💬 Adds comment: "✅ Issue Resolved - This issue has been fixed in the latest update"
7. 🔍 Reviews any other new changes
8. 📤 Posts comments only on new issues

## Configuration

### Environment Variables
```bash
# Required
AZURE_DEVOPS_PAT=your_pat_token
AZURE_DEVOPS_ORG=your_org_name

# AI Provider (at least one required)
GROQ_API_KEY=your_groq_key          # Primary (free, fast)
ANTHROPIC_API_KEY=your_claude_key   # Fallback
```

### Webhook Setup
Register webhook in Azure DevOps for BOTH events:
- `git.pullrequest.created`
- `git.pullrequest.updated`

URL: `https://your-domain.com/webhooks/azure-devops/pr`

## Files Modified

### `app/simple_main.py`
- Added `is_update` parameter to webhook handler
- Detects event type (`created` vs `updated`)
- Passes review type to background task

### `app/real_review.py`
- Added `is_update` parameter to `review_pr()` method
- Implemented iteration tracking and comparison
- Added `_get_last_reviewed_iteration()` - Load saved state
- Added `_save_last_reviewed_iteration()` - Persist state
- Added `_get_iteration_changes()` - Compare iterations
- Added `_get_all_pr_changes()` - Full review helper
- Added `_check_and_resolve_previous_issues()` - Issue verification
- Added `_check_if_issue_fixed()` - AI-powered fix detection
- Enhanced `_filter_duplicate_comments()` - Prevent duplicates

## Benefits

### For Developers
- ✅ No duplicate comments on unchanged code
- ✅ Clear visibility when issues are resolved
- ✅ Faster reviews (only new changes analyzed)
- ✅ Encourages iterative improvement

### For Teams
- ✅ Reduced noise in PR comments
- ✅ Better tracking of issue resolution
- ✅ More efficient code review process
- ✅ Automated quality gates

### For System
- ✅ Lower AI API costs (fewer tokens)
- ✅ Faster processing (fewer files)
- ✅ Better resource utilization
- ✅ Scalable to large PRs

## Deployment

### Local Testing
```bash
# Start the service
python app/simple_main.py

# Trigger test PR update
curl -X POST "http://localhost:8000/webhooks/azure-devops/pr" \
  -H "Content-Type: application/json" \
  -d '{"eventType": "git.pullrequest.updated", ...}'
```

### Production (Render.com)
1. Push code to GitHub
2. Render auto-deploys from main branch
3. Webhook already configured in Azure DevOps
4. No additional setup needed

## Monitoring

### Logs to Watch
```
📥 Received webhook: git.pullrequest.updated
Review type: incremental (PR update)
Current iteration: 3
Last reviewed iteration: 2
Will review changes from iteration 2 to 3
Found 2 files changed since iteration 2
Checking previous issues for resolution...
  ✅ Resolved: ProductController.java:45
  ⚠️  Still unresolved: UserService.java:89
Issue resolution check complete: 1 resolved, 1 still open
  - Analyzing ProductController.java...
    Found 0 new issues (previous issue fixed!)
Filtered out 0 duplicate comments
Total comments to post: 0
✅ Review complete for PR 123!
```

## Future Enhancements

- [ ] Redis/MySQL for distributed state storage
- [ ] Webhook for issue resolution notifications
- [ ] Analytics dashboard for resolution rates
- [ ] Custom resolution criteria per project
- [ ] Integration with work item tracking

## Testing

### Test Scenario 1: New PR
1. Create PR with security issue
2. Verify comment posted
3. Check iteration 1 saved

### Test Scenario 2: Fix Issue
1. Update PR with fix
2. Verify issue marked as resolved
3. Verify no duplicate comments
4. Check iteration 2 saved

### Test Scenario 3: Add New Code
1. Update PR with new file
2. Verify new file reviewed
3. Verify old issues still tracked
4. Check iteration 3 saved

## Support

For issues or questions:
- Check logs in Render.com dashboard
- Review `.pr_state_*.json` files for state
- Verify webhook delivery in Azure DevOps
- Check AI API keys are valid
