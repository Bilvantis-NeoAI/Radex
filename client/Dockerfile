FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install
RUN npm install uuid
RUN npm install firebase

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev"]