"""
Configuration settings for GDrive ViewOnly Saver.
"""

import os

# ═══════════════════════════════════════════════════════════════
#  OUTPUT SETTINGS
# ═══════════════════════════════════════════════════════════════

# Default output directory for downloaded files
OUTPUT_DIR = "/tmp/downloads"

# Image quality settings
IMAGE_QUALITY = 95          # JPEG quality (1-100), higher = better quality, larger file
IMAGE_DPI = 300             # DPI for the output PDF
IMAGE_FORMAT = "PNG"        # PNG (lossless) or JPEG (lossy but smaller)

# ═══════════════════════════════════════════════════════════════
#  BROWSER SETTINGS
# ═══════════════════════════════════════════════════════════════

# Browser window size - larger = higher resolution captures
BROWSER_WIDTH = 1920
BROWSER_HEIGHT = 1080

# Device scale factor (pixel ratio) - 2 means 2x resolution
# Higher values produce sharper images but use more memory
DEVICE_SCALE_FACTOR = 2.0

# Headless mode: True = no visible browser, False = show browser window
HEADLESS = True

# ═══════════════════════════════════════════════════════════════
#  TIMING SETTINGS (in seconds)
# ═══════════════════════════════════════════════════════════════

# Time to wait for initial page load
PAGE_LOAD_WAIT = 4

# Time to wait between scrolls for pages to render
SCROLL_WAIT = 0.5

# Time to wait after all scrolling is done before capturing
FINAL_WAIT = 1.5

# Maximum time to wait for any single element
ELEMENT_TIMEOUT = 10

# ═══════════════════════════════════════════════════════════════
#  ADVANCED SETTINGS
# ═══════════════════════════════════════════════════════════════

# Maximum number of retry attempts for failed page captures
MAX_RETRIES = 3

# Chrome user data directory (leave empty to use a temporary profile)
# Set this to your Chrome profile path if you need to access files
# that require Google account authentication
# Example: "C:\\Users\\YourName\\AppData\\Local\\Google\\Chrome\\User Data"
CHROME_USER_DATA_DIR = ""

# Chrome profile name (only used if CHROME_USER_DATA_DIR is set)
CHROME_PROFILE = "Default"

# Temp directory for intermediate files
TEMP_DIR = "/tmp/.temp"
