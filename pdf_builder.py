"""
PDF Builder module — assembles extracted page images into a high-quality PDF.
Supports both lossless (img2pdf) and Pillow-based assembly methods.
"""

import os
import io
from typing import List, Optional

from PIL import Image

import config
from utils import log_info, log_success, log_warning, log_error, log_progress, format_size


class PDFBuilder:
    """Assembles page images into a high-quality PDF document."""
    
    @staticmethod
    def build_pdf(
        images: List[bytes],
        output_path: str,
        dpi: int = None,
        quality: int = None
    ) -> Optional[str]:
        """
        Build a PDF from a list of page images (as bytes).
        
        Args:
            images: List of image data in bytes (PNG or JPEG)
            output_path: Full path for the output PDF file
            dpi: Resolution in dots per inch (default from config)
            quality: JPEG quality 1-100 (default from config)
        
        Returns:
            Path to the created PDF file, or None on failure
        """
        if not images:
            log_error("No images provided to build PDF")
            return None
        
        dpi = dpi or config.IMAGE_DPI
        quality = quality or config.IMAGE_QUALITY
        
        log_info(f"Building PDF from {len(images)} pages...")
        log_info(f"Output: {output_path}")
        log_info(f"Settings: DPI={dpi}, Quality={quality}")
        
        # Try img2pdf first (lossless, fastest)
        result = PDFBuilder._build_with_img2pdf(images, output_path)
        if result:
            return result
        
        # Fallback: Use Pillow
        log_info("Falling back to Pillow-based PDF assembly...")
        return PDFBuilder._build_with_pillow(images, output_path, dpi, quality)
    
    @staticmethod
    def _build_with_img2pdf(images: List[bytes], output_path: str) -> Optional[str]:
        """
        Build PDF using img2pdf (lossless — no re-encoding).
        This produces the highest quality output as it embeds images directly.
        """
        try:
            import img2pdf
            
            # Convert any non-JPEG/PNG images to PNG first
            processed_images = []
            for i, img_data in enumerate(images):
                try:
                    # Validate the image
                    img = Image.open(io.BytesIO(img_data))
                    
                    # img2pdf works best with JPEG and PNG
                    if img.format not in ('JPEG', 'PNG'):
                        # Convert to PNG
                        buf = io.BytesIO()
                        img.save(buf, format='PNG')
                        processed_images.append(buf.getvalue())
                    else:
                        processed_images.append(img_data)
                    
                    log_progress(i + 1, len(images), "  Processing:")
                    
                except Exception as e:
                    log_warning(f"Skipping invalid image {i + 1}: {e}")
            
            if not processed_images:
                return None
            
            # Build PDF with img2pdf
            # Use A4-like layout that adapts to image aspect ratio
            pdf_bytes = img2pdf.convert(processed_images)
            
            with open(output_path, 'wb') as f:
                f.write(pdf_bytes)
            
            file_size = os.path.getsize(output_path)
            log_success(f"PDF created successfully! Size: {format_size(file_size)}")
            return output_path
            
        except ImportError:
            log_warning("img2pdf not available, using alternative method")
            return None
        except Exception as e:
            log_warning(f"img2pdf failed: {e}")
            return None
    
    @staticmethod
    def _build_with_pillow(
        images: List[bytes],
        output_path: str,
        dpi: int,
        quality: int
    ) -> Optional[str]:
        """
        Build PDF using Pillow.
        Slightly lower quality than img2pdf but more compatible.
        """
        try:
            pil_images = []
            
            for i, img_data in enumerate(images):
                try:
                    img = Image.open(io.BytesIO(img_data))
                    
                    # Convert to RGB if necessary (PDF doesn't support RGBA)
                    if img.mode == 'RGBA':
                        # Create white background
                        bg = Image.new('RGB', img.size, (255, 255, 255))
                        bg.paste(img, mask=img.split()[3])
                        img = bg
                    elif img.mode != 'RGB':
                        img = img.convert('RGB')
                    
                    pil_images.append(img)
                    log_progress(i + 1, len(images), "  Processing:")
                    
                except Exception as e:
                    log_warning(f"Skipping invalid image {i + 1}: {e}")
            
            if not pil_images:
                log_error("No valid images to create PDF")
                return None
            
            # Save as PDF
            first_img = pil_images[0]
            remaining = pil_images[1:] if len(pil_images) > 1 else []
            
            save_kwargs = {
                "format": "PDF",
                "resolution": float(dpi),
                "save_all": True,
                "append_images": remaining,
                "quality": quality,
            }
            
            first_img.save(output_path, **save_kwargs)
            
            file_size = os.path.getsize(output_path)
            log_success(f"PDF created successfully! Size: {format_size(file_size)}")
            return output_path
            
        except Exception as e:
            log_error(f"Pillow PDF creation failed: {e}")
            return None
    
    @staticmethod
    def save_individual_images(
        images: List[bytes],
        output_dir: str,
        prefix: str = "page",
        fmt: str = None
    ) -> List[str]:
        """
        Save each page image as an individual file.
        
        Args:
            images: List of image data in bytes
            output_dir: Directory to save images in
            prefix: Filename prefix
            fmt: Image format (PNG or JPEG)
        
        Returns:
            List of saved file paths
        """
        fmt = fmt or config.IMAGE_FORMAT
        ext = "png" if fmt.upper() == "PNG" else "jpg"
        
        os.makedirs(output_dir, exist_ok=True)
        saved_paths = []
        
        for i, img_data in enumerate(images):
            try:
                img = Image.open(io.BytesIO(img_data))
                
                # Convert RGBA to RGB for JPEG
                if fmt.upper() == "JPEG" and img.mode == 'RGBA':
                    bg = Image.new('RGB', img.size, (255, 255, 255))
                    bg.paste(img, mask=img.split()[3])
                    img = bg
                elif img.mode != 'RGB' and fmt.upper() == "JPEG":
                    img = img.convert('RGB')
                
                filename = f"{prefix}_{i + 1:03d}.{ext}"
                filepath = os.path.join(output_dir, filename)
                
                save_kwargs = {}
                if fmt.upper() == "JPEG":
                    save_kwargs["quality"] = config.IMAGE_QUALITY
                    save_kwargs["optimize"] = True
                
                img.save(filepath, format=fmt.upper(), **save_kwargs)
                saved_paths.append(filepath)
                
                log_progress(i + 1, len(images), "  Saving:")
                
            except Exception as e:
                log_warning(f"Failed to save image {i + 1}: {e}")
        
        if saved_paths:
            total_size = sum(os.path.getsize(p) for p in saved_paths)
            log_success(f"Saved {len(saved_paths)} images ({format_size(total_size)})")
        
        return saved_paths
