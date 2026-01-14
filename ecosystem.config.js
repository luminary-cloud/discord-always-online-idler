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
        // Human-like sleep schedule in EU timezone
        HUMAN_SCHEDULE_MODE: 'true', // Set to 'true' to enable realistic sleep/wake cycles
        TIMEZONE: 'Europe/Amsterdam', // EU timezone (CET/CEST)
        SLEEP_TIME_START: '21', // Earliest hour accounts can go to sleep (22:00)
        SLEEP_TIME_END: '2', // Latest hour accounts can go to sleep (02:00 next day)
        WAKE_TIME_START: '6', // Earliest hour accounts can wake up (06:00)
        WAKE_TIME_END: '10', // Latest hour accounts can wake up (10:00)
        // Game activity settings (fake game playing)
        GAME_ACCOUNTS: '', // Comma-separated usernames or user IDs to play the game (e.g., 'user1,user2,123456789')
        GAME_NAME: 'GAME NAME', // Game name to display
        GAME_IMAGE:
          'https://cdn.discordapp.com/app-icons/', // URL to game icon/image
        GAME_SESSIONS: '10-15,18-23', // Time windows for gaming (e.g., '11-14,20-23' = afternoon and evening)
        MIN_PLAY_HOURS: '2', // Minimum hours to play per session
        MAX_PLAY_HOURS: '5', // Maximum hours to play per session
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
