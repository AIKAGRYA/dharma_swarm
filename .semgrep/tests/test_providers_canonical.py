def violation_anthropic_from():
    # ruleid: dharma.providers-canonical
    from anthropic import AsyncAnthropic
    return AsyncAnthropic


def violation_anthropic_import():
    # ruleid: dharma.providers-canonical
    import anthropic
    return anthropic


def violation_openai_from():
    # ruleid: dharma.providers-canonical
    from openai import AsyncOpenAI
    return AsyncOpenAI


def violation_ollama():
    # ruleid: dharma.providers-canonical
    import ollama
    return ollama


def ok_via_factory():
    # ok: dharma.providers-canonical
    from dharma_swarm.providers import get_provider
    return get_provider
