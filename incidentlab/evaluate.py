"""Compatibility entry point: testing only; never trains or calibrates."""
from .test_model import test_model

if __name__ == "__main__":
    test_model()
