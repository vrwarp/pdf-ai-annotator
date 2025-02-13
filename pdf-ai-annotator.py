import os
import glob
import time
import json
import argparse
import pikepdf
from google import genai
from dotenv import load_dotenv
from pydantic import BaseModel

class PdfAiAnnotations(BaseModel):
  summary: str
  keywords: str
  title: str
  filename: str

# Load environment variables (for GEMINI_KEY and others)
load_dotenv()

# Initialize the Gemini AI client using GEMINI_KEY from .env
gemini_key = os.getenv("GEMINI_KEY")
client = genai.Client(api_key=gemini_key)

# Configure the Gemini model generation
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_schema": PdfAiAnnotations,
    "response_mime_type": "application/json",
}

# The prompt to be used for generating metadata
PROMPT = (
"""
## Instructions for Document Processing

Hi team, your role is to process scanned documents so they are easy to find and understand. For each document, please follow these steps:

**Step 1: Quickly Understand the Document**

*   Take a moment to read through the document and get a general idea of what it's about.
    *   **What is the main topic?** (e.g., Medical bill, Financial statement)
    *   **Who sent it or created it?** (e.g., Doctor's office, Bank, Company name)
    *   **What kind of document is it?** (e.g., Invoice, Report, Letter)
    *   **What date is mentioned in the document?** (Look for dates at the top, in headers, or within the text)

**Step 2: Write a Short Summary**

*   Write a very brief summary of the document in just one or two sentences.
    *   **Focus on the most important information.**  Imagine you are telling a coworker what this document is in a few seconds.
    *   **Example:** "This document is a medical invoice from Dr. Smith for services provided to John Doe in October 2024."

**Step 3: List Key Topics (Keywords)**

*   Think about the main subjects, people, and things the document is about. List up to **10 keywords** that someone could use to search for this document later.
    *   **Think of words people might type into a search bar.**
    *   **Examples:**  `Invoice`, `Medical`, `Smith`, `October`, `2024`, `John Doe`, `Bill`, `Healthcare`, `Payment`, `Services`

**Step 4: Create an Informative Title**

*   Write a short title that quickly tells you what the document is. This title is for our use to easily understand the file.
    *   **Keep it brief but clear.**
    *   **Example:** `Medical Invoice - Dr. Smith - John Doe - Oct 2024`

**Step 5: Create a Suitable Filename (Very Important!)**

*   Now, create a filename for the document using the standard below. **This is crucial for keeping our files organized.**

---

**File Naming Standard**

To keep all our files in order, we use a specific system to name them. Please follow this exactly:

**`[Date]_[Category]_[Source]_[Description]_[Details].pdf`**

*   **Date:** This is usually the date on the document itself.
    *   **Preferred Format:** If the **full date (Day, Month, and Year)** is available, use **`YYYYMMDD`** format (Year, Month, Day).
        *   **Example:** For January 5th, 2025, use `20250105`
    *   **If the exact Day is missing:**  Use **`YYYYMM00`** format (Year, Month, `00` for day).
        *   **Example:** If the document is dated "January 2025" but no specific day, use `20250100`
    *   **If the Month and Day are missing (only Year is available):** Use **`YYYY0000`** format (Year, `00` for month, `00` for day).
        *   **Example:** If the document only says "2025", use `20250000`
    *   **If the Year is clear, but Month and Day are implied (e.g., "October Invoice" in a known year):** Use your best judgment. If the year is clearly related to the document's content, use `YYYYMM00` or `YYYYMMDD` if you can infer the month, otherwise use `YYYY0000`. **When in doubt, use the least specific date you are certain about.**
    *   **Rare cases: Month and Day known, but Year unclear:**  In extremely rare cases, if only Month and Day are truly identifiable, use **`0000MMDD`**.  **Double-check if you can find any year context.**
        *   **Example (very unusual):** If a very old document only has "March 15th" written, and no year can be found anywhere, use `00000315`. **This should be a last resort.**

    *   **Put the Date *first* in the filename.**

*   **Category:** Use a single, short word to group similar files together. Choose from these examples, or use your best judgment if it fits:
    *   **Examples:** `Medical`, `Financial`, `Insurance`, `Vehicle`, `Legal`, `ProjectA`, `ClientB`, `VendorC`
*   **Source:**  Who or where did this document come from?  Use a short, recognizable name.
    *   **Examples:** `Google`, `CityHall`, `DrJones`, `AcmeCorp`, `Internal` (if we created it ourselves)
*   **Description:** Briefly describe what the document *is*.  Use simple words.
    *   **Examples:** `Invoice`, `Report`, `Minutes`, `Agreement`, `Statement`, `Email`, `Form`
*   **Details:** Add extra information *only if needed* to tell similar files apart.  For example, a patient name, account number, or project phase.
    *   **Use hyphens** to separate words within the Details section.
    *   **Only use this section if it's truly necessary to make the filename clearer.**
    *   **Example:** `Patient-Johnson`, `Project-Phase2`, `Account-12345`

*   **Important Notes for Filenames:**
    *   **Separate each section with a single underscore** (`_`).
    *   **Do not use any spaces** in the filename.
    *   **Always end with `.pdf`** (if it's a PDF file).

**Examples with Incomplete Dates:**

*   **Document Date: "January 2025" (Day missing)**
    *   Filename Example: `20250100_Financial_BankABC_Statement_Checking.pdf`
*   **Document Date: "Year 2025" (Month and Day missing)**
    *   Filename Example: `20250000_Legal_LawFirmXYZ_Contract_VendorAgreement.pdf`
*   **Document Date: "March 15th" (Year completely missing - *very rare, use cautiously*)**
    *   Filename Example: `00000315_Medical_ClinicGeneral_Appointment_Patient-JSmith.pdf` (*Use this very rarely and only if absolutely no year context exists*)

**Example with Full Date:**

`20250310_Financial_MyBank_Statement_Savings-Account.pdf`
"""
)

