#!/usr/bin/env python3
"""
Main Entry Point for Trading Bot
This script provides an easy way to run the trading bot from the project root.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(__file__))

# Import and run the main script
if __name__ == "__main__":
    from src.core.script import main
    main()
