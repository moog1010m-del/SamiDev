FROM node:22-alpine
WORKDIR /app
COPY gamehost /app/gamehost
COPY game /app/game
ENV NODE_ENV=production SAMIDEV_GAMEHOST_PORT=8091 SAMIDEV_GAME_DIR=/app/game
USER node
EXPOSE 8091
CMD ["node", "/app/gamehost/server.js"]
