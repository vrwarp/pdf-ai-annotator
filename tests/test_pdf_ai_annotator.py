"""Unit tests for the CLI annotator (``pdf_ai_annotator``).

These tests exercise the core ``process_file`` logic in isolation.  All calls to
the Gemini API and to ``pikepdf`` are mocked so the tests are fast, deterministic
and require no network access or API key.
"""

import os
import shutil
import tempfile
import unittest
from unittest.mock import patch

import pikepdf

from pdf_ai_annotator import (
    PdfAiAnnotations,
    process_file,
    PROMPT,
    generation_config,
)


class TestPdfAiAnnotator(unittest.TestCase):
    """Unit tests for the ``PdfAiAnnotator`` application."""

    def setUp(self):
        """Create temporary input/output directories and a dummy PDF file."""
        self.input_dir = tempfile.mkdtemp()
        self.output_dir = tempfile.mkdtemp()

        self.dummy_pdf_path = os.path.join(self.input_dir, "dummy.pdf")
        with pikepdf.Pdf.new() as pdf:
            pdf.save(self.dummy_pdf_path)

        # Sample data for mocking Gemini's response.
        self.sample_gemini_response = {
            "summary": "This is a test summary.",
            "keywords": "test, summary, pdf",
            "title": "Test Document",
            "filename": "20240101_TestCategory_TestSource_TestDescription_TestDetails.pdf",
        }

        # Responses that should cause processing to halt before saving.
        self.invalid_gemini_responses = [
            PdfAiAnnotations(summary="", keywords="", title="", filename=""),
            PdfAiAnnotations(summary="This is a test summary.", keywords="test, summary, pdf", title="Test Document", filename=""),
            PdfAiAnnotations(summary="This is a test summary.", keywords="test, summary, pdf", title="", filename="valid_filename.pdf"),
            PdfAiAnnotations(summary="", keywords="test, summary, pdf", title="Test Document", filename="valid_filename.pdf"),
            PdfAiAnnotations(summary="This is a test summary.", keywords="", title="Test Document", filename="valid_filename.pdf"),
            PdfAiAnnotations(summary="This is a test summary.", keywords="test, summary, pdf", title="Test Document", filename="invalid_filename"),
            PdfAiAnnotations(summary="", keywords="test, summary, pdf", title="Test Document", filename="20240101_TestCategory_TestSource_TestDescription_TestDetails.pdf"),
            PdfAiAnnotations(summary="This is a test summary.", keywords="", title="Test Document", filename="20240101_TestCategory_TestSource_TestDescription_TestDetails.pdf"),
            PdfAiAnnotations(summary="This is a test summary.", keywords="test, summary, pdf", title="", filename="20240101_TestCategory_TestSource_TestDescription_TestDetails.pdf"),
            PdfAiAnnotations(summary="This is a test summary.", keywords="test, summary, pdf", title="Test Document", filename=""),
        ]

    def tearDown(self):
        """Remove temporary directories."""
        shutil.rmtree(self.input_dir, ignore_errors=True)
        shutil.rmtree(self.output_dir, ignore_errors=True)

    # ── model schema ──────────────────────────────────────────────────────────

    def test_annotations_model_fields(self):
        """The Pydantic model exposes the four expected metadata fields."""
        ann = PdfAiAnnotations(**self.sample_gemini_response)
        self.assertEqual(ann.summary, "This is a test summary.")
        self.assertEqual(ann.keywords, "test, summary, pdf")
        self.assertEqual(ann.title, "Test Document")
        self.assertEqual(ann.filename, self.sample_gemini_response["filename"])

    # ── happy path ────────────────────────────────────────────────────────────

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
        """A valid response uploads, applies metadata, saves, and deletes the original."""
        mock_upload.return_value = "file_obj"
        mock_generate_content.return_value.parsed = PdfAiAnnotations(**self.sample_gemini_response)

        mock_pdf = mock_pikepdf_open.return_value.__enter__.return_value
        mock_meta = mock_pdf.open_metadata.return_value.__enter__.return_value

        process_file(self.dummy_pdf_path, self.output_dir)

        mock_upload.assert_called_once_with(file=self.dummy_pdf_path)
        mock_generate_content.assert_called_once_with(
            model="gemini-flash-latest",
            config=generation_config,
            contents=[PROMPT, "file_obj"],
        )

        mock_pikepdf_open.assert_called_once_with(self.dummy_pdf_path, allow_overwriting_input=True)
        mock_pdf.open_metadata.assert_called_once()
        mock_meta.__setitem__.assert_any_call("dc:title", self.sample_gemini_response["title"])
        mock_meta.__setitem__.assert_any_call("dc:description", self.sample_gemini_response["summary"])
        mock_meta.__setitem__.assert_any_call("dc:subject", self.sample_gemini_response["keywords"])

        expected_output_file_path = os.path.join(self.output_dir, self.sample_gemini_response["filename"])
        mock_pdf.save.assert_called_once_with(expected_output_file_path)
        mock_os_remove.assert_called_once_with(self.dummy_pdf_path)

    # ── cautious mode ─────────────────────────────────────────────────────────

    @patch("os.remove")
    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_process_file_cautious_skip_save(
        self,
        mock_generate_content,
        mock_upload,
        mock_pikepdf_open,
        mock_os_remove,
    ):
        """Declining the save prompt leaves both save and remove uncalled."""
        mock_upload.return_value = "file_obj"
        mock_generate_content.return_value.parsed = PdfAiAnnotations(**self.sample_gemini_response)
        mock_pdf = mock_pikepdf_open.return_value.__enter__.return_value

        with patch("builtins.input", return_value="n"):
            process_file(self.dummy_pdf_path, self.output_dir, cautious=True)

        mock_pdf.save.assert_not_called()
        mock_os_remove.assert_not_called()

    @patch("os.remove")
    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_process_file_cautious_skip_delete(
        self,
        mock_generate_content,
        mock_upload,
        mock_pikepdf_open,
        mock_os_remove,
    ):
        """Saving but declining deletion calls save once and never removes."""
        mock_upload.return_value = "file_obj"
        mock_generate_content.return_value.parsed = PdfAiAnnotations(**self.sample_gemini_response)
        mock_pdf = mock_pikepdf_open.return_value.__enter__.return_value

        with patch("builtins.input", side_effect=["y", "n"]):
            process_file(self.dummy_pdf_path, self.output_dir, cautious=True)

        mock_pdf.save.assert_called_once()
        mock_os_remove.assert_not_called()

    @patch("os.remove")
    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_process_file_cautious_confirm_all(
        self,
        mock_generate_content,
        mock_upload,
        mock_pikepdf_open,
        mock_os_remove,
    ):
        """Confirming both prompts calls both save and remove."""
        mock_upload.return_value = "file_obj"
        mock_generate_content.return_value.parsed = PdfAiAnnotations(**self.sample_gemini_response)
        mock_pdf = mock_pikepdf_open.return_value.__enter__.return_value

        with patch("builtins.input", side_effect=["y", "y"]):
            process_file(self.dummy_pdf_path, self.output_dir, cautious=True)

        mock_pdf.save.assert_called_once()
        mock_os_remove.assert_called_once()

    # ── validation / error handling ───────────────────────────────────────────

    @patch("os.remove")
    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_process_file_missing_metadata(
        self,
        mock_generate_content,
        mock_upload,
        mock_pikepdf_open,
        mock_os_remove,
    ):
        """Any missing/invalid metadata field halts before opening or removing files."""
        for invalid_response in self.invalid_gemini_responses:
            mock_upload.return_value = "file_obj"
            mock_generate_content.return_value.parsed = invalid_response

            process_file(self.dummy_pdf_path, self.output_dir)

            mock_os_remove.assert_not_called()
            mock_pikepdf_open.assert_not_called()

    @patch("os.remove")
    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_path_traversal_sanitized(
        self,
        mock_generate_content,
        mock_upload,
        mock_pikepdf_open,
        mock_os_remove,
    ):
        """A filename containing path traversal is reduced to its basename."""
        malicious_response = {
            "summary": "Summary",
            "keywords": "Keywords",
            "title": "Title",
            "filename": "../malicious.pdf",
        }
        mock_upload.return_value = "file_obj"
        mock_generate_content.return_value.parsed = PdfAiAnnotations(**malicious_response)
        mock_pdf = mock_pikepdf_open.return_value.__enter__.return_value

        process_file(self.dummy_pdf_path, self.output_dir)

        expected_path = os.path.join(self.output_dir, "malicious.pdf")
        mock_pdf.save.assert_called_once_with(expected_path)

    @patch("os.remove")
    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_process_file_overwrite_same_file(
        self,
        mock_generate_content,
        mock_upload,
        mock_pikepdf_open,
        mock_os_remove,
    ):
        """When input and output resolve to the same path, deletion is skipped."""
        mock_upload.return_value = "file_obj"

        input_filename = os.path.basename(self.dummy_pdf_path)
        response_data = self.sample_gemini_response.copy()
        response_data["filename"] = input_filename
        mock_generate_content.return_value.parsed = PdfAiAnnotations(**response_data)

        mock_pdf = mock_pikepdf_open.return_value.__enter__.return_value

        # Use the input directory as the output directory so the paths match.
        process_file(self.dummy_pdf_path, self.input_dir)

        mock_pikepdf_open.assert_called_once_with(self.dummy_pdf_path, allow_overwriting_input=True)
        mock_pdf.save.assert_called_once_with(self.dummy_pdf_path)
        mock_os_remove.assert_not_called()

    @patch("pikepdf.open", autospec=True)
    @patch("pdf_ai_annotator.client.files.upload")
    @patch("pdf_ai_annotator.client.models.generate_content")
    def test_process_file_applies_all_metadata_keys(
        self,
        mock_generate_content,
        mock_upload,
        mock_pikepdf_open,
    ):
        """Exactly the three XMP metadata keys are written to the PDF."""
        mock_upload.return_value = "file_obj"
        mock_generate_content.return_value.parsed = PdfAiAnnotations(**self.sample_gemini_response)

        mock_pdf = mock_pikepdf_open.return_value.__enter__.return_value
        mock_meta = mock_pdf.open_metadata.return_value.__enter__.return_value

        with patch("os.remove"):
            process_file(self.dummy_pdf_path, self.output_dir)

        written_keys = {call.args[0] for call in mock_meta.__setitem__.call_args_list}
        self.assertEqual(written_keys, {"dc:title", "dc:description", "dc:subject"})


if __name__ == "__main__":
    unittest.main()
