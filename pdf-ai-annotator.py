import os
import glob
import time
import json
import argparse
import pikepdf
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables (for GEMINI_KEY)
load_dotenv()

# Initialize the Gemini AI client
gemini_key = os.getenv("GEMINI_KEY")
client = genai.Client(api_key=gemini_key)

# Configure the Gemini model generation
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_schema": types.Schema(
        type=types.Type.OBJECT,
        properties={
            "summary": types.Schema(type=types.Type.STRING),
            "keywords": types.Schema(type=types.Type.STRING),
            "filename": types.Schema(type=types.Type.STRING),
            "title": types.Schema(type=types.Type.STRING),
        },
    ),
    "response_mime_type": "application/json",
}

# The prompt to be used for generating metadata
PROMPT = (
    "Review the file. Your task is to produce a 4 sentence summary, "
    "list of 100 keywords, an informative title, and a suitable filename "
    "that would be informative yet terse. The filename should include a "
    "relevant date and the original file extension."
)

def process_file(input_file_path, output_dir):
    """
    Processes a single PDF file:
      - Uploads the file to Gemini for metadata generation.
      - Parses the Gemini response.
      - Updates the PDF's XMP metadata with the title, summary, and keywords.
      - Saves the updated PDF to the output directory with the new filename.
      - Removes the original file.
    """
    print(f"Processing file: {input_file_path}")
    
    # Upload the file for processing
    file_obj = client.files.upload(file=input_file_path)
    
    # Request metadata generation from Gemini
    response = client.models.generate_content(
        model="gemini-2.0-flash-lite-preview-02-05",
        config=generation_config,
        contents=[PROMPT, file_obj]
    )
    
    # Debug/log the raw response text if needed
    # print(response.text)
    
    # Parse the JSON response from the model
    result = json.loads(response.text)
    summary     = result.get("summary", "")
    keywords    = result.get("keywords", "")
    new_filename = result.get("filename", "updated_file.pdf")
    title       = result.get("title", "")
    
    print("Title:", title)
    print("Summary:", summary)
    print("Keywords:", keywords)
    print("New filename:", new_filename)
    
    # Open the PDF and update its metadata using pikepdf's open_metadata interface.
    with pikepdf.open(input_file_path) as pdf:
        with pdf.open_metadata() as meta:
            meta["dc:title"] = title
            meta["dc:description"] = summary
            meta["dc:subject"] = keywords
        
        # Construct the full output path using the new filename
        output_file_path = os.path.join(output_dir, new_filename)
        pdf.save(output_file_path)
    
    # Remove the original file after processing
    os.remove(input_file_path)
    print(f"Processed and moved file to: {output_file_path}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor an input directory for files matching a pattern and process them."
    )
    parser.add_argument(
        "input_dir",
        help="Directory to monitor for incoming PDF files"
    )
    parser.add_argument(
        "file_pattern",
        help="File pattern to match (e.g., '*.pdf')"
    )
    parser.add_argument(
        "output_dir",
        help="Directory where the processed files will be saved"
    )
    parser.add_argument(
        "poll_interval",
        type=int,
        default=5,
        help="Polling interval (in seconds) for checking the input directory (default: 5)"
    )
    parser.add_argument(
        "task_pause_time",
        type=int,
        default=60,
        help="Amount of time to pause between task (default: 60)"
    )
    args = parser.parse_args()
    
    input_dir = args.input_dir
    file_pattern = args.file_pattern
    output_dir = args.output_dir
    interval = args.poll_interval
    pause_time = args.task_pause_time
    
    # Verify that the input and output directories exist
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist.")
        exit(1)
    if not os.path.isdir(output_dir):
        print(f"Error: Output directory '{output_dir}' does not exist.")
        exit(1)
    
    print(f"Monitoring directory: {input_dir} for files matching: {file_pattern}")
    print(f"Processed files will be saved to: {output_dir}")
    print(f"Polling interval: {interval} seconds\n")
    
    # Continuously monitor the input directory
    while True:
        # Use glob to find files matching the file pattern in the input directory
        matching_files = glob.glob(os.path.join(input_dir, file_pattern))
        
        if matching_files:
            for file_path in matching_files:
                try:
                    process_file(file_path, output_dir)
                except Exception as e:
                    print(f"Error processing file '{file_path}': {e}")
                time.sleep(pause_time)
        else:
            # No matching files found
            pass
        
        # Wait for the specified interval before checking again
        time.sleep(interval)

if __name__ == '__main__':
    main()
