# Render Deployment Guide

This guide will help you deploy the LlegarCasa Scraper application to Render using Docker.

## Prerequisites

1. A [Render account](https://render.com)
2. Your code pushed to a Git repository (GitHub, GitLab, or Bitbucket)
3. Docker installed locally for testing (optional)

## Deployment Steps

### 1. Test Locally (Optional but Recommended)

First, test the Docker container locally:

```bash
# Build the Docker image
docker build -t llegar-casa-scraper .

# Run the container
docker run -p 8000:8000 -e PORT=8000 llegar-casa-scraper

# Test the application
curl http://localhost:8000/health
```

### 2. Deploy to Render

#### Option A: Using the Render Dashboard

1. **Create a New Web Service**:
   - Go to [Render Dashboard](https://dashboard.render.com)
   - Click "New +" and select "Web Service"
   - Connect your Git repository

2. **Configure the Service**:
   - **Name**: `llegar-casa-scraper`
   - **Runtime**: Docker
   - **Build Command**: Leave empty (Docker will handle this)
   - **Start Command**: Leave empty (Docker CMD will be used)

3. **Environment Variables**:
   Add these environment variables in the Render dashboard:
   ```
   ENVIRONMENT=production
   DEBUG=false
   SCRAPER_HEADLESS_MODE=true
   SCRAPER_SAVE_SCREENSHOTS=false
   SCRAPER_DEBUG_MODE=false
   CORS_ORIGINS=["*"]
   APP_NAME=LlegarCasa Scrapper
   APP_VERSION=1.0.0
   ```

4. **Advanced Settings**:
   - **Health Check Path**: `/health`
   - **Auto-Deploy**: Yes

#### Option B: Using render.yaml (Infrastructure as Code)

1. The `render.yaml` file is already configured in your repository
2. Simply connect your repository to Render
3. Render will automatically detect and use the `render.yaml` configuration
4. Update the `CORS_ORIGINS` value in `render.yaml` with your actual frontend domain

### 3. Post-Deployment Configuration

#### Update CORS Origins
After deployment, update the CORS origins in your environment variables:
```
CORS_ORIGINS=["https://your-frontend-domain.com", "https://your-custom-domain.com"]
```

#### Monitor the Application
Your application will be available at:
- Health check: `https://your-app.onrender.com/health`
- API docs: `https://your-app.onrender.com/docs`
- Monitoring: `https://your-app.onrender.com/monitoring/health/system`

## Resource Requirements

### Minimum Requirements
- **Plan**: Starter ($7/month) for development/testing
- **RAM**: 512 MB minimum
- **CPU**: 0.1 CPU minimum

### Recommended for Production
- **Plan**: Standard ($25/month) or higher
- **RAM**: 2 GB or more
- **CPU**: 1 CPU or more

### Important Notes:
- Browser automation (Playwright) is resource-intensive
- Each scraping request uses significant memory
- Consider using Professional plans for high-traffic scenarios

## Environment Variables Reference

| Variable                   | Value              | Description                                  |
| -------------------------- | ------------------ | -------------------------------------------- |
| `ENVIRONMENT`              | `production`       | Sets the application environment             |
| `DEBUG`                    | `false`            | Disables debug mode for production           |
| `SCRAPER_HEADLESS_MODE`    | `true`             | Runs browser in headless mode                |
| `SCRAPER_SAVE_SCREENSHOTS` | `false`            | Disables screenshot saving                   |
| `SCRAPER_DEBUG_MODE`       | `false`            | Disables scraper debug mode                  |
| `CORS_ORIGINS`             | `["*"]`            | Allowed CORS origins (update for production) |
| `PORT`                     | Auto-set by Render | Port for the application                     |

## Health Checks and Monitoring

The application includes comprehensive health checks:

- **Basic Health**: `/health`
- **System Health**: `/monitoring/health/system`
- **Detailed Health**: `/monitoring/health/detailed`
- **Metrics**: `/monitoring/metrics`
- **Performance**: `/monitoring/performance`

## Troubleshooting

### Common Issues

#### 1. Build Failures
**Error**: Docker build fails during Playwright installation
**Solution**: 
- Check that all system dependencies are installed in the Dockerfile
- Verify the Playwright version in requirements.txt

#### 2. Memory Issues
**Error**: Container killed due to memory limits
**Solutions**:
- Upgrade to a higher Render plan (Standard or Professional)
- Optimize the number of concurrent browser instances
- Consider adding swap space

#### 3. Browser Launch Failures
**Error**: Browser fails to start in headless mode
**Solutions**:
- Ensure `SCRAPER_HEADLESS_MODE=true`
- Check that all browser dependencies are installed
- Verify the container has sufficient resources

#### 4. Startup Timeouts
**Error**: Service fails health checks during startup
**Solutions**:
- Increase startup time limits in Render settings
- Check application logs for startup errors
- Verify the health check endpoint is responding

### Checking Logs

To view application logs:
1. Go to your service in the Render dashboard
2. Click on the "Logs" tab
3. Look for error messages during startup or runtime

### Performance Optimization

1. **Enable Request Caching**: Consider implementing caching for frequently requested data
2. **Rate Limiting**: The application includes built-in rate limiting
3. **Monitoring**: Use the built-in monitoring endpoints to track performance
4. **Scaling**: Consider horizontal scaling for high-traffic scenarios

## Custom Domain Setup

1. **Add Custom Domain**:
   - Go to your service settings in Render
   - Add your custom domain
   - Update DNS records as instructed

2. **Update CORS Origins**:
   ```
   CORS_ORIGINS=["https://yourdomain.com"]
   ```

## Security Considerations

1. **Environment Variables**: Never commit sensitive data to your repository
2. **CORS Configuration**: Restrict CORS origins to your actual domains
3. **Rate Limiting**: The application includes built-in rate limiting
4. **HTTPS**: Render provides free SSL certificates

## Support

If you encounter issues:

1. Check the application logs in Render dashboard
2. Test the health endpoints
3. Review the troubleshooting section above
4. Contact Render support for infrastructure issues

## Cost Estimation

**Development/Testing**:
- Starter Plan: $7/month
- Estimated monthly cost: $7-14

**Production**:
- Standard Plan: $25/month
- Professional Plan: $85/month
- Estimated monthly cost: $25-85 depending on usage

## Next Steps

After deployment:

1. Test all API endpoints
2. Monitor application performance
3. Set up alerts for health check failures
4. Configure proper CORS origins
5. Consider setting up a custom domain
6. Implement proper logging aggregation if needed 