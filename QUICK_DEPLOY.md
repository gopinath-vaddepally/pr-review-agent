# Quick Deploy Guide

Choose your platform and follow the steps:

---

## 🚀 Render.com (Recommended - Free & Easy)

### Steps:
1. **Push to GitHub**
   ```powershell
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/YOUR_USERNAME/azure-pr-review-agent.git
   git push -u origin main
   ```

2. **Deploy on Render**
   - Go to https://render.com
   - Sign up with GitHub
   - New + → Web Service
   - Connect your repo
   - Environment: Docker
   - Dockerfile Path: `Dockerfile.simple`
   - Add environment variables:
     ```
     AZURE_DEVOPS_PAT=your_pat
     AZURE_DEVOPS_ORG=visyneri
     OPENAI_API_KEY=your_key
     WEBHOOK_SECRET=random123
     ```
   - Deploy!

3. **Get URL**: `https://your-app.onrender.com`

**Time**: 10 minutes | **Cost**: Free

---

## ☁️ Azure Container Instances (Cheap)

### Steps:
1. **Build & Push Docker Image**
   ```powershell
   docker login
   docker build -f Dockerfile.simple -t YOUR_USERNAME/pr-review-agent:latest .
   docker push YOUR_USERNAME/pr-review-agent:latest
   ```

2. **Deploy to Azure**
   ```powershell
   az login
   az group create --name pr-review-rg --location eastus
   
   az container create `
     --resource-group pr-review-rg `
     --name pr-review-agent `
     --image YOUR_USERNAME/pr-review-agent:latest `
     --dns-name-label pr-review-unique123 `
     --ports 8000 `
     --environment-variables `
       AZURE_DEVOPS_PAT="your_pat" `
       AZURE_DEVOPS_ORG="visyneri" `
       OPENAI_API_KEY="your_key"
   ```

3. **Get URL**
   ```powershell
   az container show --resource-group pr-review-rg --name pr-review-agent --query ipAddress.fqdn -o tsv
   ```

**Time**: 15 minutes | **Cost**: $1-2/month

---

## 🌐 Azure Web App (Production)

### Steps:
1. **Build & Push** (same as above)

2. **Deploy to Web App**
   ```powershell
   az appservice plan create --name pr-review-plan --resource-group pr-review-rg --is-linux --sku B1
   
   az webapp create `
     --resource-group pr-review-rg `
     --plan pr-review-plan `
     --name pr-review-unique123 `
     --deployment-container-image-name YOUR_USERNAME/pr-review-agent:latest
   
   az webapp config appsettings set `
     --resource-group pr-review-rg `
     --name pr-review-unique123 `
     --settings `
       AZURE_DEVOPS_PAT="your_pat" `
       AZURE_DEVOPS_ORG="visyneri" `
       OPENAI_API_KEY="your_key"
   ```

3. **Get URL**: `https://pr-review-unique123.azurewebsites.net`

**Time**: 20 minutes | **Cost**: $18/month

---

## 📝 Register Webhook (All Platforms)

After deployment:

1. Azure DevOps → Project Settings → Service Hooks
2. + Create subscription → Web Hooks
3. Event: Pull request created
4. URL: `https://your-app-url/webhooks/azure-devops/pr`
5. Test → Finish

---

## 🧪 Test

```powershell
curl https://your-app-url/health
```

Should return:
```json
{"status":"healthy","version":"0.1.0","mode":"local"}
```

---

## 📊 Comparison

| Platform | Cost | Time | HTTPS | Auto-Deploy |
|----------|------|------|-------|-------------|
| Render | Free | 10 min | ✅ | ✅ |
| Azure CI | $1-2/mo | 15 min | ❌ | ❌ |
| Azure Web App | $18/mo | 20 min | ✅ | ❌ |

---

## 💡 My Recommendation

**Start with Render** (free, easiest)

**Move to Azure** if you need:
- Better performance
- No sleep
- Azure integration

---

## 📚 Detailed Guides

- **DEPLOY_DOCKER_IMAGE.md** - Complete Docker deployment guide
- **DEPLOY_TO_RENDER.md** - Render.com details
- **DEPLOY_TO_AZURE.md** - Azure details
- **DEPLOYMENT_OPTIONS.md** - Full comparison

---

**Pick one and deploy now!** 🚀
