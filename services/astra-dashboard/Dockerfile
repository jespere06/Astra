FROM node:20-alpine AS development

WORKDIR /app

COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]
