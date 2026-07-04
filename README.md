# PDF AI Annotator

[![CI](https://github.com/vrwarp/pdf-ai-annotator/actions/workflows/ci.yml/badge.svg)](https://github.com/vrwarp/pdf-ai-annotator/actions/workflows/ci.yml)
[![Docker Publish](https://github.com/vrwarp/pdf-ai-annotator/actions/workflows/docker-publish.yml/badge.svg)](https://github.com/vrwarp/pdf-ai-annotator/actions/workflows/docker-publish.yml)
[![Docker Hub](https://img.shields.io/docker/pulls/vrwarp/pdf-ai-annotator.svg)](https://hub.docker.com/r/vrwarp/pdf-ai-annotator)

PDF AI Annotator is a Python application that monitors an input directory for PDF files, processes them using Google's Gemini AI to generate metadata (summary, keywords, title, and a new filename), updates the PDF's XMP metadata using [pikepdf](https://pikepdf.readthedocs.io/), and then moves the processed file to an output directory. All configuration options can be set via command-line arguments or via environment variables defined in a `.env` file.

It ships in two flavours:

- **CLI annotator** (`pdf_ai_annotator.py`) — a headless watcher that polls a directory and processes files as they arrive.
- **Web management portal** (`web_portal.py`) — a [FastAPI](https://fastapi.tiangolo.com/) web UI to configure the app, upload and browse files, start/stop the processor, and tail logs from a browser.

This repository is hosted on GitHub at:
[https://github.com/vrwarp/pdf-ai-annotator](https://github.com/vrwarp/pdf-ai-annotator)

A Docker image is also available at Docker Hub:
[`vrwarp/pdf-ai-annotator:latest`](https://hub.docker.com/r/vrwarp/pdf-ai-annotator)

## Features

- **Automated Monitoring:** Continuously monitors an input directory for PDF files matching a specified pattern.
- **Metadata Generation:** Uses Gemini AI to generate a short summary, a list of keywords, a title, and a new filename for each PDF.
- **PDF Metadata Update:** Updates the PDF's XMP metadata with the generated title, summary, and keywords.
- **Consistent Naming:** Renames files to a structured `[Date]_[Category]_[Source]_[Description]_[Details].pdf` convention.
- **Safe by Default:** Sanitizes generated filenames against path traversal, and avoids data loss when the input and output files resolve to the same path.
- **Cautious Mode:** Optionally prompts for confirmation before saving processed files and deleting originals.
- **Web Portal:** Browser-based dashboard for configuration, file management, processor control, and live logs.

## Prerequisites

- Python 3.9+
- Gemini AI API key (set as `GEMINI_KEY`)
- The Python libraries listed in [`requirements.txt`](requirements.txt), including:
  - [google-genai](https://pypi.org/project/google-genai/)
  - [pikepdf](https://pypi.org/project/pikepdf/)
  - [python-dotenv](https://pypi.org/project/python-dotenv/)
  - [fastapi](https://pypi.org/project/fastapi/) + [uvicorn](https://pypi.org/project/uvicorn/) (web portal)

## Installation

1. **Clone the Repository:**

   ```bash
   git clone https://github.com/vrwarp/pdf-ai-annotator.git
   cd pdf-ai-annotator
   ```

2. **(Optional) Create and Activate a Virtual Environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate
   ```

3. **Install Dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

## Configuration

The application can be configured using command-line arguments or via environment variables defined in a `.env` file. Create a `.env` file in the root directory with the following content:

```ini
# .env file example
GEMINI_KEY=your_gemini_api_key
INPUT_DIR=/path/to/input/directory
FILE_PATTERN=*.pdf
OUTPUT_DIR=/path/to/output/directory
POLL_INTERVAL=5
TASK_PAUSE_TIME=60
CAUTIOUS=false
```

When using the web portal, these values can also be edited (and persisted to `.env`) from the **Configuration** page.

## Usage

### Running the CLI Annotator

You can run the script with command-line options. For example:

```bash
python pdf_ai_annotator.py --input_dir /path/to/input --file_pattern "*.pdf" --output_dir /path/to/output --poll_interval 5 --task_pause_time 60
```

If the `.env` file is properly configured, you can simply run:

```bash
python pdf_ai_annotator.py
```

### Running the Web Portal

Start the FastAPI management portal (defaults to `http://0.0.0.0:8000`):

```bash
python web_portal.py
```

Then open [http://localhost:8000](http://localhost:8000) in your browser. From there you can:

- **Dashboard** — see processor status and processing stats.
- **Files** — upload PDFs into the input directory and browse/delete input and output files.
- **Configuration** — edit and persist settings to `.env`.
- **Logs** — tail recent processing logs.
- Start and stop the background processor via the dashboard controls (`POST /api/processor/start` and `POST /api/processor/stop`).

### Command-Line Arguments

- `--input_dir`: Directory to monitor for incoming PDF files.
- `--file_pattern`: Glob pattern to match files (e.g., `"*.pdf"`).
- `--output_dir`: Directory where processed files will be saved.
- `--poll_interval`: Polling interval (in seconds) for checking the input directory (default: 5).
- `--task_pause_time`: Time to pause (in seconds) between processing each file (default: 60).
- `--cautious`: Prompt for confirmation before saving processed files and deleting originals.

### Environment Variables

Each flag has a corresponding environment variable which you can set in your `.env` file:

- `INPUT_DIR`
- `FILE_PATTERN`
- `OUTPUT_DIR`
- `POLL_INTERVAL`
- `TASK_PAUSE_TIME`
- `CAUTIOUS`

## Development

If you want to contribute or modify the code, follow these steps to set up your development environment.

### Install Development Dependencies

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

### Running Tests

This project uses [pytest](https://docs.pytest.org/). Tests live in the [`tests/`](tests/) directory and are split into:

- **Unit tests** for the CLI annotator (`tests/test_pdf_ai_annotator.py`) — the Gemini API and `pikepdf` are fully mocked.
- **Unit and end-to-end integration tests** for the web portal (`tests/test_web_portal.py`) — the FastAPI app is driven through an in-process HTTP client (`TestClient`), exercising real request/response cycles, file uploads, config persistence, and the background processor lifecycle.

Run the whole suite from the repository root:

```bash
pytest
```

No Gemini API key is required to run the tests — a placeholder key is injected automatically (see `tests/conftest.py`) and all external calls are mocked, so the tests are fast, deterministic, and offline.

### Continuous Integration

Every push and pull request to `main` runs the [CI workflow](.github/workflows/ci.yml), which:

- Runs the test suite across Python 3.9, 3.11, and 3.12.
- Builds the Docker image to verify the `Dockerfile`.

### Docstrings

All functions, methods, and classes are documented using **Google Style Python Docstrings**. Please ensure that any new code includes appropriate documentation.

## Docker Deployment

You can easily containerize and deploy the application using Docker.

### Using the Provided Docker Image

A Docker image is available on Docker Hub at [`vrwarp/pdf-ai-annotator:latest`](https://hub.docker.com/r/vrwarp/pdf-ai-annotator).

By default the container starts the **web portal** on port 8000:

```bash
docker run --rm \
  -p 8000:8000 \
  -e GEMINI_KEY=your_gemini_api_key \
  -e INPUT_DIR=/data/input \
  -e OUTPUT_DIR=/data/output \
  -v "$(pwd)/input:/data/input" \
  -v "$(pwd)/output:/data/output" \
  vrwarp/pdf-ai-annotator:latest
```

To run the **headless CLI annotator** instead of the web portal, override the command:

```bash
docker run --rm \
  -e GEMINI_KEY=your_gemini_api_key \
  -e INPUT_DIR=/data/input \
  -e OUTPUT_DIR=/data/output \
  -v "$(pwd)/input:/data/input" \
  -v "$(pwd)/output:/data/output" \
  vrwarp/pdf-ai-annotator:latest python pdf_ai_annotator.py
```

### Building Locally

```bash
docker build -t pdf-ai-annotator:local .
```

### Automated Publishing

The image is published to Docker Hub automatically by the [Docker Publish workflow](.github/workflows/docker-publish.yml) whenever changes are merged to `main` (tagged `latest` and with the short commit SHA), and whenever a `v*` version tag is pushed (tagged with the corresponding semantic version).

Publishing requires two repository secrets to be configured under **Settings → Secrets and variables → Actions**:

- `DOCKERHUB_USERNAME` — your Docker Hub username.
- `DOCKERHUB_TOKEN` — a Docker Hub [access token](https://docs.docker.com/security/for-developers/access-tokens/) with push permission.

## Acknowledgements

This `README.md` file and large parts of the `pdf_ai_annotator.py` are written by ChatGPT.
