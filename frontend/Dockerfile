FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# Serve with a lightweight static server
FROM node:20-alpine
RUN npm install -g serve
COPY --from=builder /app/dist /app/dist
CMD ["serve", "-s", "/app/dist", "-l", "5173"]
