import os
import json
import argparse
from google import genai
from google.genai import types
from dotenv import load_dotenv
import pikepdf

# Load environment variables
load_dotenv()

# Parse command-line arguments
parser = argparse.ArgumentParser(
    description="Process a PDF file using Gemini AI to update its metadata and rename it."
)
parser.add_argument(
    "input_file",
    help="Path to the input PDF file",
)
parser.add_argument(
    "output_dir",
    help="Directory where the updated PDF will be saved",
)
args = parser.parse_args()

input_file_path = args.input_file
output_dir = args.output_dir

# Verify that the input file exists
if not os.path.isfile(input_file_path):
    print(f"Error: The input file '{input_file_path}' does not exist.")
    exit(1)

# Verify that the output directory exists; if not, exit.
if not os.path.isdir(output_dir):
    print(f"Error: The output directory '{output_dir}' does not exist.")
    exit(1)

# Initialize the Gemini AI client
gemini_key = os.getenv("GEMINI_KEY")
client = genai.Client(api_key=gemini_key)

# Configure the model generation
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

# Upload the input file to Gemini
file = client.files.upload(file=input_file_path)

# Request content generation from the model
response = client.models.generate_content(
    model="gemini-2.0-flash-lite-preview-02-05",
    config=generation_config,
    contents=[
        """Review the file. Your task is to produce a 4 sentence summary,
        list of 100 keywords, a informative title, and a suitable filename
        that would be informative yet terse. The filename should include a
        relevant date, including the original file extension.
        
        Summarize it then propose a filename that would be informative but
        terse. Please also add in a relevant date.""",
        file
    ]
)

# Output the raw response text (for debugging/logging)
print(response.text)

# Parse the JSON response from the model
result = json.loads(response.text)
summary   = result.get("summary", "")
keywords  = result.get("keywords", "")
new_filename = result.get("filename", "updated_file.pdf")
title     = result.get("title", "")

print("Title:", title)
print("Summary:", summary)
print("Keywords:", keywords)
print("New filename:", new_filename)

# Open the input PDF and update its metadata using pikepdf's metadata interface
with pikepdf.open(input_file_path) as pdf:
    with pdf.open_metadata() as meta:
        meta["dc:title"] = title
        meta["dc:description"] = summary
        meta["dc:subject"] = keywords
    # Construct the full output file path using the provided output directory
    output_file_path = os.path.join(output_dir, new_filename)
    # Save the updated PDF
    pdf.save(output_file_path)

print(f"PDF metadata updated and saved to {output_file_path}")
