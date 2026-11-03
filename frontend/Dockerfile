FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Atalhos de entrada por perfil no ecrã de login (dados de demonstração). Usar VITE_DEMO=0 em produção real.
ARG VITE_DEMO=1
ENV VITE_DEMO=$VITE_DEMO
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
