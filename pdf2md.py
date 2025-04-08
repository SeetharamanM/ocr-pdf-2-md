#!/usr/bin/env python3
"""
PDF to Markdown OCR Converter

A reliable, fast, and simple script to convert scanned PDF pages into Markdown files.
Uses Tesseract OCR engine via pytesseract and handles PDF processing with pdf2image.

Dependencies:
- pytesseract
- pdf2image
- Pillow (PIL)
- tesseract-ocr (system dependency)
- poppler (system dependency)

Usage:
    python pdf_to_markdown.py input.pdf [output_dir]
"""

import os
import sys
import argparse
import re
from pathlib import Path
import pytesseract
from pdf2image import convert_from_path, pdfinfo_from_path
from PIL import Image
import logging
import importlib
import importlib.util

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def setup_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description="Convert scanned PDF files to Markdown.")
    parser.add_argument("pdf_path", help="Path to the PDF file")
    parser.add_argument("--output_dir", default="output_markdown", help="Directory to save Markdown files")
    parser.add_argument("--dpi", type=int, default=300, help="DPI for PDF conversion (higher = better quality but slower)")
    parser.add_argument("--lang", default="eng", help="Tesseract language (default: eng)")
    parser.add_argument("--pages", help="Pages to process (e.g., '1,3-5,10'). Default: all pages")
    parser.add_argument("--timeout", type=int, default=180, help="Timeout for Tesseract OCR in seconds")
    parser.add_argument("--fix-pdf", action="store_true", help="Force PDF repair for problematic files")
    parser.add_argument("--use-ocrmypdf", action="store_true", help="Use OCRmyPDF for enhanced processing")
    return parser.parse_args()

def parse_page_ranges(page_range_str, total_pages):
    """Parse page ranges like '1,3-5,10' into a list of page numbers"""
    if not page_range_str:
        return list(range(1, total_pages + 1))
    
    pages = set()
    for part in page_range_str.split(','):
        if '-' in part:
            start, end = map(int, part.split('-'))
            pages.update(range(start, end + 1))
        else:
            pages.add(int(part))
    
    # Filter out pages beyond total_pages
    return sorted([p for p in pages if 1 <= p <= total_pages])

def pdf_to_images(pdf_path, dpi=300, pages=None):
    """Convert PDF pages to PIL Image objects"""
    try:
        logger.info(f"Converting PDF to images (DPI: {dpi})")
        
        # Handle the leading zeros syntax error in some PDFs
        # Set strict=False to bypass common PDF syntax errors
        try:
            images = convert_from_path(pdf_path, dpi=dpi, fmt='jpg', strict=False)
        except Exception as pdf_err:
            # If there's an error about leading zeros, try with pikepdf to fix it
            if "leading zeros" in str(pdf_err):
                logger.warning(f"Detected PDF with syntax issues (leading zeros). Attempting workaround...")
                try:
                    # Try to install pikepdf if not available
                    try:
                        import pikepdf
                    except ImportError:
                        logger.info("Installing pikepdf for PDF repair...")
                        import subprocess
                        subprocess.check_call([sys.executable, "-m", "pip", "install", "pikepdf"])
                        importlib.invalidate_caches()
                        import pikepdf
                        
                    # Create a temporary fixed PDF
                    temp_pdf_path = pdf_path + ".fixed.pdf"
                    with pikepdf.open(pdf_path) as pdf:
                        pdf.save(temp_pdf_path)
                    
                    # Use the fixed PDF
                    logger.info("Using repaired PDF for conversion")
                    images = convert_from_path(temp_pdf_path, dpi=dpi, fmt='jpg')
                    
                    # Clean up temporary file
                    try:
                        os.remove(temp_pdf_path)
                    except:
                        pass
                        
                except Exception as repair_err:
                    logger.error(f"PDF repair failed: {repair_err}")
                    raise pdf_err  # Re-raise the original error
            else:
                # If it's some other error, try with poppler_path set to None
                # This can help on some systems where poppler is installed but not detected
                logger.warning(f"Standard conversion failed: {pdf_err}. Trying alternative method...")
                images = convert_from_path(pdf_path, dpi=dpi, fmt='jpg', poppler_path=None, use_pdftocairo=True)
        
        if pages:
            # Adjust for 0-based indexing in the images list
            return [images[i-1] for i in pages if i <= len(images)]
        return images
    except Exception as e:
        logger.error(f"Error converting PDF to images: {e}")
        logger.info("Providing diagnostic information for troubleshooting...")
        
        try:
            # Try to get PDF info for diagnostics
            info = pdfinfo_from_path(pdf_path, poppler_path=None)
            logger.info(f"PDF Info: Pages: {info['Pages']}, Version: {info.get('PDF version', 'Unknown')}")
        except:
            logger.warning("Could not get PDF information")
            
        # Check if file exists and get size
        if os.path.exists(pdf_path):
            file_size = os.path.getsize(pdf_path)
            logger.info(f"PDF file exists, size: {file_size} bytes")
        else:
            logger.error(f"PDF file does not exist at path: {pdf_path}")
        
        sys.exit(1)

