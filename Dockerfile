# Stage 1: Build frontend
FROM node:22-alpine AS frontend-builder

WORKDIR /app
COPY package.json ./
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm ci
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# Stage 2: Build backend
FROM python:3.13-slim

# Install uv
RUN pip install uv

WORKDIR /app

# Copy backend
COPY backend/ ./backend/
COPY pyproject.toml ./

# Install backend dependencies
RUN cd backend && uv pip install --system -r requirements.txt

# Copy built frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create data directory
RUN mkdir -p /app/backend/data

# Expose port
EXPOSE 21345

# Set working directory
WORKDIR /app/backend

# Start backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "21345"]
