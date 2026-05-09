import os
import sys
import shutil
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add root project dir to path so we can import modules
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from utils import extract_file_id, is_folder_url, sanitize_filename
from browser_handler import BrowserHandler
from pdf_builder import PDFBuilder
import config

app = FastAPI()

class DownloadRequest(BaseModel):
    url: str

@app.post("/api/download")
def download_api(request: DownloadRequest):
    url = request.url
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
        
    try:
        # Note: Running Chrome via Selenium on Vercel Serverless is generally not supported out-of-the-box
        # because of the size limitations of Chromium. This code is provided as requested but expects
        # a proper host environment (like Render, Railway, or VPS) to function correctly.
        
        is_folder = is_folder_url(url)
        
        browser = BrowserHandler()
        builder = PDFBuilder()
        
        # Vercel only allows writing to /tmp
        output_dir = "/tmp/downloads"
        config.TEMP_DIR = "/tmp/.temp"
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(config.TEMP_DIR, exist_ok=True)
        
        browser.start()
        
        if is_folder:
            files_data = browser.get_folder_file_ids(url)
            if not files_data:
                browser.close()
                raise HTTPException(status_code=400, detail="Could not find files in folder or folder is private.")
            
            # For web API, we might just process the first file as a demo
            # Processing multiple files in a single HTTP request will cause timeouts.
            fid, title = files_data[0]
            view_url = f"https://drive.google.com/file/d/{fid}/view"
            
        else:
            file_id = extract_file_id(url)
            view_url = f"https://drive.google.com/file/d/{file_id}/view"
            title = None
            
        if not browser.open_file(view_url):
            browser.close()
            raise HTTPException(status_code=400, detail="Could not access the file. It might be private.")
            
        if not title:
            title = browser.get_file_title()
            
        total_pages = browser.get_total_pages()
        browser.scroll_through_all_pages(total_pages)
        images = browser.capture_page_images(total_pages)
        
        browser.close()
        
        if not images:
            raise HTTPException(status_code=500, detail="Failed to extract images from the document.")
            
        safe_title = sanitize_filename(title)
        pdf_path = os.path.join(output_dir, f"{safe_title}.pdf")
        
        if builder.build_pdf(images, pdf_path):
            return {"status": "success", "file_path": pdf_path}
        else:
            raise HTTPException(status_code=500, detail="Failed to build PDF file.")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/file")
def get_file(path: str):
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="File not found")
    filename = os.path.basename(path)
    return FileResponse(path, media_type='application/pdf', filename=filename)

# Mount the static frontend
public_dir = os.path.join(ROOT_DIR, "public")
if os.path.exists(public_dir):
    app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")
