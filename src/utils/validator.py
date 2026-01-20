import requests

def verify_url(url: str) -> bool:
    """
    Weryfikuje, czy URL istnieje (status < 400), wykonując request HEAD.
    Służy do wykrywania halucynacji LLM.
    
    Args:
        url (str): Adres URL do sprawdzenia.
        
    Returns:
        bool: True jeśli URL działa, False w przeciwnym razie.
    """
    if not url or not url.startswith(("http://", "https://")):
        return False
        
    try:
        response = requests.head(url, timeout=3, allow_redirects=True)
        return response.status_code < 400
    except requests.RequestException:
        return False
