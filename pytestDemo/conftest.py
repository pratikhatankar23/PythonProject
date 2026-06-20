import pytest


@pytest.fixture(scope="session") #module

#function -- it will run before each test case
#Module -- it will run ones before all the testcases in .py file
#session -- it will run ones before all the testcases folder (project)


def preSetupWork():
    print("I setup browser instance")