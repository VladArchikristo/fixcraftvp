FROM node:20-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production
COPY src/ ./src/
COPY .env.example ./.env.example
COPY data/toll_navigator.db /app/data/toll_navigator.db
RUN mkdir -p /app/data
EXPOSE 3001
CMD ["node", "src/server.js"]
