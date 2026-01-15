# HangiAltin - BIST Gold ETF Comparison

A Python backend service to find the cheapest BIST (Borsa İstanbul) gold ETF to buy, similar to hangikredi's approach.

## Features

- Compare multiple BIST gold ETFs (ZGOLD, GLDTR, ISGLK, etc.)
- Find the cheapest option based on price per gram of gold
- NAV (Net Asset Value) comparison
- Get detailed price comparisons
- RESTful API with FastAPI
- Modern, responsive web interface

## Installation

1. **Create a virtual environment** (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

## Running the Server

**Start the FastAPI server:**
```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## Access the Application

After starting the server:

- **Front-End**: `http://localhost:8000/` or `http://localhost:8000/static/index.html`
- **API**: `http://localhost:8000/api`
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`

## Front-End Features

- 🎨 Beautiful, modern UI with gradient design
- 📊 Real-time ETF price comparison
- 🏆 Highlights the cheapest option (by price per gram)
- 📱 Fully responsive (mobile-friendly)
- 🔄 Auto-refresh functionality
- 💹 Shows NAV comparison, price changes, volume, and differences
- 📐 Detailed calculation formulas

## API Endpoints

### Get All Gold ETFs
```
GET /api/gold-etf/list
```

### Get Specific ETF Details
```
GET /api/gold-etf/{symbol}
```

### Compare All ETFs (Find Cheapest)
```
GET /api/gold-etf/compare
```

### Compare Two Specific ETFs
```
GET /api/gold-etf/compare/{symbol1}/{symbol2}
```

## Quick Start Guide

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the server:**
   ```bash
   uvicorn app.main:app --reload
   ```

3. **Open your browser:**
   ```
   http://localhost:8000
   ```

4. **Click "Karşılaştır" button** to see ETF comparisons

## Troubleshooting

### Port Already in Use
If port 8000 is already in use, use a different port:
```bash
uvicorn app.main:app --reload --port 8001
```

### Rate Limiting
Yahoo Finance has strict rate limits. If you see rate limit errors:
- Wait 5-10 minutes before trying again
- The API uses caching (5 min TTL) to reduce requests
- Consider using the front-end which handles errors gracefully

### Missing Dependencies
If you get import errors:
```bash
pip install --upgrade -r requirements.txt
```

## Project Structure

```
hangialtin/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app
│   ├── models.py            # Pydantic models
│   ├── routers/
│   │   ├── __init__.py
│   │   └── gold_etf.py      # API routes
│   └── services/
│       ├── __init__.py
│       ├── bist_fetcher.py  # BIST data fetcher (yfinance)
│       └── comparison_service.py  # Comparison logic
├── static/
│   ├── index.html           # Front-end HTML
│   ├── styles.css           # Front-end styles
│   └── app.js               # Front-end JavaScript
├── requirements.txt
└── README.md
```

## License

MIT
