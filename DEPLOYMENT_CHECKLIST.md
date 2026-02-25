# Deployment Checklist

## Before You Start

- [ ] You have a GitHub account
- [ ] You have Azure DevOps PAT (Personal Access Token)
- [ ] You have OpenAI API key

---

## Step 1: Push to GitHub (5 minutes)

```powershell
# Initialize Git
git init
git add .
git commit -m "Initial commit"

# Create repo on GitHub (https://github.com/new)
# Name: azure-pr-review-agent
# Private: Yes

# Push (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/azure-pr-review-agent.git
git branch -M main
git push -u origin main
```

- [ ] Git initialized
- [ ] GitHub repo created
- [ ] Code pushed

---

## Step 2: Deploy to Render (5 minutes)

1. Go to https://render.com
2. Sign up with GitHub
3. New + → Web Service
4. Connect your repository
5. Configure:
   - Environment: Docker
   - Plan: Free
6. Add environment variables:
   ```
   AZURE_DEVOPS_PAT=your_pat
   AZURE_DEVOPS_ORG=visyneri
   OPENAI_API_KEY=your_key
   WEBHOOK_SECRET=random_string
   ```
7. Click "Create Web Service"
8. Wait 5-10 minutes

- [ ] Render account created
- [ ] Web service created
- [ ] Environment variables added
- [ ] Deployment successful
- [ ] Got your URL: `https://______.onrender.com`

---

## Step 3: Test Deployment (2 minutes)

```powershell
# Test health endpoint (replace with your URL)
curl https://your-app.onrender.com/health
```

Expected response:
```json
{"status":"healthy","version":"0.1.0","mode":"local"}
```

- [ ] Health endpoint works
- [ ] API docs accessible: `https://your-app.onrender.com/docs`

---

## Step 4: Register Webhook (3 minutes)

1. Azure DevOps → Your Project
2. Project Settings → Service Hooks
3. + Create subscription → Web Hooks
4. Event: Pull request created
5. URL: `https://your-app.onrender.com/webhooks/azure-devops/pr`
6. Test → Finish

- [ ] Webhook created
- [ ] Test successful

---

## Step 5: Test with Real PR (5 minutes)

1. Create a branch in Azure DevOps
2. Make some changes
3. Create a Pull Request
4. Check Render logs
5. Check PR for review comments

- [ ] PR created
- [ ] Webhook received (check Render logs)
- [ ] Review comments posted

---

## Done! 🎉

Your PR Review Agent is live!

**Your webhook URL**: `https://your-app.onrender.com/webhooks/azure-devops/pr`

**View logs**: https://dashboard.render.com → Your service → Logs

**Next steps**:
- Customize plugins
- Add more languages
- Upgrade to paid tier (optional)

---

## Troubleshooting

### Build failed?
- Check Render logs
- Verify Dockerfile exists
- Check requirements.txt

### Webhook not working?
- Check Azure DevOps Service Hooks history
- Check Render logs for incoming requests
- Verify webhook URL is correct

### App sleeping?
- Normal on free tier
- First request takes ~30s to wake
- Upgrade to paid tier to prevent sleep

---

## Quick Reference

**Render Dashboard**: https://dashboard.render.com
**Your App Logs**: Dashboard → Your service → Logs
**Azure DevOps Service Hooks**: Project Settings → Service Hooks
**OpenAI Usage**: https://platform.openai.com/usage

---

Total time: ~20 minutes
