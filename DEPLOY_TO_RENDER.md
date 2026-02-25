# Deploy to Render - Step by Step

## Step 1: Push Code to GitHub

### 1.1 Initialize Git (if not already done)
```powershell
git init
git add .
git commit -m "Initial commit - Azure DevOps PR Review Agent"
```

### 1.2 Create GitHub Repository
1. Go to https://github.com
2. Click "+" → "New repository"
3. Name: `azure-pr-review-agent`
4. Make it **Private** (contains your API keys)
5. Don't initialize with README (you already have one)
6. Click "Create repository"

### 1.3 Push to GitHub
```powershell
# Replace YOUR_USERNAME with your GitHub username
git remote add origin https://github.com/YOUR_USERNAME/azure-pr-review-agent.git
git branch -M main
git push -u origin main
```

---

## Step 2: Deploy to Render

### 2.1 Sign Up for Render
1. Go to https://render.com
2. Click "Get Started"
3. Sign up with GitHub (easiest)
4. Authorize Render to access your repositories

### 2.2 Create Web Service
1. Click "New +" → "Web Service"
2. Connect your repository:
   - If you see your repo, click "Connect"
   - If not, click "Configure account" and grant access
3. Configure:
   - **Name**: `azure-pr-review` (or any name you want)
   - **Region**: Choose closest to you
   - **Branch**: `main`
   - **Root Directory**: Leave empty
   - **Environment**: `Docker`
   - **Plan**: `Free`

### 2.3 Add Environment Variables
Click "Advanced" → "Add Environment Variable"

Add these (one by one):

```
AZURE_DEVOPS_PAT=your_personal_access_token_here
AZURE_DEVOPS_ORG=visyneri
OPENAI_API_KEY=your_openai_key_here
WEBHOOK_SECRET=any_random_string_here
LOG_LEVEL=INFO
```

**Important**: 
- Get your Azure DevOps PAT from: Azure DevOps → User Settings → Personal Access Tokens
- Get your OpenAI key from: https://platform.openai.com/api-keys
- WEBHOOK_SECRET can be any random string (e.g., `my-secret-key-12345`)

### 2.4 Deploy
1. Click "Create Web Service"
2. Wait 5-10 minutes for build and deployment
3. Watch the logs - you'll see:
   - Building Docker image
   - Installing dependencies
   - Starting application

### 2.5 Get Your URL
Once deployed, you'll see:
```
Your service is live at https://azure-pr-review.onrender.com
```

Copy this URL!

---

## Step 3: Test Your Deployment

### 3.1 Test Health Endpoint
```powershell
curl https://azure-pr-review.onrender.com/health
```

You should see:
```json
{"status":"healthy","version":"0.1.0","mode":"local"}
```

### 3.2 View API Documentation
Open in browser:
```
https://azure-pr-review.onrender.com/docs
```

---

## Step 4: Register Webhook in Azure DevOps

### 4.1 Go to Azure DevOps
1. Open your Azure DevOps project
2. Click "Project Settings" (bottom left)
3. Under "General", click "Service Hooks"

### 4.2 Create Webhook Subscription
1. Click "+ Create subscription"
2. Select "Web Hooks"
3. Click "Next"

### 4.3 Configure Trigger
1. **Trigger on this type of event**: Pull request created
2. **Filters**: Leave default (or customize)
3. Click "Next"

### 4.4 Configure Action
1. **URL**: `https://azure-pr-review.onrender.com/webhooks/azure-devops/pr`
2. **HTTP headers**: Leave empty
3. **Messages to send**: All
4. **Detailed messages to send**: All
5. Click "Test" to verify
6. Click "Finish"

---

## Step 5: Test with a Real PR

### 5.1 Create a Test PR
1. Create a new branch in your Azure DevOps repo
2. Make some code changes
3. Create a Pull Request

### 5.2 Watch the Magic!
1. Go to Render dashboard → Your service → Logs
2. You should see:
   ```
   INFO: Received webhook: git.pullrequest.created
   INFO: Processing PR 123: Your PR Title
   [Agent] Starting analysis...
   ```

3. Check your PR in Azure DevOps - you should see review comments!

---

## Troubleshooting

### Build Failed?
**Check Render logs for errors:**
- Missing dependencies? Check `requirements.txt`
- Docker build failed? Check `Dockerfile`

**Common fixes:**
```powershell
# Make sure all files are committed
git status
git add .
git commit -m "Fix deployment"
git push
```

### App Won't Start?
**Check environment variables:**
1. Go to Render dashboard → Your service → Environment
2. Verify all variables are set correctly
3. Click "Save Changes" to restart

### Webhook Not Received?
**Check Azure DevOps Service Hooks:**
1. Project Settings → Service Hooks
2. Click on your webhook
3. Check "History" tab for delivery attempts
4. Look for errors

**Check Render logs:**
1. Dashboard → Your service → Logs
2. Look for incoming webhook requests

### App Sleeps After 15 Minutes?
**This is normal on free tier:**
- First request after sleep takes ~30 seconds
- Upgrade to paid tier ($7/month) to prevent sleep

---

## Important Notes

### Free Tier Limitations
- ✅ Unlimited webhooks
- ✅ Unlimited PRs
- ⚠️ App sleeps after 15 min inactivity
- ⚠️ 750 hours/month (enough for testing)

### Security
- Your `.env` file is NOT pushed to GitHub (it's in `.gitignore`)
- Environment variables are stored securely in Render
- Keep your repository private

### Costs
- **Render**: Free
- **OpenAI**: ~$0.01-0.05 per PR review
- **Total**: Essentially free for testing

---

## Next Steps

1. ✅ Deploy to Render
2. ✅ Register webhook
3. ✅ Test with a PR
4. 🎯 Customize plugins for your needs
5. 🎯 Add more language support
6. 🎯 Upgrade to paid tier if needed

---

## Quick Commands Reference

```powershell
# Push changes
git add .
git commit -m "Update"
git push

# View Render logs
# Go to: https://dashboard.render.com → Your service → Logs

# Test webhook locally (before deploying)
.\start_local_simple.ps1
.\test_pr_webhook.ps1
```

---

## Support

- **Render Docs**: https://render.com/docs
- **Render Status**: https://status.render.com
- **Your App Logs**: Dashboard → Your service → Logs
- **Your App URL**: Dashboard → Your service → (top of page)

---

Good luck! 🚀
