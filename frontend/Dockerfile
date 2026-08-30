FROM node:20-slim

WORKDIR /app

# Install dependencies as root, then switch to non-root
COPY package.json package-lock.json* ./
RUN npm install

# Create non-root user (UID 1001, since 1000 exists in node image)
RUN groupadd -r epsilon && useradd -r -g epsilon -u 1001 -m -d /home/epsilon epsilon
RUN chown -R epsilon:epsilon /app
USER 1001

# Copy application
COPY --chown=epsilon:epsilon . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
