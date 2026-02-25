# Azure DevOps PR Review Agent

AI-powered code review agent for Azure DevOps pull requests.

---

## Quick Deploy (5 Minutes)

### Your Situation
- ✅ Agent is ready
- ❌ Corporate firewall blocks tunnels
- ✅ Need public URL for Azure DevOps webhooks

### Solution: Deploy to Render.com (Free)

1. **Push to GitHub**
   ```bash
   git add .
   git commit -m "Ready to deploy"
   git push origin main
   ```

2. **Deploy**
   - Go to https://render.com
   - Sign up (free, use GitHub)
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Settings:
     - **Environment**: Docker
     - **Plan**: Free

3. **Add Environment Variables**
   ```
   AZURE_DEVOPS_PAT=your_personal_access_token
   AZURE_DEVOPS_ORG=your_organization_name
   OPENAI_API_KEY=your_openai_api_key
   WEBHOOK_SECRET=any_random_string
   ```

4. **Deploy** - Wait 5 minutes, you'll get:
   ```
   https://your-app-name.onrender.com
   ```

5. **Register Webhook in Azure DevOps**
   - Go to your Azure DevOps project
   - **Project Settings** → **Service Hooks**
   - Click "+ Create subscription"
   - Select "Web Hooks"
   - Configure:
     - **Event**: Pull request created
     - **URL**: `https://your-app-name.onrender.com/webhooks/azure-devops/pr`
   - Click "Test" then "Finish"

6. **Test**
   - Create a PR in Azure DevOps
   - Watch the agent analyze and comment!

---

## Alternative Platforms

| Platform | Free Tier | Setup Time | Best For |
|----------|-----------|------------|----------|
| **Render** | ✅ Yes | 5 min | Easiest |
| **Railway** | $5 credit/mo | 5 min | Best value |
| **Fly.io** | ✅ Yes | 10 min | Best performance |

### Railway.app
```bash
# Same as Render, but go to railway.app
# Includes database + Redis in free tier
```

### Fly.io
```bash
# Install CLI
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"

# Deploy
fly launch --name azure-pr-review
fly secrets set AZURE_DEVOPS_PAT=your_pat
fly secrets set AZURE_DEVOPS_ORG=your_org
fly secrets set OPENAI_API_KEY=your_key
fly deploy
```

---

## Local Testing (Optional)

### Test Without Azure DevOps
```powershell
# Start simplified API (no database needed)
.\start_local_simple.ps1

# Test webhook simulation
.\test_pr_webhook.ps1
```

### Full Docker Stack
```bash
# Requires Docker Desktop
docker compose up -d

# Access at http://localhost:8000
```

---

## Configuration

Edit `.env` file:

```env
# Required
AZURE_DEVOPS_PAT=your_personal_access_token
AZURE_DEVOPS_ORG=your_organization
OPENAI_API_KEY=your_openai_key

# Optional (for local Docker deployment)
DATABASE_URL=mysql+aiomysql://user:pass@mysql:3306/pr_review
REDIS_URL=redis://redis:6379/0
WEBHOOK_SECRET=your_secret
```

### Get Azure DevOps PAT
1. Go to Azure DevOps
2. User Settings → Personal Access Tokens
3. New Token
4. Scopes: Code (Read & Write), Pull Request Threads (Read & Write)
5. Copy the token

### Get OpenAI API Key
1. Go to https://platform.openai.com
2. API Keys → Create new secret key
3. Copy the key

---

## Features

- ✅ Receives Azure DevOps PR webhooks
- ✅ Analyzes code changes with AI
- ✅ Detects bugs, security issues, code smells
- ✅ Posts review comments on PRs
- ✅ Supports Java and Angular (extensible)
- ✅ Plugin system for custom rules

---

## Architecture

```
Azure DevOps PR → Webhook → Your App → OpenAI → Review Comments
```

**Tech Stack:**
- FastAPI (web framework)
- LangChain/LangGraph (agent orchestration)
- OpenAI (code analysis)
- Azure DevOps SDK (PR integration)
- tree-sitter (code parsing)
- MySQL + Redis (optional, for production)

---

## Project Structure

```
app/
  ├── api/              # Webhook endpoints
  ├── agents/           # Review agent logic
  ├── analyzers/        # Code analyzers
  ├── services/         # Azure DevOps integration
  └── models/           # Data models

plugins/
  ├── java/             # Java-specific rules
  └── angular/          # Angular-specific rules

tests/                  # Unit tests
```

---

## Troubleshooting

### Firewall blocks tunnels?
→ Deploy to cloud (Render, Railway, Fly.io)

### Webhook not received?
→ Check Azure DevOps Service Hooks history
→ Verify webhook URL is correct
→ Check app logs on platform dashboard

### App not starting?
→ Check environment variables are set
→ View logs on platform dashboard

### Database connection failed?
→ Use simplified mode: `app/simple_main.py` (no database)

---

## Development

### Run Tests
```bash
pytest
```

### Add Custom Plugin
1. Create folder: `plugins/your-language/`
2. Add `plugin.py` and `config.yaml`
3. See `plugins/java/` for example

### Customize Review Rules
Edit plugin config files:
- `plugins/java/config.yaml`
- `plugins/angular/config.yaml`

---

## Cost

**Free Tier (Render/Fly.io):**
- ✅ Unlimited webhooks
- ✅ Unlimited PRs
- ⚠️ App sleeps after 15 min inactivity
- ⚠️ First request takes ~30s to wake

**Paid Tier ($7-20/month):**
- ✅ No sleep
- ✅ Faster performance
- ✅ More resources

**OpenAI Costs:**
- ~$0.01-0.05 per PR review
- Depends on code size

---

## Next Steps

1. **Deploy to Render** (5 minutes)
2. **Register webhook** in Azure DevOps
3. **Create a test PR** and watch it work
4. **Customize plugins** for your needs
5. **Upgrade to paid tier** if needed

---

## Support

- Check app logs on platform dashboard
- Test webhook: `curl https://your-app.com/health`
- View API docs: `https://your-app.com/docs`

---

## License

MIT
