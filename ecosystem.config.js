module.exports = {
  apps: [
    {
      name: 'discord-always-online-idler',
      script: 'main.py',
      interpreter: 'python3',
      cwd: __dirname,
      env: {
        // Provide up to 5 tokens; extras will be ignored by the app
        TOKENS: 'token1, token2, token3, token4, token5',
      },
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      out_file: './pm2-out.log',
      error_file: './pm2-error.log',
      time: true,
    },
  ],
};
