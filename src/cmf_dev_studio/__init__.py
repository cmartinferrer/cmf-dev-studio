"""CMF Dev Studio."""

def main() -> int:
    import uvicorn
    uvicorn.run("cmf_dev_studio.api.app:app", host="127.0.0.1", port=8000)
    return 0
