#!/usr/bin/env python
"""
Hammer Chat CLI - Entry Point
==============================

Quick access to chat with The Hammer data.

Usage:
    python chat_cli.py

Commands inside chat:
    help  - Show available commands
    stats - Show knowledge base statistics
    exit  - Exit the chat
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.cli.chat import main

if __name__ == "__main__":
    main()
