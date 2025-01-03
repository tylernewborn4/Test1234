from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import asyncio
from flight_scraper import FlightURLBuilder, scrape_flight_data
from datetime import datetime
import uvicorn
import os
import json

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

@app.get("/")
async def root():
    return {
        "message": "Welcome to Flight Price Scraper API",
        "endpoints": {
            "/search": "POST - Search for flights",
            "/health": "GET - Check API health"
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/search")
async def search_flights(request: FlightRequest):
    # Validate input
    if not request.validate_date_format():
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    if not request.validate_airport_code(request.departure):
        raise HTTPException(status_code=400, detail="Invalid departure airport code")
        
    if not request.validate_airport_code(request.destination):
        raise HTTPException(status_code=400, detail="Invalid destination airport code")

    try:
        # Generate URL
        url = FlightURLBuilder.build_url(
            departure=request.departure.upper(),
            destination=request.destination.upper(),
            departure_date=request.departure_date
        )
        
        # Scrape flight data
        flight_data = await scrape_flight_data(url)
        
        return {"flights": flight_data}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
