# Deploy Docker Image - Simple Guide

## Prerequisites

- Docker Desktop installed
- Azure CLI installed (for Azure)
- Docker Hub account (free) OR Azure Container Registry

---

# Option 1: Deploy to Render.com with Docker

## Step 1: Push Code to GitHub

```powershell
# Initialize Git
git init
git add .
git commit -m "Initial commit"

# Create repo on GitHub: https://github.com/new
# Name: azure-pr-review-agent
# Private: Yes

# Push (replace YOUR_USERNAME)
git remote add origin https://github.com/YOUR_USERNAME/azure-pr-review-agent.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy to Render

1. Go to https://render.com
2. Sign up with GitHub
3. Click "New +" → "Web Service"
4. Connect your GitHub repository
5. Configure:
   - **Name**: `azure-pr-review`
   - **Environment**: `Docker`
   - **Dockerfile Path**: `Dockerfile.simple`
   - **Plan**: `Free`

6. Add Environment Variables:
   ```
   AZURE_DEVOPS_PAT=your_pat_here
   AZURE_DEVOPS_ORG=visyneri
   OPENAI_API_KEY=your_openai_key
   WEBHOOK_SECRET=random_string_123
   LOG_LEVEL=INFO
   ```

7. Click "Create Web Service"

8. Wait 5-10 minutes - Render will:
   - Clone your repo
   - Build Docker image using `Dockerfile.simple`
   - Deploy it
   - Give you a URL: `https://azure-pr-review.onrender.com`

## Step 3: Test

```powershell
curl https://azure-pr-review.onrender.com/health
```

**Done!** Your webhook URL: `https://azure-pr-review.onrender.com/webhooks/azure-devops/pr`

---

# Option 2: Deploy to Azure with Docker

## Step 1: Build and Push Docker Image to Docker Hub

### 1.1 Login to Docker Hub
```powershell
docker login
# Enter your Docker Hub username and password
```

### 1.2 Build Image
```powershell
# Build using simple Dockerfile (no database)
docker build -f Dockerfile.simple -t YOUR_DOCKERHUB_USERNAME/pr-review-agent:latest .

# Example:
# docker build -f Dockerfile.simple -t johndoe/pr-review-agent:latest .
```

### 1.3 Push to Docker Hub
```powershell
docker push YOUR_DOCKERHUB_USERNAME/pr-review-agent:latest
```

## Step 2: Deploy to Azure Container Instances

### 2.1 Login to Azure
```powershell
az login
```

### 2.2 Create Resource Group
```powershell
az group create --name pr-review-rg --location eastus
```

### 2.3 Deploy Container
```powershell
az container create `
  --resource-group pr-review-rg `
  --name pr-review-agent `
  --image YOUR_DOCKERHUB_USERNAME/pr-review-agent:latest `
  --dns-name-label pr-review-agent-unique123 `
  --ports 8000 `
  --environment-variables `
    AZURE_DEVOPS_PAT="your_pat" `
    AZURE_DEVOPS_ORG="visyneri" `
    OPENAI_API_KEY="your_key" `
    WEBHOOK_SECRET="random_string" `
    LOG_LEVEL="INFO"
```

**Note**: `dns-name-label` must be globally unique. Add random numbers if needed.

### 2.4 Get Your URL
```powershell
az container show `
  --resource-group pr-review-rg `
  --name pr-review-agent `
  --query ipAddress.fqdn `
  --output tsv
```

Your URL will be: `http://pr-review-agent-unique123.eastus.azurecontainer.io:8000`

### 2.5 Test
```powershell
curl http://pr-review-agent-unique123.eastus.azurecontainer.io:8000/health
```

**Done!** Your webhook URL: `http://pr-review-agent-unique123.eastus.azurecontainer.io:8000/webhooks/azure-devops/pr`

---

# Alternative: Azure Web App for Containers

If you want HTTPS and better performance:

## Step 1: Same as above (build and push to Docker Hub)

## Step 2: Deploy to Azure Web App

