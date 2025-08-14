import google.generativeai as genai


def ask_once(prompt: str, *, api_key: str, model: str = "gemini-1.5-flash") -> str:
    """
    Send a single prompt, return plain text answer.
    """
    genai.configure(api_key=api_key)
    m = genai.GenerativeModel(model)
    resp = m.generate_content(prompt)
    # robustness: if candidates empty or no text
    if not getattr(resp, "text", None):
        return "(No text response)"
    return resp.text