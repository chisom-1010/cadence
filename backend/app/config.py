from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase (server-side only; never expose the service key to the client)
    supabase_url: str
    supabase_service_key: str

    # CORS: comma-separated list of allowed frontend origins
    cors_origins: str = "http://localhost:3000"

    # Email
    mailtrap_api_token: str = ""
    sender_email: str = ""
    sender_name: str = "Outreach"
    # Demo mode: when set, every outgoing email is redirected to this address
    demo_recipient: str = ""
    # Live sending: email the lead's own address. Off by default. While off, every email is
    # delivered only to the signed-in account owner (or DEMO_RECIPIENT if set).
    live_sending: bool = False

    # LLM: any OpenAI-compatible chat completions endpoint (Groq, Gemini, ...)
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_api_key: str = ""
    llm_model: str = ""
    # Optional cheaper model for bulk lead research; falls back to llm_model
    llm_model_fast: str = ""

    # Web search for lead discovery (Tavily)
    tavily_api_key: str = ""

    # Limits
    max_leads_per_discovery: int = 20
    research_delay_seconds: float = 2.0
    website_text_chars: int = 5000
    min_fit_to_draft: int = 40
    send_delay_seconds: float = 1.0

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
