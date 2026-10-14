FROM node:22-alpine
WORKDIR /app
COPY --chown=node:node gamehost /app/gamehost
COPY --chown=node:node game /app/game
RUN mkdir -p /app/recordings && chown node:node /app/recordings
ENV NODE_ENV=production SAMIDEV_GAMEHOST_PORT=8091 SAMIDEV_GAME_DIR=/app/game
USER node
EXPOSE 8091
CMD ["node", "/app/gamehost/server.js"]
