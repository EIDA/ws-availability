
import sys
import os

# Add the project root directory to the python path
# This ensures that 'apps' can be imported during tests,
# regardless of where pytest is run from (e.g. CI environments).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
