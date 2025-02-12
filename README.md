# PDF AI Annotator

PDF AI Annotator is a Python application that monitors an input directory for PDF files, processes them using Google's Gemini AI to generate metadata (summary, keywords, title, and a new filename), updates the PDF’s XMP metadata using [pikepdf](https://pikepdf.readthedocs.io/), and then moves the processed file to an output directory. All configuration options can be set via command-line arguments or via environment variables defined in a `.env` file.

This repository is hosted on GitHub at:  
[https://github.com/vrwarp/pdf-ai-annotator](https://github.com/vrwarp/pdf-ai-annotator)

A Docker image is also available at Docker Hub:  
[`vrwarp/pdf-ai-annotator:latest`](https://hub.docker.com/r/vrwarp/pdf-ai-annotator)

## Features

- **Automated Monitoring:** Continuously monitors an input directory for PDF files matching a specified pattern.
- **Metadata Generation:** Uses Gemini AI to generate a short summary, a list of keywords, a title, and a new filename for each PDF.
- **PDF Metadata Update:** Updates the PDF's XMP metadata with the generated title, summary, and keywords.

## Prerequisites

- Python 3
- Gemini AI API key (set as `GEMINI_KEY`)
- The following Python libraries:
  - [google-genai](https://pypi.org/project/google-genai/)
  - [pikepdf](https://pypi.org/project/pikepdf/)
  - [python-dotenv](https://pypi.org/project/python-dotenv/)

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

   Install the dependencies:
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
```

## Usage

### Running Locally

You can run the script with command-line options. For example:

```bash
python pdf-ai-annotator.py --input_dir /path/to/input --file_pattern "*.pdf" --output_dir /path/to/output --poll_interval 5 --task_pause_time 60
```

If the `.env` file is properly configured, you can simply run:

```bash
python pdf-ai-annotator.py
```

### Command-Line Arguments

- `--input_dir`: Directory to monitor for incoming PDF files.
- `--file_pattern`: Glob pattern to match files (e.g., `"*.pdf"`).
- `--output_dir`: Directory where processed files will be saved.
- `--poll_interval`: Polling interval (in seconds) for checking the input directory (default: 5).
- `--task_pause_time`: Time to pause (in seconds) between processing each file (default: 60).

### Environment Variables

Each flag has a corresponding environment variable which you can set in your `.env` file:
- `INPUT_DIR`
- `FILE_PATTERN`
- `OUTPUT_DIR`
- `POLL_INTERVAL`
- `TASK_PAUSE_TIME`

## Docker Deployment

You can easily containerize and deploy the application using Docker.

### Using the Provided Docker Image

A Docker image is available on Docker Hub at [`vrwarp/pdf-ai-annotator:latest`](https://hub.docker.com/r/vrwarp/pdf-ai-annotator).

## Acknowledgements

This `README.md` file and large parts of the `pdf-ai-annotator.py` are written by ChatGPT.
