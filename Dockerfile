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

# Persist portal configuration to a mountable volume. Settings saved from the
# web UI are written to /config/settings.env, which survives restarts when the
# /config volume is mounted (e.g. -v ./config:/config).
ENV CONFIG_FILE=/config/settings.env
RUN mkdir -p /config
VOLUME ["/config"]

# The background processor starts automatically on launch. Set AUTO_START=false
# to disable and control it from the dashboard instead.
ENV AUTO_START=true

# Expose the web management portal port.
EXPOSE 8000

# Default: start the web management portal.
# To run the CLI annotator instead: docker run ... python pdf_ai_annotator.py
CMD ["python", "web_portal.py"]
