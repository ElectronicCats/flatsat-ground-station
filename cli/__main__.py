#!/usr/bin/env python3

import os
import sys

# Add vendor directory to sys.path for bundled dependencies
# In development, this is relative to the current script
vendor_path = os.path.join(os.path.dirname(__file__), "vendor")
if os.path.exists(vendor_path):
    sys.path.insert(0, vendor_path)

# Internal
from cli.app import main

if __name__ == "__main__":
    main()
