from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from flight_scraper import FlightURLBuilder
import uvicorn
import os

app = FastAPI(title="Flight Price Scraper API")

class FlightRequest(BaseModel):
    departure: str
    destination: str
    departure_date: str

    def validate_date_format(self):
        try:
            datetime.strptime(self.departure_date, '%Y-%m-%d')
            return True
        except ValueError:
            return False
    
    def validate_airport_code(self, code: str) -> bool:
        return len(code) == 3 and code.isalpha()

async def setup_browser():
    p = await async_playwright().start()
    # Configure browser with specific arguments for Render
    browser = await p.chromium.launch(
        headless=True,
        args=[
            '--disable-dev-shm-usage',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-gpu',
            '--no-zygote',
            '--single-process',
            '--disable-software-rasterizer'
        ]
    )
    page = await browser.new_page()
    return p, browser, page

async def scrape_flight_info(flight):
    """Extract all relevant information from a single flight element."""
    async def extract_text(selector, aria_label=None):
        try:
            if aria_label:
                element = await flight.query_selector(f'{selector}[aria-label*="{aria_label}"]')
            else:
                element = await flight.query_selector(selector)
            return await element.inner_text() if element else "N/A"
        except Exception:
            return "N/A"

    return {
        "Departure Time": await extract_text('span', "Departure time"),
        "Arrival Time": await extract_text('span', "Arrival time"),
        "Airline Company": await extract_text(".sSHqwe"),
        "Flight Duration": await extract_text("div.gvkrdb"),
        "Stops": await extract_text("div.EfT7Ae span.ogfYpf"),
        "Price": await extract_text("div.FpEdX span"),
        "co2 emissions": await extract_text("div.O7CXue"),
        "emissions variation": await extract_text("div.N6PNV")
    }

async def scrape_flight_data(url):
    flight_data = []
    playwright, browser, page = await setup_browser()
    
    try:
        await page.goto(url)
        await page.wait_for_selector(".pIav2d", timeout=30000)  # 30 second timeout
        flights = await page.query_selector_all(".pIav2d")
        
        for flight in flights:
            flight_info = await scrape_flight_info(flight)
            flight_data.append(flight_info)
            
        return flight_data
    finally:
        await browser.close()
        await playwright.stop()

@app.get("/")
async def root():
    return {"message": "Welcome to Flight Price Scraper API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/search")
async def search_flights(request: FlightRequest):
    if not request.validate_date_format():
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    if not request.validate_airport_code(request.departure):
        raise HTTPException(status_code=400, detail="Invalid departure airport code")
        
    if not request.validate_airport_code(request.destination):
        raise HTTPException(status_code=400, detail="Invalid destination airport code")

    try:
        url = FlightURLBuilder.build_url(
            departure=request.departure.upper(),
            destination=request.destination.upper(),
            departure_date=request.departure_date
        )
        
        flight_data = await scrape_flight_data(url)
        return {"flights": flight_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
