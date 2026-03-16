# Use an official Python runtime as a parent image
FROM python:3.11.0

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the working directory in the container
WORKDIR /app

# System deps:
# - git: required for `clip @ git+https://...`
# - ffmpeg: used for video encoding/decoding in pipeline
# - libgl1/libglib2.0-0: common runtime deps for OpenCV on Linux
RUN apt-get update \
	&& apt-get install -y --no-install-recommends \
		git \
		ffmpeg \
		libgl1 \
		libglib2.0-0 \
	&& rm -rf /var/lib/apt/lists/*

# Install dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy the current directory contents into the container at /app
COPY . /app/

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application (using development server for now)
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]