```powershell
# Create App Service Plan
az appservice plan create `
  --name pr-review-plan `
  --resource-group pr-review-rg `
  --is-linux `
  --sku B1

# Create Web App
az webapp create `
  --resource-group pr-review-rg `
  --plan pr-review-plan `
  --name pr-review-agent-unique123 `
  --deployment-container-image-name YOUR_DOCKERHUB_USERNAME/pr-review-agent:latest

# Add environment variables
az webapp config appsettings set `
  --resource-group pr-review-rg `
  --name pr-review-agent-unique123 `
  --settings `
    AZURE_DEVOPS_PAT="your_pat" `
    AZURE_DEVOPS_ORG="visyneri" `
    OPENAI_API_KEY="your_key" `
    WEBHOOK_SECRET="random_string" `
    LOG_LEVEL="INFO"

# Get URL
az webapp show `
  --name pr-review-agent-unique123 `
  --resource-group pr-review-rg `
  --query defaultHostName `
  --output tsv
```

Your URL: `https://pr-review-agent-unique123.azurewebsites.net`

---

# Register Webhook in Azure DevOps

After deployment (Render or Azure):

1. Go to Azure DevOps → Your Project
2. **Project Settings** → **Service Hooks**
3. **+ Create subscription** → **Web Hooks**
4. Configure:
   - **Event**: Pull request created
   - **URL**: Your webhook URL from above
5. Click **Test** → Should return 200 OK
6. Click **Finish**

---

# Comparison

| Method | Cost | Setup Time | HTTPS | Best For |
|--------|------|------------|-------|----------|
| **Render** | Free | 5 min | ✅ Yes | Testing |
| **Azure Container Instances** | $1-2/mo | 10 min | ❌ No | Testing |
| **Azure Web App** | $18/mo | 15 min | ✅ Yes | Production |

---

# Troubleshooting

## Docker build fails?
```powershell
# Test build locally first
docker build -f Dockerfile.simple -t test-image .
docker run -p 8000:8000 test-image
# Visit http://localhost:8000/health
```

## Can't push to Docker Hub?
```powershell
# Login again
docker login

# Check image exists
docker images
```

## Azure container won't start?
```powershell
# View logs
az container logs --resource-group pr-review-rg --name pr-review-agent

# Check status
az container show --resource-group pr-review-rg --name pr-review-agent
```

## Render build fails?
- Check Render logs in dashboard
- Verify `Dockerfile.simple` exists
- Check environment variables are set

---

# Update Deployment

## Render (Auto-deploys)
```powershell
git add .
git commit -m "Update"
git push
# Render auto-deploys!
```

## Azure Container Instances
```powershell
# Rebuild and push
docker build -f Dockerfile.simple -t YOUR_USERNAME/pr-review-agent:latest .
docker push YOUR_USERNAME/pr-review-agent:latest

# Delete and recreate container
az container delete --resource-group pr-review-rg --name pr-review-agent --yes
az container create ... # (same command as before)
```

## Azure Web App
```powershell
# Rebuild and push
docker build -f Dockerfile.simple -t YOUR_USERNAME/pr-review-agent:latest .
docker push YOUR_USERNAME/pr-review-agent:latest

# Restart web app
az webapp restart --name pr-review-agent-unique123 --resource-group pr-review-rg
```

---

# Clean Up

## Render
- Dashboard → Your service → Settings → Delete Service

## Azure
```powershell
# Delete everything
az group delete --name pr-review-rg --yes
```

---

# My Recommendation

**For testing**: Use **Render** (free, easiest, auto-deploys)

**For production**: Use **Azure Web App** (HTTPS, better performance)

**Cheapest Azure option**: Use **Azure Container Instances** ($1-2/month)

---

# Quick Start Commands

## Render (Easiest)
```powershell
git init
git add .
git commit -m "Initial commit"
# Push to GitHub
# Deploy on Render.com (5 clicks)
```

## Azure Container Instances (Cheapest)
```powershell
docker login
docker build -f Dockerfile.simple -t YOUR_USERNAME/pr-review-agent:latest .
docker push YOUR_USERNAME/pr-review-agent:latest
az login
az group create --name pr-review-rg --location eastus
az container create --resource-group pr-review-rg --name pr-review-agent --image YOUR_USERNAME/pr-review-agent:latest --dns-name-label pr-review-unique123 --ports 8000 --environment-variables AZURE_DEVOPS_PAT="your_pat" AZURE_DEVOPS_ORG="visyneri" OPENAI_API_KEY="your_key"
```

---

**Choose your option and follow the steps above!**
