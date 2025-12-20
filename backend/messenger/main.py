from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from playwright.async_api import async_playwright
from contextlib import asynccontextmanager
import asyncio
import os
import urllib.parse

import uvicorn

# Global browser and page instances
browser = None
page = None
playwright_instance = None


async def init_whatsapp():
    """Initialize WhatsApp Web browser session"""
    global browser, page, playwright_instance
    
    playwright_instance = await async_playwright().start()
    
    # Launch browser with user data directory to persist session
    user_data_dir = os.path.join(os.getcwd(), "whatsapp_session")
    
    browser = await playwright_instance.chromium.launch_persistent_context(
        user_data_dir=user_data_dir,
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
    )
    
    page = await browser.new_page()
    
    # Set a realistic user agent
    await page.set_extra_http_headers({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    await page.goto("https://web.whatsapp.com", wait_until="load", timeout=60000)
    await asyncio.sleep(5)
    
    print("✅ WhatsApp Web initialized. Open /qr to scan QR code.")


async def close_whatsapp():
    """Close browser session"""
    global browser, playwright_instance
    if browser:
        await browser.close()
    if playwright_instance:
        await playwright_instance.stop()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    await init_whatsapp()
    yield
    await close_whatsapp()


app = FastAPI(
    title="WhatsApp Web API",
    description="Send WhatsApp messages via API using WhatsApp Web",
    version="1.0.0",
    lifespan=lifespan
)


class MessageRequest(BaseModel):
    phone_no: str
    message: str
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone_no": "919876543210",
                "message": "Hello from WhatsApp API!"
            }
        }


@app.get("/")
async def root():
    """API Health Check"""
    return {"status": "running", "message": "WhatsApp API is running. Open /qr to scan QR code."}


