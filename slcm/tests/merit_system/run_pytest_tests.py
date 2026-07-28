import pytest
import os

def run():
    pytest.main([os.path.dirname(__file__), "-v", "--tb=short", "-s"])

if __name__ == "__main__":
    run()

# bench --site slcm execute slcm.tests.merit_system.run_pytest_tests.run
#bench --site slcm run-tests --app slcm --module slcm.tests.merit_system.test_merit_system_bench
