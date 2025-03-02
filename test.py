import unittest
import os
import tempfile
import shutil
from unittest.mock import patch, mock_open
from pydantic import ValidationError
import pikepdf
from google import genai
from pdf_ai_annotator import (
    PdfAiAnnotations,
    process_file,
    PROMPT,
    generation_config,
)  # Assuming your file is named pdf_ai_annotator.py


class TestPdfAiAnnotator(unittest.TestCase):
    def setUp(self):
        # Create temporary directories for input and output
        self.input_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()

        # Create a dummy PDF file for testing
        self.dummy_pdf_path = os.path.join(self.input_dir, "dummy.pdf")

        with pikepdf.Pdf.new() as pdf:
            pdf.save(self.dummy_pdf_path)

        # Sample data for mocking Gemini's response
        self.sample_gemini_response = {
            "summary": "This is a test summary.",
            "keywords": "test, summary, pdf",
            "title": "Test Document",
            "filename": "20240101_TestCategory_TestSource_TestDescription_TestDetails.pdf",
        }

        self.invalid_gemini_responses = [
            PdfAiAnnotations(summary="", keywords="", title="", filename=""),  # All empty
            PdfAiAnnotations(summary="This is a test summary.", keywords="test, summary, pdf", title="Test Document", filename=""),  # missing filename
            PdfAiAnnotations(summary="This is a test summary.", keywords="test, summary, pdf", title="", filename="valid_filename.pdf"),  # missing title
            PdfAiAnnotations(summary="", keywords="test, summary, pdf", title="Test Document", filename="valid_filename.pdf"),  # missing summary
            PdfAiAnnotations(summary="This is a test summary.", keywords="", title="Test Document", filename="valid_filename.pdf"),  # missing keywords
            PdfAiAnnotations(summary="This is a test summary.", keywords="test, summary, pdf", title="Test Document", filename="invalid_filename"),  # wrong extension
            PdfAiAnnotations(summary="", keywords="test, summary, pdf", title="Test Document", filename="20240101_TestCategory_TestSource_TestDescription_TestDetails.pdf"),  # empty summary
            PdfAiAnnotations(summary="This is a test summary.", keywords="", title="Test Document", filename="20240101_TestCategory_TestSource_TestDescription_TestDetails.pdf"),  # empty keywords
            PdfAiAnnotations(summary="This is a test summary.", keywords="test, summary, pdf", title="", filename="20240101_TestCategory_TestSource_TestDescription_TestDetails.pdf"),  # empty title
            PdfAiAnnotations(summary="This is a test summary.", keywords="test, summary, pdf", title="Test Document", filename=""),  # empty filename
        ]

    def tearDown(self):
        # Clean up temporary directories
        shutil.rmtree(self.input_dir)
        shutil.rmtree(self.output_dir)

    @patch("os.remove")
    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_process_file_success(
        self,
        mock_generate_content,
        mock_upload,
        mock_pikepdf_open,
        mock_os_remove,
    ):
        # Arrange
        mock_upload.return_value = "file_obj"
        mock_generate_content.return_value.parsed = PdfAiAnnotations(**self.sample_gemini_response)

        mock_pdf = mock_pikepdf_open.return_value.__enter__.return_value
        mock_meta = mock_pdf.open_metadata.return_value.__enter__.return_value

        # Act
        process_file(self.dummy_pdf_path, self.output_dir)

        # Assert
        mock_upload.assert_called_once_with(file=self.dummy_pdf_path)
        mock_generate_content.assert_called_once_with(
            model="gemini-2.0-flash",
            config=generation_config,
            contents=[PROMPT, "file_obj"],
        )

        mock_pikepdf_open.assert_called_once_with(self.dummy_pdf_path)
        mock_pdf.open_metadata.assert_called_once()
        mock_meta.__setitem__.assert_any_call("dc:title", self.sample_gemini_response["title"])
        mock_meta.__setitem__.assert_any_call("dc:description", self.sample_gemini_response["summary"])
        mock_meta.__setitem__.assert_any_call("dc:subject", self.sample_gemini_response["keywords"])

        expected_output_file_path = os.path.join(self.output_dir, self.sample_gemini_response["filename"])
        mock_pdf.save.assert_called_once_with(expected_output_file_path)
        mock_os_remove.assert_called_once_with(self.dummy_pdf_path)

    @patch("os.remove")
    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_process_file_success_cautious_skip_save(
        self,
        mock_generate_content,
        mock_upload,
        mock_pikepdf_open,
        mock_os_remove,
    ):
        # Arrange
        mock_upload.return_value = "file_obj"
        mock_generate_content.return_value.parsed = PdfAiAnnotations(**self.sample_gemini_response)
        mock_pdf = mock_pikepdf_open.return_value.__enter__.return_value

        with patch("builtins.input", return_value="n"):
            # Act
            process_file(self.dummy_pdf_path, self.output_dir, cautious=True)

        # Assert
        mock_pdf.save.assert_not_called()
        mock_os_remove.assert_not_called()

    @patch("os.remove")
    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_process_file_success_cautious_skip_delete(
        self,
        mock_generate_content,
        mock_upload,
        mock_pikepdf_open,
        mock_os_remove,
    ):
        # Arrange
        mock_upload.return_value = "file_obj"
        mock_generate_content.return_value.parsed = PdfAiAnnotations(**self.sample_gemini_response)
        mock_pdf = mock_pikepdf_open.return_value.__enter__.return_value

        with patch("builtins.input", side_effect=["y", "n"]):
            # Act
            process_file(self.dummy_pdf_path, self.output_dir, cautious=True)

        # Assert
        mock_pdf.save.assert_called_once()
        mock_os_remove.assert_not_called()


    @patch("os.remove")
    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_process_file_cautious_mode(
            self,
            mock_generate_content,
            mock_upload,
            mock_pikepdf_open,
            mock_os_remove
    ):
        # Arrange
        mock_upload.return_value = "file_obj"
        mock_generate_content.return_value.parsed = PdfAiAnnotations(**self.sample_gemini_response)

        mock_pdf = mock_pikepdf_open.return_value.__enter__.return_value
        with patch("builtins.input", side_effect=["y", "y"]):
            # Act
            mock_pikepdf_open.return_value.__enter__.return_value.save.return_value = None
            process_file(self.dummy_pdf_path, self.output_dir, cautious=True)

        # Assert
        mock_pdf.save.assert_called_once()
        mock_os_remove.assert_called_once()

    @patch("os.remove")
    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_process_file_missing_metadata(
            self,
            mock_generate_content,
            mock_upload,
            mock_pikepdf_open,
            mock_os_remove
    ):
        for invalid_response in self.invalid_gemini_responses:
            # Arrange
            mock_upload.return_value = "file_obj"
            mock_generate_content.return_value.parsed = invalid_response

            # Act
            process_file(self.dummy_pdf_path, self.output_dir)

            # Assert
            mock_os_remove.assert_not_called()
            mock_pikepdf_open.assert_not_called()


if __name__ == "__main__":
    unittest.main()