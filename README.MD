# Installation Guide for PDF to Markdown OCR Converter

## Prerequisites

Before using the script, you need to install both Python dependencies and system dependencies:

### System Dependencies

#### On Ubuntu/Debian:
```bash
sudo apt-get update
sudo apt-get install -y tesseract-ocr poppler-utils
```

#### On macOS:
```bash
brew install tesseract poppler
```

#### On Windows:
1. Install Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install Poppler for Windows: https://github.com/oschwartz10612/poppler-windows/releases/
3. Add both to your PATH environment variable

### Python Dependencies

Install the required Python packages:

```bash
pip install pytesseract pdf2image Pillow
```

## Verifying Installation

To verify that Tesseract is properly installed and accessible:

```bash
tesseract --version
```

## Usage

Basic usage:
```bash
python pdf2md.py input.pdf
```

Advanced usage:
```bash
python pdf2md.py input.pdf --output_dir my_markdown_files --dpi 400 --lang eng+fra --pages 1,3-5
```

### Command Line Arguments

- `pdf_path`: Path to the PDF file (required)
- `--output_dir`: Directory to save Markdown files (default: "output_markdown")
- `--dpi`: DPI for PDF conversion (higher = better quality but slower) (default: 300)
- `--lang`: Tesseract language code(s) (default: eng)
- `--pages`: Pages to process (e.g., '1,3-5,10'). Default: all pages
- `--timeout`: Timeout for Tesseract OCR in seconds (default: 180)
- `--single-file`: Combine all pages into one Markdown file (`<name>.md`) instead of one file per page

### Language Support

For languages other than English, you need to install the corresponding Tesseract language packs:

#### On Ubuntu/Debian:
```bash
# For French
sudo apt-get install tesseract-ocr-fra
# For German
sudo apt-get install tesseract-ocr-deu
```

To use multiple languages together:
```bash
python pdf2md.py input.pdf --lang eng+fra
```

## Troubleshooting

1. **PDF reading errors**: Make sure Poppler is correctly installed and accessible in your PATH
2. **OCR quality issues**: Try increasing the DPI (e.g., --dpi 400)
3. **Memory issues with large files**: Process the PDF one page at a time using the --pages argument
4. **Tesseract not found**: Ensure Tesseract is installed and in your PATH environment variable

## Performance Tips

- For faster processing with slightly lower quality, reduce the DPI (e.g., --dpi 200)
- For better text recognition but slower processing, increase the DPI (e.g., --dpi 400)
- Process only specific pages when working with large documents