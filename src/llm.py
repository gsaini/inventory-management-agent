"""
LLM Factory - Multi-provider LLM initialization

Supports:
- Ollama (local open source models)
- OpenAI (cloud)
- OpenAI-compatible APIs (vLLM, LM Studio, LocalAI, text-generation-webui)
- HuggingFace Inference API
"""

from functools import lru_cache
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel

from src.config import get_settings, LLMProvider


def get_ollama_llm(model: str | None = None, **kwargs) -> BaseChatModel:
    """
    Get Ollama LLM instance.
    
    Requires: pip install langchain-ollama
    Setup: Install Ollama from https://ollama.ai, then run:
        ollama pull llama3.1:8b
        ollama serve
    """
    from langchain_ollama import ChatOllama
    
    settings = get_settings()
    return ChatOllama(
        base_url=settings.ollama_base_url,
        model=model or settings.ollama_model,
        temperature=kwargs.get("temperature", 0),
        **{k: v for k, v in kwargs.items() if k != "temperature"},
    )


def get_openai_llm(model: str | None = None, **kwargs) -> BaseChatModel:
    """
    Get OpenAI LLM instance.
    
    Requires: pip install langchain-openai
    Setup: Set OPENAI_API_KEY in .env
    """
    from langchain_openai import ChatOpenAI
    
    settings = get_settings()
    return ChatOpenAI(
        model=model or settings.openai_model,
        temperature=kwargs.get("temperature", 0),
        api_key=settings.openai_api_key,
        **{k: v for k, v in kwargs.items() if k != "temperature"},
    )


def get_openai_compatible_llm(model: str | None = None, **kwargs) -> BaseChatModel:
    """
    Get OpenAI-compatible LLM instance (vLLM, LM Studio, LocalAI, etc.).
    
    Requires: pip install langchain-openai
    Setup examples:
        vLLM:      python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.1-8B-Instruct
        LM Studio: Start from GUI, enable server mode
        LocalAI:   docker run -p 8080:8080 localai/localai
    """
    from langchain_openai import ChatOpenAI
    
    settings = get_settings()
    return ChatOpenAI(
        base_url=settings.openai_compatible_base_url,
        model=model or settings.openai_compatible_model,
        temperature=kwargs.get("temperature", 0),
        api_key=settings.openai_compatible_api_key,
        **{k: v for k, v in kwargs.items() if k != "temperature"},
    )


def get_huggingface_llm(model: str | None = None, **kwargs) -> BaseChatModel:
    """
    Get HuggingFace Inference API LLM instance.
    
    Requires: pip install langchain-huggingface
    Setup: Set HUGGINGFACE_API_KEY in .env
    """
    from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
    
    settings = get_settings()
    
    # Create the endpoint
    endpoint = HuggingFaceEndpoint(
        repo_id=model or settings.huggingface_model,
        huggingfacehub_api_token=settings.huggingface_api_key,
        temperature=kwargs.get("temperature", 0.01),  # HF doesn't support exactly 0
        max_new_tokens=kwargs.get("max_new_tokens", 1024),
    )
    
    return ChatHuggingFace(llm=endpoint)


@lru_cache
def get_llm(
    model: str | None = None,
    mini: bool = False,
    **kwargs: Any,
) -> BaseChatModel:
    """
    Get LLM instance based on configured provider.
    
    Args:
        model: Override the model name (optional)
        mini: Use the smaller/faster model variant
        **kwargs: Additional arguments passed to the LLM constructor
    
    Returns:
        BaseChatModel instance ready to use with LangChain
    
    Examples:
        # Use default provider and model from config
        llm = get_llm()
        
        # Use mini model for faster responses
        llm = get_llm(mini=True)
        
        # Override model
        llm = get_llm(model="llama3.2:1b")
        
        # With tools
        llm = get_llm().bind_tools(my_tools)
    """
    settings = get_settings()
    provider = settings.llm_provider
    
    # Determine model based on mini flag
    if model is None and mini:
        if provider == LLMProvider.OLLAMA:
            model = settings.ollama_model_mini
        elif provider == LLMProvider.OPENAI:
            model = settings.openai_model_mini
        # Other providers don't have mini variants configured
    
    # Get LLM based on provider
    if provider == LLMProvider.OLLAMA:
        return get_ollama_llm(model, **kwargs)
    elif provider == LLMProvider.OPENAI:
        return get_openai_llm(model, **kwargs)
    elif provider == LLMProvider.OPENAI_COMPATIBLE:
        return get_openai_compatible_llm(model, **kwargs)
    elif provider == LLMProvider.HUGGINGFACE:
        return get_huggingface_llm(model, **kwargs)
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def get_llm_with_tools(tools: list, model: str | None = None, mini: bool = False) -> BaseChatModel:
    """
    Get LLM instance with tools bound.
    
    This is a convenience function for agents that need tool-calling.
    
    Args:
        tools: List of LangChain tools to bind
        model: Override the model name (optional)
        mini: Use the smaller/faster model variant
    
    Returns:
        BaseChatModel with tools bound
    """
    # Clear cache to get fresh instance (tools can't be bound to cached LLM)
    get_llm.cache_clear()
    
    llm = get_llm(model=model, mini=mini)
    return llm.bind_tools(tools)


