#!/bin/bash
# Initialize database tables
python -c "from app.database.create_tables import *; print('✓ Database tables created')"

# Run the main pipeline
python main.py
