from typing import Iterator, Union

import google.generativeai as genai


def one_time_chat(
    prompt: str,
    *,
    api_key: str,
    model: str = "gemini-2.5-flash-lite",
    stream: bool = False,
) -> Union[Iterator[str], str]:
    """
    If stream=False: returns a plain string.
    If stream=True:  returns an iterator[str] yielding chunks.
    """
    genai.configure(api_key=api_key)
    m = genai.GenerativeModel(model)

    if stream:
        def _gen() -> Iterator[str]:
            resp_stream = m.generate_content(prompt, stream=True)
            for event in resp_stream:
                chunk = getattr(event, "text", None)
                if chunk:
                    yield chunk
        return _gen()

    resp = m.generate_content(prompt)
    return getattr(resp, "text", "") or "(No text response)"