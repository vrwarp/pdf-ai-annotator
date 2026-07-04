# Use an official lightweight Python image.
# Python 3.10+ is required by google-genai 2.x (Gemini 3 support).
FROM python:3.12-slim

# Set the working directory inside the container.
WORKDIR /app

# Copy the requirements file into the container.
COPY requirements.txt .

# Upgrade pip and install dependencies.
RUN pip install --progress-bar off --upgrade pip && pip install --progress-bar off -r requirements.txt

# Copy application code and assets.
COPY pdf_ai_annotator.py .
COPY web_portal.py .
COPY templates/ templates/
COPY static/ static/

# Expose the web management portal port.
EXPOSE 8000

# Default: start the web management portal.
# To run the CLI annotator instead: docker run ... python pdf_ai_annotator.py
CMD ["python", "web_portal.py"]
