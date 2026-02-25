# Deploy to Render - Simple Steps

## ✅ Your code is already on GitHub!
https://github.com/gopinath-vaddepally/pr-review-agent

---

## Step 1: Go to Render

1. Open https://render.com
2. Click "Get Started" or "Sign Up"
3. Choose "Sign up with GitHub"
4. Authorize Render to access your GitHub

---

## Step 2: Create Web Service

1. Click "New +" (top right)
2. Select "Web Service"
3. You'll see your repositories
4. Find and click "Connect" next to `pr-review-agent`

---

## Step 3: Configure Service

Fill in these settings:

### Basic Settings
- **Name**: `pr-review-agent` (or any name you want)
- **Region**: Choose closest to you (e.g., Oregon, Frankfurt)
- **Branch**: `main`
- **Root Directory**: Leave empty

### Build Settings
- **Environment**: `Docker`
- **Dockerfile Path**: `Dockerfile.simple` ← **IMPORTANT!**

### Instance Type
- **Plan**: `Free`

---

## Step 4: Add Environment Variables

Click "Advanced" → Scroll to "Environment Variables"

Add these one by one (click "Add Environment Variable" for each):

```
AZURE_DEVOPS_PAT=<your_personal_access_token>
AZURE_DEVOPS_ORG=visyneri
OPENAI_API_KEY=<your_openai_api_key>
LOG_LEVEL=INFO
```

**Notes:**
- Get Azure DevOps PAT: Azure DevOps → User Settings → Personal Access Tokens
- Get OpenAI Key: https://platform.openai.com/api-keys
- **NO WEBHOOK_SECRET needed** - verification is disabled in simple mode!

---

## Step 5: Deploy!

1. Click "Create Web Service" (bottom)
2. Wait 5-10 minutes
3. Watch the logs - you'll see:
   ```
   Building Docker image...
   Installing dependencies...
   Starting application...
   Your service is live at https://pr-review-agent.onrender.com
   ```

---

## Step 6: Test Your Deployment

### 6.1 Test Health Endpoint

```powershell
curl https://pr-review-agent.onrender.com/health
```

Expected response:
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "mode": "local",
  "database": "in-memory",
  "redis": "disabled"
}
```

### 6.2 View API Docs

Open in browser:
```
https://pr-review-agent.onrender.com/docs
```

---

## Step 7: Register Webhook in Azure DevOps

1. Go to your Azure DevOps project
2. Click "Project Settings" (bottom left)
3. Under "General", click "Service Hooks"
4. Click "+ Create subscription"
5. Select "Web Hooks"
6. Click "Next"

### Configure Trigger
- **Trigger on this type of event**: Pull request created
- **Filters**: Leave default
- Click "Next"

### Configure Action
- **URL**: `https://pr-review-agent.onrender.com/webhooks/azure-devops/pr`
- **HTTP headers**: Leave empty
- **Messages to send**: All
- **Detailed messages to send**: All
- Click "Test"
- Should see: ✅ "Test notification sent successfully"
- Click "Finish"

---

## Step 8: Test with a Real PR!

1. Create a new branch in your Azure DevOps repo
2. Make some code changes
3. Create a Pull Request
4. Go to Render → Your service → Logs
5. You should see:
   ```
   INFO: Received webhook: git.pullrequest.created
   INFO: Processing PR 123: Your PR Title
   [Agent] Starting analysis for PR 123
   [Agent] PR 123 - Phase: initialize
   [Agent] PR 123 - Phase: retrieve_code
   ...
   [Agent] PR 123 - Analysis complete
   ```

---

## Important Notes

### About Webhook Security
- ✅ **Disabled in simple mode** - no signature verification
- ✅ Perfect for testing
- ⚠️ For production, use full mode with signature verification

### About Free Tier
- ✅ Completely free
- ✅ Unlimited webhooks
- ⚠️ App sleeps after 15 min of inactivity
- ⚠️ First request after sleep takes ~30 seconds to wake up

### About Database
- ✅ No database needed in simple mode
- ✅ Comments are logged, not stored
- ✅ Perfect for testing the workflow
- ⚠️ For production with history, use full mode

---

## Troubleshooting

### Build Failed?
- Check Render logs for errors
- Verify `Dockerfile.simple` path is correct
- Make sure all files are in GitHub

### Webhook Not Received?
1. Check Azure DevOps Service Hooks history
2. Check Render logs
3. Verify webhook URL is correct
4. Test health endpoint first

### App Won't Start?
- Check environment variables are set
- View logs in Render dashboard
- Verify AZURE_DEVOPS_PAT and OPENAI_API_KEY are correct

---

## Update Your App

When you make changes:

```powershell
git add .
git commit -m "Update"
git push
```

Render will automatically rebuild and redeploy! 🎉

---

## View Logs

1. Go to Render dashboard
2. Click on your service
3. Click "Logs" tab
4. See real-time logs

---

## Your URLs

- **App**: https://pr-review-agent.onrender.com
- **Health**: https://pr-review-agent.onrender.com/health
- **API Docs**: https://pr-review-agent.onrender.com/docs
- **Webhook**: https://pr-review-agent.onrender.com/webhooks/azure-devops/pr

---

## Summary

1. ✅ Code on GitHub
2. ✅ Render account created
3. ✅ Web service configured with `Dockerfile.simple`
4. ✅ Environment variables added (no WEBHOOK_SECRET needed!)
5. ✅ Deployed and tested
6. ✅ Webhook registered in Azure DevOps
7. ✅ Ready to review PRs!

**Total time: ~15 minutes**

---

Good luck! 🚀
