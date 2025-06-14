import importlib

def test_lightweight_import():
    try:
        import videocut
        importlib.reload(videocut)
    except ModuleNotFoundError as e:
        assert False, f"Import failed with missing module: {e}"