def clean_text(text):
    """Clean the OCR text and format as Markdown"""
    # Remove excessive newlines (more than 2 in a row)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # Try to detect headings (lines with all caps or short lines followed by a blank line)
    lines = text.split('\n')
    for i in range(len(lines)-1):
        line = lines[i].strip()
        next_line = lines[i+1].strip()
        
        # If line is all uppercase or ends with a colon and next line is empty, make it a heading
        if ((line.isupper() and len(line) > 3) or 
            (line.endswith(':') and len(line) < 50)) and next_line == '':
            lines[i] = f'## {line}'
    
    # Join lines back together
    text = '\n'.join(lines)
    
    # Format bullet points (lines starting with - or * or •)
    text = re.sub(r'^[-*•]\s+', '* ', text, flags=re.MULTILINE)
    
    # Detect and format numbered lists
    text = re.sub(r'^(\d+)[\.\)]\s+', r'\1. ', text, flags=re.MULTILINE)
    
    # Try to identify and mark `code` segments (text that appears to be code)
    text = re.sub(r'(?<!\n)(`[^`]+?`)(?!\n)', r'\1', text)
    
    # Fix common OCR errors
    text = re.sub(r'l\s+\n', 'I ', text)  # OCR often mistakes 'I' for 'l'
    
    return text

def image_to_markdown(image, lang='eng', timeout=180):
    """Convert a PIL Image to Markdown text using Tesseract OCR"""
    try:
        # Preprocess the image to improve OCR quality
        # Convert to grayscale
        gray_image = image.convert('L')
        
        # Apply OCR with custom configuration
        custom_config = f'--oem 3 --psm 6 -l {lang}'
        text = pytesseract.image_to_string(gray_image, config=custom_config, timeout=timeout)
        
        # Clean and format the text
        return clean_text(text)
    except Exception as e:
        logger.error(f"OCR error: {e}")
        return f"ERROR: OCR failed with error: {e}"

def try_fix_pdf(pdf_path):
    """Attempts to fix problematic PDF files"""
    logger.info("Attempting to fix problematic PDF...")
    
    # Check if pikepdf is installed or try to install it
    if importlib.util.find_spec("pikepdf") is None:
        try:
            logger.info("Installing pikepdf for PDF repair...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pikepdf"])
        except Exception as e:
            logger.error(f"Failed to install pikepdf: {e}")
            return None
    
    try:
        import pikepdf
        temp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
        temp_file.close()
        
        # Open and resave the PDF to fix common syntax issues
        with pikepdf.open(pdf_path) as pdf:
            pdf.save(temp_file.name)
        
        logger.info(f"PDF fixed and saved to temporary file: {temp_file.name}")
        return temp_file.name
    except Exception as e:
        logger.error(f"Failed to fix PDF with pikepdf: {e}")
        return None

def try_ocrmypdf_processing(pdf_path, output_path):
    """Uses OCRmyPDF for enhanced processing if available"""
    logger.info("Attempting to use OCRmyPDF for direct PDF to PDF OCR...")
    
    # Check if ocrmypdf is installed or try to install it
    if importlib.util.find_spec("ocrmypdf") is None:
        try:
            logger.info("Installing ocrmypdf...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", "ocrmypdf"])
        except Exception as e:
            logger.error(f"Failed to install ocrmypdf: {e}")
            return False
    
    try:
        import ocrmypdf
        # Process the PDF directly with OCRmyPDF
        ocrmypdf.ocr(pdf_path, output_path, force_ocr=True)
        return True
    except Exception as e:
        logger.error(f"OCRmyPDF processing failed: {e}")
        return False

