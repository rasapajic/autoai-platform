FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm ci

COPY . .

ARG NEXT_PUBLIC_API_URL=https://autoai-platform-production.up.railway.app
ARG NEXT_PUBLIC_APP_URL=
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_APP_URL=$NEXT_PUBLIC_APP_URL

RUN mkdir -p public \
  && npm run build \
  && mkdir -p .next/standalone/.next \
  && cp -r .next/static .next/standalone/.next/static \
  && cp -r public .next/standalone/public

ENV NODE_ENV=production
ENV HOSTNAME=0.0.0.0

EXPOSE 3000
CMD ["node", ".next/standalone/server.js"]
