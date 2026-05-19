"""Application settings, loaded from environment / .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    db_name: str = "supermarket_assistant"

    # CORS — the Next.js frontend origin(s)
    frontend_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # App
    app_name: str = "AI Phone Call Sales Assistant"
    debug: bool = False

    # --- Vapi (outbound calling) -------------------------------------------
    # API key for api.vapi.ai. When blank, the call service runs in DRY-RUN
    # mode: the compliance gate still runs and a call record is still
    # written, but no real telephony happens. This lets the whole flow be
    # demoed without a Vapi account.
    vapi_api_key: str = ""
    vapi_base_url: str = "https://api.vapi.ai"

    # The Vapi phone number to dial FROM (the "phoneNumberId" in Vapi's API).
    # Required for a live call; ignored in dry-run mode.
    vapi_phone_number_id: str = ""

    # The saved Vapi assistant to use for calls. This assistant is built and
    # configured ONCE in the Vapi dashboard (system prompt, voice, the four
    # function tools, and a server URL pointing at /calls/webhook). The
    # backend simply references it by id on every call. Required for a live
    # call; without it a live call is refused with a clear error.
    vapi_assistant_id: str = ""

    # Optional per-call webhook URL override. Set this to your public tunnel
    # URL plus /calls/webhook if you do not want to rely on the assistant's
    # saved server URL in Vapi.
    vapi_webhook_url: str = ""

    # The supermarket name used in the dashboard and surfaced to staff.
    supermarket_name: str = "Foodie"

    # --- Compliance (Australia) --------------------------------------------
    # Single timezone the calling-hours gate evaluates against. v1 is
    # demo-scale and customers carry no per-customer timezone; a per-customer
    # tz would be a customers-schema change (noted as a follow-up).
    calling_timezone: str = "Australia/Sydney"

    # Permitted calling window, local to calling_timezone, 24h clock.
    # The Telemarketing Industry Standard 2017 allows weekday calls
    # 9am–8pm and Saturday 9am–5pm; Sundays and public holidays are
    # excluded. Public-holiday data is out of scope for the demo.
    calling_hour_start: int = 9  # inclusive
    calling_hour_end_weekday: int = 20  # exclusive (8pm)
    calling_hour_end_saturday: int = 17  # exclusive (5pm)
    calling_allow_sunday: bool = False

    # Set true to bypass the calling-hours gate (useful for demos / tests
    # run outside the window). The do_not_call check is NEVER bypassed.
    calling_hours_override: bool = False


settings = Settings()
