from .base import LLMProvider
from .openai_provider import OpenAIProvider


def get_llm_provider(provider_name: str, **kwargs) -> LLMProvider:
    """
    Factory function to get an LLM provider instance.

    Args:
        provider_name: Name of the provider (openai, google, anthropic)
        **kwargs: Provider-specific configuration (e.g., api_key)

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider is not supported
    """
    providers = {
        "openai": OpenAIProvider,
    }

    provider_class = providers.get(provider_name.lower())
    if provider_class is None:
        supported = ", ".join(providers.keys())
        raise ValueError(
            f"Unsupported LLM provider: {provider_name}. Supported: {supported}"
        )

    return provider_class(**kwargs)
