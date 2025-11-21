"""
Docling-based PDF extraction to Markdown
"""

from docling.document_converter import DocumentConverter
from pathlib import Path


def extract_pdf_to_markdown(pdf_path):
    """
    Extract PDF content to markdown using Docling

    Args:
        pdf_path: Path to the PDF file (str or Path object)

    Returns:
        str: Extracted content in markdown format
    """
    try:
        # Initialize the document converter
        converter = DocumentConverter()

        # Convert the PDF
        result = converter.convert(pdf_path)

        # Export to markdown
        markdown_content = result.document.export_to_markdown()

        return markdown_content

    except Exception as e:
        return f"Error extracting PDF with Docling: {str(e)}"


def extract_pdf_with_options(pdf_path, options=None):
    """
    Extract PDF with custom docling options

    Args:
        pdf_path: Path to the PDF file
        options: Dict of docling conversion options (optional)

    Returns:
        str: Extracted content in markdown format
    """
    try:
        # Initialize converter with options if provided
        if options:
            converter = DocumentConverter(**options)
        else:
            converter = DocumentConverter()

        # Convert the PDF
        result = converter.convert(pdf_path)

        # Export to markdown
        markdown_content = result.document.export_to_markdown()

        return markdown_content

    except Exception as e:
        return f"Error extracting PDF with Docling: {str(e)}"


if __name__ == "__main__":
    # Test the extractor
    import sys

    if len(sys.argv) > 1:
        pdf_file = sys.argv[1]
        print("Extracting PDF with Docling...")
        content = extract_pdf_to_markdown(pdf_file)
        print(content)
    else:
        print("Usage: python docling_extractor.py <pdf_file>")
