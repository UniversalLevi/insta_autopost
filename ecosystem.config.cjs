/**
 * PM2 ecosystem config for InstaForge (production).
 * Use: pm2 start ecosystem.config.cjs
 *
 * Keeps the app running by:
 * - Restarting on crash (autorestart)
 * - Restarting if memory exceeds limit (prevents OOM)
 * - Exponential backoff between restarts (avoids restart loops)
 * - Optional daily cron restart as a safety net (edit cron_restart to enable)
 */

module.exports = {
  apps: [
    {
      name: "instaforge",
      script: "main.py",
      interpreter: "python",
      cwd: __dirname,

      // --- Restart behavior ---
      autorestart: true,
      max_restarts: 30,
      min_uptime: "10s",
      restart_delay: 2000,
      exp_backoff_restart_delay: 100,

      // Restart if memory exceeds (adjust for your server; 600M is conservative)
      max_memory_restart: "600M",

      // Optional: force restart daily at 4:00 AM to clear stuck state / slow leaks.
      // Remove or comment out if you don't want scheduled restarts.
      cron_restart: "0 4 * * *",

      // Graceful shutdown (give FastAPI/uvicorn time to close)
      kill_timeout: 15000,
      wait_ready: false,
      listen_timeout: 10000,

      // --- Logs ---
      out_file: "./logs/pm2-out.log",
      error_file: "./logs/pm2-err.log",
      merge_logs: true,
      time: true,

      // --- Environment ---
      env: {
        ENVIRONMENT: "production",
      },
      env_production: {
        ENVIRONMENT: "production",
      },
    },
  ],
};
