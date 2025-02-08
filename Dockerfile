# Use an official lightweight Python image.
FROM python:3.9-slim

# Set the working directory inside the container.
WORKDIR /app

# Copy the requirements file into the container.
COPY requirements.txt .

# Upgrade pip and install dependencies.
RUN pip install --progress-bar off --upgrade pip && pip install --progress-bar off -r requirements.txt

# Copy the rest of your application code into the container.
COPY pdf-ai-annotator.py .

# Expose any ports if your app listens on one (not necessary for a simple batch script)
# EXPOSE 8000

# Set the default command to run your script.
CMD ["python", "pdf-ai-annotator.py"]
