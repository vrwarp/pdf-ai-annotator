import os
import time
import google.genai as genai
from google.genai import types
from dotenv import load_dotenv
import json
import pikepdf

load_dotenv()

gemini_key = os.getenv("GEMINI_KEY")
client = genai.Client(api_key=gemini_key)

# Create the model
generation_config = {
  "temperature": 1,
  "top_p": 0.95,
  "top_k": 64,
  "max_output_tokens": 8192,
  "response_schema": types.Schema(
    type = types.Type.OBJECT,
    properties = {
      "summary": types.Schema(
        type = types.Type.STRING,
      ),
      "keywords": types.Schema(
        type = types.Type.STRING,
      ),
      "filename": types.Schema(
        type = types.Type.STRING,
      ),
      "title": types.Schema(
        type = types.Type.STRING,
      ),
    },
  ),
  "response_mime_type": "application/json",
}

input_file_path = "/Users/btsai/Downloads/BRW441CA8384788_000502.pdf"
file = client.files.upload(file=input_file_path)

response = client.models.generate_content(
  model="gemini-2.0-flash-lite-preview-02-05",
  config=generation_config,
  contents=[
    """Review the file. Your task is to produce a 4 sentence summary,
    list of 100 keywords, a informative title, and a suitable filename that would be informative
    yet terse. The filename should include a relevant date, including the
    original file extension.
    
    Summarize it then propose a filename that would be informative but
    terse. Please also add in a relevant date.""",
    file])
print(response.text)
result = json.loads(response.text)
summary = result.get("summary", "")
keywords = result.get("keywords", "")
new_filename = result.get("filename", "updated_file.pdf")
title = result.get("title", "")

print("Title:", title)
print("Summary:", summary)
print("Keywords:", keywords)
print("New filename:", new_filename)

# dc:description
# dc:subject

pdf = pikepdf.open(input_file_path)
with pdf.open_metadata() as meta:
    meta["dc:title"] = title
    meta["dc:description"] = summary
    meta["dc:subject"] = keywords
pdf.save("/Users/btsai/Downloads/"+new_filename)
pdf.close()