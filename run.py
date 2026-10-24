"""
Runner script for Velvet Roast Cafe POS Backend.
"""
import uvicorn
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("=================================================================")
    print("  Starting Velvet Roast Cafe POS Backend API Server")
    print("  Floor Plan & Table Dashboard: http://localhost:8000")
    print("  Interactive Swagger Docs:     http://localhost:8000/docs")
    print("  Kitchen Display System:       http://localhost:8000/static/kds.html")
    print("  Checkout & Split Billing:     http://localhost:8000/static/checkout.html")
    print("  Order Management Register:    http://localhost:8000/static/register.html")
    print("  Inventory Stock Tracker:      http://localhost:8000/static/inventory.html")
    print("=================================================================")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)
