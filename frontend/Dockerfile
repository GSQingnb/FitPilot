# FitPilot Frontend — Next.js production image
FROM node:22-alpine

RUN corepack enable && corepack prepare pnpm@11 --activate
WORKDIR /app

ARG NEXT_PUBLIC_API_BASE_URL=/api
ENV NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
ENV NODE_ENV=production

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./

RUN pnpm install --frozen-lockfile --ignore-scripts || pnpm install --no-frozen-lockfile --ignore-scripts

COPY . .

# Validate NEXT_PUBLIC_API_BASE_URL before building — reject common contamination
# patterns (Git Bash/MSYS path conversion, file:// URIs, Windows drive letters).
RUN node -e "const v=process.env.NEXT_PUBLIC_API_BASE_URL||''; if(v.match(/^file:|^[A-Za-z]:[\\\\\\/]|\\\\|Program Files/i)){console.error('REJECTED NEXT_PUBLIC_API_BASE_URL:',v);process.exit(1)} console.log('API base URL:',v)"

RUN pnpm build

RUN addgroup -g 1001 -S nodejs && adduser -S nextjs -u 1001 && \
    chown -R nextjs:nodejs /app

USER nextjs

ENV PORT=3000
ENV HOSTNAME=0.0.0.0
EXPOSE 3000

CMD ["pnpm", "start"]
