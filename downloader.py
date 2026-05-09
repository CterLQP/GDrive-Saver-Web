"""
Core downloader module — orchestrates the entire download process.
"""

import os
import time
from typing import Optional

import config
from utils import (
    extract_file_id, 
    build_view_url, 
    sanitize_filename,
    ensure_dir,
    cleanup_dir,
    is_folder_url,
    log_info, 
    log_success, 
    log_warning, 
    log_error,
    log_step,
    format_size
)
from browser_handler import BrowserHandler
from pdf_builder import PDFBuilder


class GDriveDownloader:
    """
    Main downloader class that orchestrates the process of
    downloading view-only Google Drive files.
    """
    
    def __init__(self):
        self.browser = BrowserHandler()
        self.pdf_builder = PDFBuilder()
    
    def download(
        self, 
        url: str, 
        output_dir: str = None,
        output_format: str = "pdf",
        filename: str = None
    ) -> Optional[str]:
        """
        Download a view-only Google Drive file.
        
        Args:
            url: Google Drive file URL or file ID
            output_dir: Directory to save the output (default from config)
            output_format: Output format - "pdf", "images", or "both"
            filename: Custom filename (auto-detected if not provided)
        
        Returns:
            Path to the downloaded file, or None on failure
        """
        output_dir = output_dir or config.OUTPUT_DIR
        ensure_dir(output_dir)
        
        # Check if it's a folder URL
        if is_folder_url(url):
            return self.download_folder(url, output_dir, output_format)
            
        total_steps = 5
        result = None
        
        try:
            # ─── Step 1: Parse URL ────────────────────────────────
            log_step(1, total_steps, "Parsing Google Drive URL...")
            file_id = extract_file_id(url)
            view_url = build_view_url(file_id)
            log_success(f"File ID: {file_id}")
            
            # ─── Step 2: Open in browser ──────────────────────────
            log_step(2, total_steps, "Opening file in browser...")
            self.browser.start()
            
            if not self.browser.open_file(view_url):
                log_error(
                    "Could not access the file. Possible reasons:\n"
                    "  • The file doesn't exist or was deleted\n"
                    "  • You need to be signed in to view this file\n"
                    "  • The file requires specific permission\n"
                    "\n"
                    "  Tip: Set CHROME_USER_DATA_DIR in config.py to use\n"
                    "  your existing Chrome login session."
                )
                return None
            
            # Get file title
            if not filename:
                title = self.browser.get_file_title()
                filename = sanitize_filename(title)
                log_info(f"File title: {title}")
            
            # ─── Step 3: Load all pages ───────────────────────────
            log_step(3, total_steps, "Loading all pages...")
            initial_pages = self.browser.get_total_pages()
            
            if initial_pages > 0:
                log_info(f"Detected {initial_pages} pages")
            
            total_pages = self.browser.scroll_through_all_pages(initial_pages)
            log_success(f"Total pages loaded: {total_pages}")
            
            # ─── Step 4: Extract page images ─────────────────────
            log_step(4, total_steps, "Extracting page images (high quality)...")
            images = self.browser.capture_page_images(total_pages)
            
            if not images:
                log_error(
                    "Failed to extract any page images.\n"
                    "  This might happen if:\n"
                    "  • The file uses a viewer format we don't support yet\n"
                    "  • Google Drive changed their viewer structure\n"
                    "  • The file requires authentication"
                )
                return None
            
            log_success(f"Extracted {len(images)} page images")
            
            # ─── Step 5: Build output ─────────────────────────────
            log_step(5, total_steps, "Building output file...")
            
            if output_format in ("pdf", "both"):
                # Avoid double extensions (e.g., "file.pdf.pdf")
                base_name = filename
                if base_name.lower().endswith('.pdf'):
                    base_name = base_name[:-4]
                pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
                result = self.pdf_builder.build_pdf(images, pdf_path)
            
            if output_format in ("images", "both"):
                img_dir = os.path.join(output_dir, filename)
                saved = self.pdf_builder.save_individual_images(
                    images, img_dir, prefix=filename
                )
                if saved and not result:
                    result = img_dir
            
            if result:
                print()
                log_success("═" * 50)
                log_success(f"Download complete!")
                log_success(f"Saved to: {result}")
                log_success("═" * 50)
            
            return result
            
        except KeyboardInterrupt:
            log_warning("\nDownload cancelled by user")
            return None
        except Exception as e:
            log_error(f"Download failed: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            self.browser.close()
            
    def download_folder(
        self,
        url: str,
        output_dir: str = None,
        output_format: str = "pdf"
    ) -> Optional[list]:
        """
        Extract files from a Google Drive folder and download them.
        """
        output_dir = output_dir or config.OUTPUT_DIR
        ensure_dir(output_dir)
        
        log_info(f"Folder URL detected: {url}")
        log_info("Extracting file links from folder...")
        
        try:
            self.browser.start()
            files_data = self.browser.get_folder_file_ids(url)
            
            if not files_data:
                log_error(
                    "Could not find any files in this folder.\n"
                    "  Possible reasons:\n"
                    "  • The folder is empty\n"
                    "  • The folder requires authentication (use --profile)\n"
                    "  • The URL is invalid"
                )
                return None
            
            log_success(f"Found {len(files_data)} files in folder:")
            for fid, title in files_data:
                log_info(f"  • {title} ({fid})")
                
            # Build URLs for batch download
            urls = [build_view_url(fid) for fid, _ in files_data]
            
        except Exception as e:
            log_error(f"Failed to process folder: {e}")
            return None
        finally:
            self.browser.close()
            
        print()
        log_info(f"Starting batch download for {len(urls)} files...")
        return self.batch_download(urls, output_dir, output_format)
    
    def batch_download(
        self,
        urls: list,
        output_dir: str = None,
        output_format: str = "pdf"
    ) -> list:
        """
        Download multiple files.
        
        Args:
            urls: List of Google Drive URLs
            output_dir: Output directory
            output_format: Output format
        
        Returns:
            List of (url, result_path_or_none) tuples
        """
        results = []
        total = len(urls)
        
        for i, url in enumerate(urls, 1):
            print()
            log_info(f"{'═' * 50}")
            log_info(f"Processing file {i}/{total}")
            log_info(f"URL: {url}")
            log_info(f"{'═' * 50}")
            
            result = self.download(url, output_dir, output_format)
            results.append((url, result))
            
            # Small delay between downloads to avoid rate limiting
            if i < total:
                time.sleep(2)
        
        # Print summary
        print()
        log_info("═" * 50)
        log_info("BATCH DOWNLOAD SUMMARY")
        log_info("═" * 50)
        
        success_count = sum(1 for _, r in results if r)
        fail_count = total - success_count
        
        for url, result in results:
            if result:
                log_success(f"✓ {url} → {os.path.basename(result)}")
            else:
                log_error(f"✗ {url}")
        
        print()
        log_info(f"Results: {success_count} succeeded, {fail_count} failed")
        
        return results