def process_file(input_file_path, output_dir, cautious=False):
    """
    Processes a single PDF file:
      - Uploads the file to Gemini for metadata generation.
      - Parses the Gemini response.
      - Updates the PDF's XMP metadata with the title, summary, and keywords.
      - If cautious mode is enabled, asks for confirmation before:
          a) Saving the updated PDF to the output directory.
          b) Deleting the original file.
      - Otherwise, it saves the updated file and then removes the original.
    """
    print(f"\nProcessing file: {input_file_path}")
    
    # Upload the file for processing
    file_obj = client.files.upload(file=input_file_path)
    
    # Request metadata generation from Gemini
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        config=generation_config,
        contents=[PROMPT, file_obj]
    )
    
    # Parse the JSON response from the model
    result: PdfAiAnnotations = response.parsed
    summary = result.summary
    keywords = result.keywords
    new_filename = result.filename
    title = result.title
    
    if summary == "" or keywords == "" or new_filename == "" or title == "":
        print(f"Error: Metadata generation failed for {input_file_path}. Please check the Gemini API response.")
        return
    
    if new_filename[-4:] != ".pdf":
        print(f"Error: The generated filename '{new_filename}' does not end with '.pdf'.")
        return

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
        
        # If cautious mode is enabled, ask for confirmation before saving.
        if cautious:
            answer = input(f"Do you want to save the updated file to '{output_file_path}'? (y/n): ")
            if answer.strip().lower() != 'y':
                print("Skipping saving of updated file.")
                return
        
        # Save the updated PDF
        pdf.save(output_file_path)
        print(f"Updated file saved to: {output_file_path}")
    
    # If cautious mode is enabled, ask for confirmation before deleting the original file.
    if cautious:
        answer = input(f"Do you want to delete the original file '{input_file_path}'? (y/n): ")
        if answer.strip().lower() != 'y':
            print("Skipping deletion of original file.")
            return

    # Remove the original file after processing
    os.remove(input_file_path)
    print(f"Original file '{input_file_path}' deleted.\n")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor an input directory for files matching a pattern and process them."
    )
    parser.add_argument(
        "--input_dir",
        default=os.getenv("INPUT_DIR"),
        help="Directory to monitor for incoming PDF files (or set via .env: INPUT_DIR)"
    )
    parser.add_argument(
        "--file_pattern",
        default=os.getenv("FILE_PATTERN", "*.pdf"),
        help="File pattern to match (e.g., '*.pdf') (or set via .env: FILE_PATTERN)"
    )
    parser.add_argument(
        "--output_dir",
        default=os.getenv("OUTPUT_DIR"),
        help="Directory where the processed files will be saved (or set via .env: OUTPUT_DIR)"
    )
    parser.add_argument(
        "--poll_interval",
        type=int,
        default=int(os.getenv("POLL_INTERVAL", 5)),
        help="Polling interval (in seconds) for checking the input directory (default: 5 or via .env: POLL_INTERVAL)"
    )
    parser.add_argument(
        "--task_pause_time",
        type=int,
        default=int(os.getenv("TASK_PAUSE_TIME", 60)),
        help="Amount of time to pause between processing each file (default: 60 or via .env: TASK_PAUSE_TIME)"
    )
    parser.add_argument(
        "--cautious",
        action="store_true",
        default=(os.getenv("CAUTIOUS", "False").lower() in ["true", "1", "yes"]),
        help="Enable cautious mode to ask for confirmation before saving and deleting files (or set via .env: CAUTIOUS)"
    )
    args = parser.parse_args()
    
    input_dir = args.input_dir
    file_pattern = args.file_pattern
    output_dir = args.output_dir
    interval = args.poll_interval
    pause_time = args.task_pause_time
    cautious = args.cautious
    
    # Verify that the input and output directories exist
    if input_dir is None:
        print("Error: Input directory not provided. Use --input_dir or set INPUT_DIR in your .env file.")
        exit(1)
    if output_dir is None:
        print("Error: Output directory not provided. Use --output_dir or set OUTPUT_DIR in your .env file.")
        exit(1)
    if not os.path.isdir(input_dir):
        print(f"Error: Input directory '{input_dir}' does not exist.")
        exit(1)
    if not os.path.isdir(output_dir):
        print(f"Error: Output directory '{output_dir}' does not exist.")
        exit(1)
    
    print(f"Monitoring directory: {input_dir} for files matching: {file_pattern}")
    print(f"Processed files will be saved to: {output_dir}")
    print(f"Polling interval: {interval} seconds")
    print(f"Task pause time: {pause_time} seconds")
    print(f"Cautious mode: {'ON' if cautious else 'OFF'}\n")
    
    # Continuously monitor the input directory
    while True:
        # Use glob to find files matching the file pattern in the input directory
        matching_files = glob.glob(os.path.join(input_dir, file_pattern))
        
        if matching_files:
            for file_path in matching_files:
                try:
                    process_file(file_path, output_dir, cautious=cautious)
                except Exception as e:
                    print(f"Error processing file '{file_path}': {e}")
                # Pause between processing tasks
                time.sleep(pause_time)
        # Wait for the specified polling interval before checking again
        time.sleep(interval)

if __name__ == '__main__':
    main()
