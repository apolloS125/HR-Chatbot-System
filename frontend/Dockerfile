FROM oven/bun:1.3 AS build
WORKDIR /app
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile
COPY . .
ARG NEXT_PUBLIC_LIFF_ID
ARG NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
ENV NEXT_PUBLIC_LIFF_ID=$NEXT_PUBLIC_LIFF_ID
ENV NEXT_PUBLIC_BACKEND_URL=$NEXT_PUBLIC_BACKEND_URL
RUN bun run build

FROM oven/bun:1.3-slim
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app ./
EXPOSE 3000
CMD ["bun", "run", "start"]