# Provider information for help/docs
PROVIDER_INFO = {
    LLMProvider.OLLAMA: {
        "name": "Ollama",
        "description": "Local open-source models (Llama 4, Mistral, Qwen, etc.)",
        "install": "https://ollama.ai",
        "setup": [
            "1. Install Ollama from https://ollama.ai",
            "2. Pull a model: ollama pull llama4:scout",
            "3. Start server: ollama serve",
            "4. Set LLM_PROVIDER=ollama in .env",
        ],
        "recommended_models": [
            "llama4:scout - Llama 4 Scout 17B/16E (109B MoE, default)",
            "llama4:maverick - Llama 4 Maverick 17B/128E (402B MoE, highest quality)",
            "llama3.3:70b - Llama 3.3 70B (text-only, very capable)",
            "mistral:7b - Fast and efficient",
            "qwen2.5:7b - Strong coding abilities",
            "deepseek-coder-v2:16b - Best for code tasks",
        ],
    },
    LLMProvider.OPENAI: {
        "name": "OpenAI",
        "description": "Cloud-hosted GPT models",
        "install": "pip install langchain-openai",
        "setup": [
            "1. Get API key from https://platform.openai.com",
            "2. Set OPENAI_API_KEY in .env",
            "3. Set LLM_PROVIDER=openai in .env",
        ],
        "recommended_models": [
            "gpt-4o - Best quality",
            "gpt-4o-mini - Fast and cheap",
        ],
    },
    LLMProvider.OPENAI_COMPATIBLE: {
        "name": "OpenAI-Compatible",
        "description": "vLLM, LM Studio, LocalAI, text-generation-webui",
        "install": "Depends on server choice",
        "setup": [
            "vLLM:",
            "  pip install vllm",
            "  python -m vllm.entrypoints.openai.api_server --model meta-llama/Llama-3.1-8B-Instruct",
            "",
            "LM Studio:",
            "  Download from https://lmstudio.ai",
            "  Enable local server in settings",
            "",
            "LocalAI:",
            "  docker run -p 8080:8080 localai/localai",
        ],
        "recommended_models": ["Depends on server"],
    },
    LLMProvider.HUGGINGFACE: {
        "name": "HuggingFace",
        "description": "HuggingFace Inference API (cloud)",
        "install": "pip install langchain-huggingface",
        "setup": [
            "1. Get API key from https://huggingface.co/settings/tokens",
            "2. Set HUGGINGFACE_API_KEY in .env",
            "3. Set LLM_PROVIDER=huggingface in .env",
        ],
        "recommended_models": [
            "meta-llama/Llama-4-Scout-17B-16E-Instruct",
            "meta-llama/Llama-4-Maverick-17B-128E-Instruct",
            "meta-llama/Llama-3.3-70B-Instruct",
        ],
    },
}


def print_provider_info():
    """Print information about available LLM providers."""
    print("\n" + "=" * 60)
    print("Available LLM Providers")
    print("=" * 60)
    
    for provider, info in PROVIDER_INFO.items():
        print(f"\n{info['name']} ({provider.value})")
        print("-" * 40)
        print(f"Description: {info['description']}")
        print(f"\nSetup:")
        for step in info["setup"]:
            print(f"  {step}")
        print(f"\nRecommended Models:")
        for model in info["recommended_models"]:
            print(f"  • {model}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    print_provider_info()
