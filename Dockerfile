# Use a base image that supports Python 3.11.9
#FROM python:3.11-slim
FROM python:3.11-slim

# Install FFmpeg
RUN apt-get update && \
    apt-get install -y ffmpeg

# Set up your application
WORKDIR /app
COPY . .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose port and run the application
CMD ["python3", "-m", "bot"]
