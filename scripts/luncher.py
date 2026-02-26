import os
import sys
import uvicorn

# Ensure project root is on sys.path when running this file directly.
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="localhost", port=8080, reload=True)
