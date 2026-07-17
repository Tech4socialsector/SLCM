import pytest
import os

def run():
    pytest.main([os.path.dirname(__file__), "-v", "--tb=short", "-s"])

if __name__ == "__main__":
    run()
