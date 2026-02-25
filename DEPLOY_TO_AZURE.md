# Deploy to Azure - Step by Step

## Option 1: Azure Web App for Containers (Recommended - Simple)

This deploys just the API without MySQL/Redis. Perfect for testing!

### Prerequisites
- Azure subscription
- Azure CLI installed
- Docker Desktop installed

---

## Step 1: Build and Push Docker Image

### 1.1 Login to Azure
```powershell
az login
```

### 1.2 Create Azure Container Registry (ACR)
```powershell
# Create resource group
az group create --name pr-review-rg --location eastus

# Create container registry (name must be unique)
az acr create --resource-group pr-review-rg --name prreviewacr --sku Basic

# Login to ACR
az acr login --name prreviewacr
```

### 1.3 Build and Push Image
```powershell
# Build image using simple Dockerfile
docker build -f Dockerfile.simple -t prreviewacr.azurecr.io/pr-review-agent:latest .

# Push to ACR
docker push prreviewacr.azurecr.io/pr-review-agent:latest
```

---

## Step 2: Deploy to Azure Web App

### 2.1 Create Web App
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
  --name pr-review-agent `
  --deployment-container-image-name prreviewacr.azurecr.io/pr-review-agent:latest
```

### 2.2 Configure Container Registry Access
```powershell
# Enable admin user on ACR
az acr update --name prreviewacr --admin-enabled true

# Get ACR credentials
az acr credential show --name prreviewacr

# Configure Web App to use ACR
az webapp config container set `
  --name pr-review-agent `
  --resource-group pr-review-rg `
  --docker-custom-image-name prreviewacr.azurecr.io/pr-review-agent:latest `
  --docker-registry-server-url https://prreviewacr.azurecr.io `
  --docker-registry-server-user prreviewacr `
  --docker-registry-server-password <password-from-previous-command>
```

### 2.3 Add Environment Variables
```powershell
az webapp config appsettings set `
  --resource-group pr-review-rg `
  --name pr-review-agent `
  --settings `
    AZURE_DEVOPS_PAT="your_pat" `
    AZURE_DEVOPS_ORG="visyneri" `
    OPENAI_API_KEY="your_key" `
    WEBHOOK_SECRET="your_secret" `
    LOG_LEVEL="INFO"
```

### 2.4 Get Your URL
```powershell
az webapp show --name pr-review-agent --resource-group pr-review-rg --query defaultHostName --output tsv
```

Your app will be at: `https://pr-review-agent.azurewebsites.net`

---

## Step 3: Test Deployment

```powershell
# Test health endpoint
curl https://pr-review-agent.azurewebsites.net/health

# View logs
az webapp log tail --name pr-review-agent --resource-group pr-review-rg
```

---

## Step 4: Register Webhook in Azure DevOps

1. Go to your Azure DevOps project
2. **Project Settings** → **Service Hooks**
3. **+ Create subscription** → **Web Hooks**
4. Configure:
   - Event: Pull request created
   - URL: `https://pr-review-agent.azurewebsites.net/webhooks/azure-devops/pr`
5. Test and Finish

---

## Option 2: Full Deployment with MySQL + Redis (Production)

For production with database, you need separate Azure services:

### 2.1 Create Azure Database for MySQL
```powershell
az mysql flexible-server create `
  --resource-group pr-review-rg `
  --name pr-review-mysql `
  --admin-user adminuser `
  --admin-password "YourPassword123!" `
  --sku-name Standard_B1ms `
  --tier Burstable `
  --storage-size 32
```

### 2.2 Create Azure Cache for Redis
```powershell
az redis create `
  --resource-group pr-review-rg `
  --name pr-review-redis `
  --location eastus `
  --sku Basic `
  --vm-size c0
```

### 2.3 Update Web App Environment Variables
```powershell
# Get MySQL connection string
$mysqlHost = az mysql flexible-server show --resource-group pr-review-rg --name pr-review-mysql --query fullyQualifiedDomainName -o tsv

# Get Redis connection string
$redisKey = az redis list-keys --resource-group pr-review-rg --name pr-review-redis --query primaryKey -o tsv
$redisHost = az redis show --resource-group pr-review-rg --name pr-review-redis --query hostName -o tsv

# Update app settings
az webapp config appsettings set `
  --resource-group pr-review-rg `
  --name pr-review-agent `
  --settings `
    DATABASE_URL="mysql+aiomysql://adminuser:YourPassword123!@${mysqlHost}:3306/pr_review" `
    REDIS_URL="redis://:${redisKey}@${redisHost}:6380/0?ssl=True"
```

### 2.4 Use Full Dockerfile
Build and push using the regular `Dockerfile` instead of `Dockerfile.simple`

---

## Costs

### Option 1 (Simple - No Database)
- **Web App (B1)**: ~$13/month
- **Container Registry**: ~$5/month
- **Total**: ~$18/month

### Option 2 (Full - With Database)
- **Web App (B1)**: ~$13/month
- **MySQL (Burstable)**: ~$15/month
- **Redis (Basic C0)**: ~$17/month
- **Container Registry**: ~$5/month
- **Total**: ~$50/month

### Free Tier Alternative
Use **Azure Container Instances** (pay per second):
```powershell
az container create `
  --resource-group pr-review-rg `
  --name pr-review-agent `
  --image prreviewacr.azurecr.io/pr-review-agent:latest `
  --dns-name-label pr-review-agent `
  --ports 8000 `
  --environment-variables `
    AZURE_DEVOPS_PAT="your_pat" `
    AZURE_DEVOPS_ORG="visyneri" `
    OPENAI_API_KEY="your_key"
```

Cost: ~$1-2/month (pay per second)

---

## Troubleshooting

### Container won't start?
```powershell
# View logs
az webapp log tail --name pr-review-agent --resource-group pr-review-rg

# Check container logs
az webapp log download --name pr-review-agent --resource-group pr-review-rg
```

### Can't push to ACR?
```powershell
# Login again
az acr login --name prreviewacr

# Check if image exists locally
docker images
```

### Webhook not working?
- Check Web App logs
- Verify webhook URL in Azure DevOps
- Check firewall rules

---

## Update Deployment

When you make changes:

```powershell
# Rebuild and push
docker build -f Dockerfile.simple -t prreviewacr.azurecr.io/pr-review-agent:latest .
docker push prreviewacr.azurecr.io/pr-review-agent:latest

# Restart Web App
az webapp restart --name pr-review-agent --resource-group pr-review-rg
```

---

## Clean Up (Delete Everything)

```powershell
az group delete --name pr-review-rg --yes
```

---

## Recommendation

**For testing**: Use Option 1 (Simple) with Azure Container Instances (~$1-2/month)

**For production**: Use Option 2 (Full) with Web App + MySQL + Redis (~$50/month)

**Cheapest option**: Use Render.com (free tier) - see DEPLOY_TO_RENDER.md