@app.get("/qr", response_class=HTMLResponse)
async def get_qr_page():
    """
    QR Code Scanner Page - Open this in browser to scan WhatsApp QR code
    """
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>WhatsApp QR Code</title>
        <style>
            body {
                display: flex;
                flex-direction: column;
                align-items: center;
                justify-content: center;
                min-height: 100vh;
                margin: 0;
                background: #111b21;
                color: white;
                font-family: Arial, sans-serif;
            }
            h1 { color: #25D366; }
            .qr-container {
                background: white;
                padding: 20px;
                border-radius: 10px;
                margin: 20px;
            }
            img { 
                max-width: 280px;
                display: block;
            }
            p { color: #aaa; margin: 10px 0; }
            #status {
                padding: 10px 20px;
                border-radius: 5px;
                font-weight: bold;
            }
            .logged-in { background: #25D366; color: white; }
            .waiting { background: #f0ad4e; color: black; }
        </style>
    </head>
    <body>
        <h1>📱 WhatsApp Web Login</h1>
        <p>Open WhatsApp → Settings → Linked Devices → Link a Device</p>
        <div class="qr-container">
            <img id="qr" src="/qr-image" alt="QR Code">
        </div>
        <p id="status" class="waiting">Checking status...</p>
        <script>
            setInterval(() => {
                document.getElementById('qr').src = '/qr-image?' + Date.now();
            }, 3000);
            
            setInterval(async () => {
                try {
                    const res = await fetch('/status');
                    const data = await res.json();
                    const el = document.getElementById('status');
                    el.textContent = data.message;
                    el.className = data.status === 'logged_in' ? 'logged-in' : 'waiting';
                } catch(e) {}
            }, 2000);
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/qr-image")
async def get_qr_image():
    """Returns the QR code image"""
    global page
    
    if not page:
        raise HTTPException(status_code=500, detail="Browser not initialized")
    
    try:
        await asyncio.sleep(0.5)
        
        qr_selectors = ['canvas', '[data-testid="qrcode"]', 'div[data-ref] canvas']
        
        for selector in qr_selectors:
            try:
                qr_element = await page.wait_for_selector(selector, timeout=3000)
                if qr_element:
                    qr_path = os.path.join(os.getcwd(), "qr_code.png")
                    await qr_element.screenshot(path=qr_path, type="png")
                    return FileResponse(qr_path, media_type="image/png")
            except:
                continue
        
        # Return full page screenshot if no QR found
        screenshot_path = os.path.join(os.getcwd(), "page_screenshot.png")
        await page.screenshot(path=screenshot_path, full_page=True)
        return FileResponse(screenshot_path, media_type="image/png")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status")
async def check_status():
    """Check WhatsApp Web login status"""
    global page
    
    if not page:
        raise HTTPException(status_code=500, detail="Browser not initialized")
    
    try:
        logged_in_selectors = ['#side', '[data-testid="chat-list"]', '[data-testid="default-user"]']
        
        for selector in logged_in_selectors:
            try:
                element = await page.wait_for_selector(selector, timeout=2000)
                if element:
                    return {"status": "logged_in", "message": "✅ WhatsApp Web is ready!"}
            except:
                continue
        
        qr_selectors = ['canvas', '[data-testid="qrcode"]']
        for selector in qr_selectors:
            try:
                qr = await page.wait_for_selector(selector, timeout=2000)
                if qr:
                    return {"status": "waiting_for_qr", "message": "⏳ Please scan QR code"}
            except:
                continue
        
        return {"status": "loading", "message": "⏳ Loading WhatsApp Web..."}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/send-message")
async def send_whatsapp_message(request: MessageRequest):
    """
    Send WhatsApp message to a phone number.
    
    - **phone_no**: Phone number with country code (e.g., "919876543210" for India)
    - **message**: Message text to send
    """
    global page
    
    if not page:
        raise HTTPException(status_code=500, detail="Browser not initialized")
    
    phone = request.phone_no.lstrip("+")
    message = request.message
    encoded_message = urllib.parse.quote(message)
    
    try:
        url = f"https://web.whatsapp.com/send?phone={phone}&text={encoded_message}"
        await page.goto(url, wait_until="load", timeout=60000)
        await asyncio.sleep(8)
        
        # Check for invalid phone popup
        try:
            invalid_popup = await page.query_selector('div[data-testid="popup-contents"]')
            if invalid_popup:
                popup_text = await invalid_popup.inner_text()
                if "invalid" in popup_text.lower() or "not on whatsapp" in popup_text.lower():
                    raise HTTPException(status_code=400, detail=f"Phone number not on WhatsApp: {phone}")
        except HTTPException:
            raise
        except:
            pass
        
        # Find message input
        input_selectors = [
            '[data-testid="conversation-compose-box-input"]',
            'div[contenteditable="true"][data-tab="10"]',
            'footer div[contenteditable="true"]',
            '#main footer div[contenteditable="true"]',
            'div[role="textbox"]'
        ]
        
        input_box = None
        for selector in input_selectors:
            try:
                input_box = await page.wait_for_selector(selector, timeout=10000)
                if input_box:
                    break
            except:
                continue
        
        if not input_box:
            await page.screenshot(path="error_screenshot.png")
            raise HTTPException(status_code=500, detail="Could not find message input")
        
        await input_box.click()
        await asyncio.sleep(1)
        
        # Find and click send button
        send_selectors = ['[data-testid="send"]', 'span[data-icon="send"]', '[aria-label="Send"]']
        
        send_button = None
        for selector in send_selectors:
            try:
                send_button = await page.wait_for_selector(selector, timeout=5000)
                if send_button:
                    break
            except:
                continue
        
        if send_button:
            await send_button.click()
        else:
            await page.keyboard.press("Enter")
        
        await asyncio.sleep(2)
        
        return {"status": "success", "message": f"Message sent to {phone}"}
        
    except HTTPException:
        raise
    except Exception as e:
        try:
            await page.screenshot(path="error_screenshot.png")
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8003))
    uvicorn.run(app, host="0.0.0.0", port=port)
