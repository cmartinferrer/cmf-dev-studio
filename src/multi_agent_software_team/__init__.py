"""Multi-Agent Studio."""

def main() -> int:
    import uvicorn
    uvicorn.run("multi_agent_software_team.api.app:app", host="127.0.0.1", port=8000)
    return 0
