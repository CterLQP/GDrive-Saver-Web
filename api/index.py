import os
import sys
import shutil
import uuid
import threading
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

# Global dictionary to hold task status
# In a real production app, use Redis/Celery. For a single-instance container, memory is fine.
tasks = {}

def process_download(task_id: str, url: str):
    try:
        tasks[task_id] = {"status": "processing", "message": "Khởi động Chrome (10%)...", "progress": 10}
        
        is_folder = is_folder_url(url)
        browser = BrowserHandler()
        builder = PDFBuilder()
        
        output_dir = "/tmp/downloads"
        config.TEMP_DIR = "/tmp/.temp"
        os.makedirs(output_dir, exist_ok=True)
        os.makedirs(config.TEMP_DIR, exist_ok=True)
        
        browser.start()
        
        if is_folder:
            tasks[task_id] = {"status": "processing", "message": "Đang quét thư mục (20%)...", "progress": 20}
            files_data = browser.get_folder_file_ids(url)
            if not files_data:
                browser.close()
                tasks[task_id] = {"status": "error", "message": "Không tìm thấy file trong thư mục hoặc thư mục bị khoá."}
                return
            
            # For web API demo, process the first file
            fid, title = files_data[0]
            view_url = f"https://drive.google.com/file/d/{fid}/view"
        else:
            tasks[task_id] = {"status": "processing", "message": "Đang lấy ID tài liệu (20%)...", "progress": 20}
            file_id = extract_file_id(url)
            view_url = f"https://drive.google.com/file/d/{file_id}/view"
            title = None
            
        tasks[task_id] = {"status": "processing", "message": "Đang mở tài liệu (30%)...", "progress": 30}
        if not browser.open_file(view_url):
            browser.close()
            tasks[task_id] = {"status": "error", "message": "Không thể truy cập tài liệu. Có thể file yêu cầu đăng nhập."}
            return
            
        if not title:
            title = browser.get_file_title()
            
        tasks[task_id] = {"status": "processing", "message": "Đang cuộn tải trang (50%) - Bước này tốn nhiều thời gian...", "progress": 50}
        total_pages = browser.get_total_pages()
        browser.scroll_through_all_pages(total_pages)
        
        tasks[task_id] = {"status": "processing", "message": "Đang trích xuất hình ảnh chất lượng cao (80%)...", "progress": 80}
        images = browser.capture_page_images(total_pages)
        
        browser.close()
        
        if not images:
            tasks[task_id] = {"status": "error", "message": "Lỗi: Không thể lấy được hình ảnh nào từ tài liệu."}
            return
            
        tasks[task_id] = {"status": "processing", "message": "Đang đóng gói file PDF (90%)...", "progress": 90}
        safe_title = sanitize_filename(title)
        pdf_path = os.path.join(output_dir, f"{safe_title}.pdf")
        
        if builder.build_pdf(images, pdf_path):
            tasks[task_id] = {"status": "success", "file_path": pdf_path, "progress": 100, "message": "Hoàn tất!"}
        else:
            tasks[task_id] = {"status": "error", "message": "Lỗi trong quá trình tạo file PDF."}
            
    except Exception as e:
        tasks[task_id] = {"status": "error", "message": str(e)}

@app.post("/api/download")
def start_download(request: DownloadRequest):
    url = request.url
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    task_id = str(uuid.uuid4())
    tasks[task_id] = {"status": "starting", "message": "Đang xếp hàng...", "progress": 0}
    
    # Start background thread
    thread = threading.Thread(target=process_download, args=(task_id, url))
    thread.daemon = True
    thread.start()
    
    return {"task_id": task_id}

@app.get("/api/status/{task_id}")
def check_status(task_id: str):
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]

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
