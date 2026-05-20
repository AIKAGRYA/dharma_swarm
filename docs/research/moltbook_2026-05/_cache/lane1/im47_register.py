from src.providers.moltbook_provider import MoltbookProvider
from src.settings import settings

moltbook_api = MoltbookProvider()

response = moltbook_api.register(
    name=settings.AGENT_NAME, description=settings.AGENT_DESCRIPTION
)

print(response)
