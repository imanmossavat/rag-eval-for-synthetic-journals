"""Put the generator package dir on sys.path so its bare imports (`import config`,
`from llm import ...`) resolve when pytest runs from anywhere."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
