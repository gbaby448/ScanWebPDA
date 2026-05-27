import ai_filter
import notifier

def test_ai_filter():
    assert ai_filter.check_ollama_status() is not None, "Ollama status check should return a value"

def test_notifier():
    assert notifier.test_ntfy_diagnostic("https://ntfy.sh/example", lambda _: None) == True, "Ntfy diagnostic should return True"