def pdf_to_markdown_direct(pdf_path, output_dir, base_name, lang="eng"):
    """Attempt to extract text directly from PDF without OCR if possible"""
    try:
        # Check if PyPDF2 is installed or try to install it
        if importlib.util.find_spec("PyPDF2") is None:
            try:
                logger.info("Installing PyPDF2...")
                import subprocess
                subprocess.check_call([sys.executable, "-m", "pip", "install", "PyPDF2"])
            except Exception as e:
                logger.error(f"Failed to install PyPDF2: {e}")
                return False
        
        import PyPDF2
        
        try:
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                
                for i, page in enumerate(reader.pages):
                    try:
                        text = page.extract_text()
                        
                        # If we got meaningful text, clean and save it
                        if text and len(text.strip()) > 100:  # Arbitrary threshold to check if text extraction worked
                            formatted_text = clean_text(text)
                            output_file = os.path.join(output_dir, f"{base_name}_page_{i+1}.md")
                            
                            with open(output_file, 'w', encoding='utf-8') as f:
                                f.write(formatted_text)
                            
                            logger.info(f"Extracted text directly from page {i+1} (no OCR needed)")
                    except Exception as page_error:
                        logger.warning(f"Could not extract text from page {i+1}: {page_error}")
                
                return True
                
        except Exception as e:
            logger.warning(f"Direct text extraction failed: {e}")
            return False
            
    except Exception as e:
        logger.warning(f"PDF direct text extraction setup failed: {e}")
        return False

def main():
    args = setup_args()
    pdf_path = args.pdf_path
    output_dir = args.output_dir
    original_pdf_path = pdf_path
    temp_pdf_path = None
    
    # Check if file exists
    if not os.path.isfile(pdf_path):
        logger.error(f"File not found: {pdf_path}")
        sys.exit(1)
    
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Processing PDF: {pdf_path}")
    
    # Fix PDF if requested or try OCRmyPDF for enhanced processing
    if args.fix_pdf:
        fixed_path = try_fix_pdf(pdf_path)
        if fixed_path:
            temp_pdf_path = fixed_path
            pdf_path = fixed_path
            logger.info(f"Using fixed PDF: {pdf_path}")
    
    # Try OCRmyPDF if requested (direct PDF to searchable PDF conversion)
    if args.use_ocrmypdf:
        ocr_pdf_path = os.path.join(output_dir, os.path.basename(original_pdf_path).replace('.pdf', '_ocr.pdf'))
        if try_ocrmypdf_processing(pdf_path, ocr_pdf_path):
            logger.info(f"Successfully created searchable PDF with OCRmyPDF: {ocr_pdf_path}")
            pdf_path = ocr_pdf_path
    
    # Get base filename without extension
    base_name = os.path.splitext(os.path.basename(original_pdf_path))[0]
    
    # Try direct text extraction first (might work for some PDFs without OCR)
    direct_extraction = pdf_to_markdown_direct(pdf_path, output_dir, base_name)
    
    if direct_extraction:
        logger.info("Successfully extracted text directly from PDF without OCR")
    else:
        # Convert PDF to images
        try:
            images = pdf_to_images(pdf_path, dpi=args.dpi)
            total_pages = len(images)
            logger.info(f"Total pages detected: {total_pages}")
            
            # Parse page ranges if specified
            pages_to_process = parse_page_ranges(args.pages, total_pages)
            
            # Process each page
            for page_num in pages_to_process:
                if page_num > total_pages:
                    logger.warning(f"Page {page_num} exceeds total pages ({total_pages}). Skipping.")
                    continue
                    
                image = images[page_num-1]  # Adjust for 0-based indexing
                
                logger.info(f"Processing page {page_num}/{total_pages}")
                
                # Perform OCR and convert to Markdown
                markdown_text = image_to_markdown(image, lang=args.lang, timeout=args.timeout)
                
                # Write to output file
                output_file = os.path.join(output_dir, f"{base_name}_page_{page_num}.md")
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(markdown_text)
                
                logger.info(f"Saved Markdown to: {output_file}")
            
            logger.info(f"OCR conversion complete. Processed {len(pages_to_process)} page(s).")
        except Exception as e:
            logger.error(f"Error during image conversion and OCR: {e}")
            sys.exit(1)
    
    # Clean up temporary files
    if temp_pdf_path and os.path.exists(temp_pdf_path):
        try:
            os.remove(temp_pdf_path)
            logger.info(f"Removed temporary file: {temp_pdf_path}")
        except Exception as e:
            logger.warning(f"Could not remove temporary file {temp_pdf_path}: {e}")

if __name__ == "__main__":
    main()