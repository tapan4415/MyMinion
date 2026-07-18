FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
COPY frontend/package.json ./frontend/package.json
COPY mobile/package.json ./mobile/package.json
RUN npm install
COPY frontend ./frontend
COPY shared ./shared
RUN npm --workspace frontend run build
FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app ./
EXPOSE 3000
CMD ["npm", "--workspace", "frontend", "start"]
