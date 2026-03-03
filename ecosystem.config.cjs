module.exports = {
  apps: [
    {
      name: "instaforge",

      // Run your existing Python entrypoint
      script: "main.py",
      interpreter: "python3",          // or "python" if that's what you use
      cwd: "/var/www/instaAutoPost",

      // ---- Restart / stability ----
      autorestart: true,
      max_restarts: 20,
      min_uptime: "20s",
      restart_delay: 5000,
      max_memory_restart: "800M",

      // ---- Logging ----
      out_file: "./logs/pm2-out.log",
      error_file: "./logs/pm2-error.log",
      merge_logs: true,
      time: true,

      // ---- Env for main.py / web.main:app ----
      env: {
        ENVIRONMENT: "production",
        HOST: "127.0.0.1",
        PORT: "8011",
        WORKERS: "1"    // main.py uses this when ENVIRONMENT=production
      }
    }
  ]
};