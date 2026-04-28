# Frontend Dockerfile — runs the Vite dev server.
#
# For a real production deploy you'd do a multi-stage build:
#   1. node:20 builds the static bundle into /app/dist
#   2. nginx:alpine serves /app/dist
#
# For development (which is what we use here), we just keep the Node
# image running with `npm run dev`.

FROM node:20-slim

WORKDIR /app

# Install deps first (cached layer when code changes but deps don't).
COPY package.json package-lock.json* ./
RUN npm install

# Copy the rest of the source.
COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
