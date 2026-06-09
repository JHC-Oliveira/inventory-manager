# Stage 1 — Dev server (we use this for now)
FROM node:22-alpine3.22

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev"]